"""
OCIF Decision & Action Service Wrapper — Layer 7 (META CORE).

Orchestrates RAG output verification, rules-as-code checks, risk valuations,
HITL approval queues, sandboxed action execution, and immutable audit persistence.

Traces to:
  - Document 7 (LLD) Section 8: Decision & Action Layer (Integrations)
  - Document 14 (Security Design) Section 6: Guardrails & Policy Engine
  - Document 13 (Agent Design) Section 5: Governance Invariants
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.config import settings
from axiom.core.exceptions import PolicyViolationError, HITLRequiredError, GovernanceBlockedError
from axiom.core.models.base import DecisionOutcome, PolicyCheckResult, UserRole

from axiom.core.models.cognition import CognitionResult, ProposedAction
from axiom.core.models.decision import DecisionRecord, PolicyCheck, ExecutionLog
from axiom.layer7_decision.policy_engine import PolicyEngine
from axiom.layer7_decision.hallucination_detector import HallucinationDetector
from axiom.layer7_decision.risk_scorer import RiskScorer
from axiom.layer7_decision.hitl_queue import HITLQueue
from axiom.layer7_decision.action_executor import ActionExecutor
from axiom.layer7_decision.audit_logger import AuditLogger
from axiom.storage.models import Tool

logger = logging.getLogger("AxiomDecisionService")


class DecisionService:
    """
    Unified entrypoint for the Layer 7 Decision & Action (META CORE) Service.
    """

    def __init__(self) -> None:
        self.policy_engine = PolicyEngine()
        self.hallucination_detector = HallucinationDetector()
        self.risk_scorer = RiskScorer()
        self.hitl_queue = HITLQueue()
        self.action_executor = ActionExecutor()
        self.audit_logger = AuditLogger()

    async def evaluate_and_execute(
        self,
        db: AsyncSession,
        cognition_result: CognitionResult
    ) -> DecisionRecord:
        """
        Coordinates hallucination detection, rules checks, risk scoring,
        and logs the outcome in the hash-chained audit ledger.
        
        Executes actions synchronously if auto-approved, or queues for HITL.
        """
        request_context = cognition_result.request_context
        tenant_id = request_context.tenant.tenant_id
        session_id = request_context.session_id
        user_role = request_context.user.role

        logger.info(f"Evaluating decision boundaries for request context: {request_context.correlation_id}")

        # 1. Verification Phase: Hallucination Check
        grounding_chunks = cognition_result.orchestration_plan.enriched_context.retrieved_chunks
        no_grounding_found = cognition_result.orchestration_plan.enriched_context.no_grounding_found

        is_grounded, grounding_score, grounding_err = self.hallucination_detector.verify_grounding(
            content=cognition_result.content,
            grounding_chunks=grounding_chunks,
            no_grounding_found=no_grounding_found
        )

        checks: List[PolicyCheck] = []
        if not is_grounded:
            checks.append(
                PolicyCheck(
                    rule_name="hallucination-prevention-gate",
                    result=PolicyCheckResult.FAIL,
                    description="Factual overlap validation check against grounding documents",
                    error_message=grounding_err
                )
            )

        # 2. Rules Evaluation Phase
        policy_checks = []
        decision_outcome = DecisionOutcome.AUTO_APPROVED
        max_risk = 0.0
        
        # If hallucination check failed, block action immediately
        if not is_grounded:
            decision_outcome = DecisionOutcome.BLOCKED

        # Map actions proposed by Layer 6 Cognition
        proposed_actions = cognition_result.proposed_actions
        action_taken_snapshot = None

        if proposed_actions and is_grounded:
            # We evaluate each proposed action against policies
            for action in proposed_actions:
                # Load tool settings to get risk level & endpoint configuration
                # Find matching Tool definition in registry
                from sqlalchemy import select
                from axiom.storage.models import Tool
                
                tool_res = await db.execute(
                    select(Tool)
                    .filter(Tool.tool_id == action.tool_id)
                    .filter(Tool.tenant_id == tenant_id)
                )
                tool = tool_res.scalars().first()
                tool_risk_level = tool.risk_level if tool else action.risk_self_assessment
                endpoint = tool.endpoint if tool else "local"

                # A. Evaluate deterministic policy engine checks
                rule_checks = await self.policy_engine.evaluate_policies(
                    db=db,
                    tenant_id=tenant_id,
                    action_type=action.action_type,
                    payload=action.payload
                )
                policy_checks.extend(rule_checks)

                # If any rule failed, block it
                if any(c.result == PolicyCheckResult.FAIL for c in rule_checks):
                    decision_outcome = DecisionOutcome.BLOCKED
                    break

                # B. Risk Assessment
                action_risk = self.risk_scorer.calculate_risk(
                    action_type=action.action_type,
                    payload=action.payload,
                    user_role=user_role,
                    tool_risk_level=tool_risk_level
                )
                max_risk = max(max_risk, action_risk)

            # C. Route based on risk thresholds
            if decision_outcome != DecisionOutcome.BLOCKED:
                if max_risk > settings.policy.hitl_required_min_risk:
                    # Risk is too high: force queue for HITL approval
                    decision_outcome = DecisionOutcome.BLOCKED  # Blocked until reviewer logs approval
                elif max_risk > settings.policy.auto_approval_max_risk:
                    # Risk is medium: route to HITL approval
                    decision_outcome = DecisionOutcome.BLOCKED

        # 3. Action Execution Phase (Only if auto-approved)
        execution_logs: List[ExecutionLog] = []
        approval_id = None

        if decision_outcome == DecisionOutcome.AUTO_APPROVED and proposed_actions:
            for action in proposed_actions:
                # Resolve endpoint
                from sqlalchemy import select
                from axiom.storage.models import Tool
                tool_res = await db.execute(select(Tool).filter(Tool.tool_id == action.tool_id))
                tool = tool_res.scalars().first()
                endpoint = tool.endpoint if tool else "local"
                
                # Sandboxed dispatch
                log = await self.action_executor.execute_action(
                    action_type=action.action_type,
                    payload=action.payload,
                    endpoint=endpoint
                )
                execution_logs.append(log)
                action_taken_snapshot = {
                    "action_type": action.action_type,
                    "payload": action.payload,
                    "status": log.status
                }
        elif decision_outcome == DecisionOutcome.BLOCKED and proposed_actions:
            # Check if this qualifies for HITL queueing
            if max_risk > settings.policy.auto_approval_max_risk:
                # We need to write a stub AuditEvent first so that it is hash-chained
                # and linked to the HITL approval ticket
                pass

        # 4. Audit persistence phase (tamper-evident SHA-256 chain link)
        # Note: Fail-closed: audit logging errors rollback transactions automatically
        policy_snapshot = [
            {"rule_name": c.rule_name, "result": c.result, "error": c.error_message}
            for c in (checks + policy_checks)
        ]
        
        sources_snapshot = [
            {"chunk_id": c.chunk_id, "title": c.title, "score": c.score}
            for c in grounding_chunks
        ]

        audit_event = await self.audit_logger.log_event(
            db=db,
            tenant_id=tenant_id,
            session_id=session_id,
            actor="human" if user_role == UserRole.PROCESS_OWNER else "agent",
            input_snapshot={"query": cognition_result.orchestration_plan.enriched_context.context_frame.request_context.session_id},
            retrieved_sources=sources_snapshot,
            model_used=cognition_result.model_name_used,
            policy_checks=policy_snapshot,
            risk_score=max_risk,
            decision=decision_outcome.value,
            action_taken=action_taken_snapshot
        )

        # 5. Queue HITL ticket if needed
        # We link the pending HITL ticket to the newly created AuditEvent ID
        if decision_outcome == DecisionOutcome.BLOCKED and max_risk > settings.policy.auto_approval_max_risk:
            approval_id = await self.hitl_queue.create_approval_request(
                db=db,
                event_id=audit_event.event_id,
                tenant_id=tenant_id
            )
            # Raise human approval error to trigger 202 status outputs at L8
            raise HITLRequiredError(
                detail="Action requires human-in-the-loop validation.",
                approval_id=approval_id,
                risk_score=max_risk
            )

        # Raise standard rule failures if blocked
        if decision_outcome == DecisionOutcome.BLOCKED:
            failures = [c.error_message for c in (checks + policy_checks) if c.result == PolicyCheckResult.FAIL]
            raise PolicyViolationError(
                detail=f"Proposed action violates policy rules: {failures}",
                violated_rules=failures,
                risk_score=max_risk
            )

        # 6. Assemble and return DecisionRecord
        record = DecisionRecord(
            outcome=decision_outcome,
            risk_score=max_risk,
            policy_checks=checks + policy_checks,
            audit_event_id=audit_event.event_id,
            prev_event_hash=audit_event.prev_event_hash,
            event_hash=audit_event.event_hash,
            approval_id=approval_id,
            execution_logs=execution_logs,
            cognition_result=cognition_result,
            request_context=request_context
        )

        return record
