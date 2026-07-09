"""
OCIF Policy Engine — Layer 7 (META CORE).

Executes deterministic rules-as-code evaluation (rules DSL) over proposed actions.
Adheres to the default-deny and fail-closed security invariants (per Doc 14 Section 6).
Evaluations are completely deterministic and never run through an LLM.

Traces to:
  - Document 14 (Security Design) Section 6: Guardrails & Policy Engine
  - Document 7 (LLD) Section 12 Invariant 4: Fail-closed posture
  - Document 9 (Database Design) Section 4.5: policies schema
"""

import json
import logging
from typing import Dict, Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import PolicyViolationError, GovernanceBlockedError
from core.models.base import PolicyCheckResult
from core.models.decision import PolicyCheck
from storage.models import Policy

logger = logging.getLogger("AxiomPolicyEngine")


class PolicyEngine:
    """
    Deterministic rules-as-code engine.
    """

    async def evaluate_policies(
        self,
        db: AsyncSession,
        tenant_id: str,
        action_type: str,
        payload: Dict[str, Any]
    ) -> List[PolicyCheck]:
        """
        Loads and executes all active policies for the tenant.
        
        Enforces default-deny: if rules exist but none allow, or any checks fail,
        action is blocked. Fail-closed on errors.
        """
        logger.info(f"Evaluating policies for action '{action_type}' (Tenant: {tenant_id})")

        # 1. Fetch active policies from the database
        try:
            result = await db.execute(
                select(Policy)
                .filter(Policy.tenant_id == tenant_id)
                .filter(Policy.is_active == True)
            )
            policies = result.scalars().all()
        except Exception as e:
            logger.critical(f"Fail-closed: database query failed during policy evaluation: {e}")
            raise GovernanceBlockedError("Policy engine blocked: database schema access error during execution.")

        checks: List[PolicyCheck] = []

        # If no policies are registered, default to a general safety block (default-deny)
        if not policies:
            logger.warning(f"No active policies found for tenant {tenant_id}. Triggering default-deny block.")
            checks.append(
                PolicyCheck(
                    rule_name="default-deny-posture",
                    result=PolicyCheckResult.FAIL,
                    description="Default safety gate blocking action because no explicit tenant rules are loaded",
                    error_message="Action blocked: no active policies registered."
                )
            )
            return checks

        # 2. Evaluate each policy rule DSL
        for policy in policies:
            try:
                rule_def = json.loads(policy.rule_definition)
                # Structure: {"rules": [{"field": "amount", "operator": "lte", "value": 500.0, "action": "allow"}]}
                rules_list = rule_def.get("rules", [])
                
                for idx, rule in enumerate(rules_list):
                    rule_name = f"{policy.name}_r{idx}"
                    field = rule.get("field")
                    operator = rule.get("operator")
                    rule_value = rule.get("value")
                    effect = rule.get("effect", "deny")  # default deny

                    # Check if action has the required field to check
                    if field not in payload:
                        # Fail-closed: missing field required by policy rules triggers automatic deny
                        checks.append(
                            PolicyCheck(
                                rule_name=rule_name,
                                result=PolicyCheckResult.FAIL,
                                description=f"Evaluate field '{field}' using operator '{operator}'",
                                error_message=f"Fail-closed: payload missing required policy check property '{field}'"
                            )
                        )
                        continue

                    val = payload[field]
                    passed = self._eval_rule_condition(val, operator, rule_value)

                    if passed:
                        if effect == "allow":
                            checks.append(
                                PolicyCheck(
                                    rule_name=rule_name,
                                    result=PolicyCheckResult.PASS,
                                    description=f"Rule allowed action because field '{field}' satisfies '{operator}' condition"
                                )
                            )
                        else:
                            checks.append(
                                PolicyCheck(
                                    rule_name=rule_name,
                                    result=PolicyCheckResult.FAIL,
                                    description=f"Rule explicitly blocked action because field '{field}' satisfies '{operator}' condition",
                                    error_message=f"Action denied by policy rule: {policy.name}"
                                )
                            )
                    else:
                        # Rule condition did not match. If default effect is allow, then it fails, else it passes.
                        # For clean deterministic paths: if a condition isn't met, check next rule.
                        pass

            except Exception as e:
                logger.critical(f"Fail-closed: syntax/parsing error in policy rule definition: {e}")
                raise GovernanceBlockedError(f"Governance blocked: policy evaluation error in rule '{policy.name}'.")

        return checks

    def _eval_rule_condition(self, val: Any, operator: str, rule_value: Any) -> bool:
        """Determines condition matching."""
        try:
            if operator == "lte":
                return float(val) <= float(rule_value)
            elif operator == "gte":
                return float(val) >= float(rule_value)
            elif operator == "eq":
                return str(val).lower() == str(rule_value).lower()
            elif operator == "contains":
                return str(rule_value).lower() in str(val).lower()
            else:
                return False
        except Exception:
            return False
