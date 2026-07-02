"""
OCIF Cognition Service Wrapper — Layer 6.

Orchestrates prompt generation, LLM provider routing, fallback execution loops
on network/model failures (per Doc 18 Section 7), confidence scorer calibration,
proposed action parsing, and outputs the canonical CognitionResult DTO.

Traces to:
  - Document 6 (LLD) Section 7: Cognition Service
  - Document 10 (API Specification) Section 6: Cognition API
  - Document 12 (Prompt Engineering Guide) Section 8: Provider adaptation
"""

import json
import logging
import re
from typing import Dict, Any, List, Tuple

from axiom.core.config import settings
from axiom.core.exceptions import LLMProviderError, LLMTimeoutError
from axiom.core.models.base import LLMProvider, RequestContext
from axiom.core.models.cognition import CognitionResult, ProposedAction, TokenUsage
from axiom.core.models.orchestration import OrchestrationPlan
from axiom.layer6_cognition.model_router import ModelRouter
from axiom.layer6_cognition.confidence_scorer import ConfidenceScorer

logger = logging.getLogger("AxiomCognitionService")


class CognitionService:
    """
    Unified entrypoint for the Layer 6 Cognition (LLM Gateway) Service.
    """

    def __init__(self) -> None:
        self.router = ModelRouter()
        self.scorer = ConfidenceScorer()

    async def execute_reasoning(
        self,
        request_context: RequestContext,
        orchestration_plan: OrchestrationPlan,
        prompt: str,
        selected_provider: str = "auto"
    ) -> CognitionResult:
        """
        Executes reasoning trace generation via LLM gateway routing.
        Implements automatic fallback retry logic if the primary provider fails.
        """
        logger.info(f"Dispatched reasoning request. Correlation ID: {request_context.correlation_id}")

        # Resolve provider enum
        try:
            prov_enum = LLMProvider(selected_provider.lower())
        except ValueError:
            prov_enum = LLMProvider.AUTO

        # 1. Resolve Provider and execute with fallback loop
        intent = orchestration_plan.enriched_context.context_frame.intent
        
        provider_name, provider_impl = self.router.get_provider(prov_enum, intent)
        
        response_payload = None
        attempts = 0
        max_attempts = 2

        while attempts < max_attempts:
            attempts += 1
            try:
                response_payload = await provider_impl.generate(
                    prompt=prompt,
                    max_tokens=settings.llm.default_max_tokens,
                    temperature=settings.llm.default_temperature
                )
                break  # Success!
            except Exception as e:
                logger.error(f"Provider '{provider_name}' generation failed: {e}. Attempt {attempts}/{max_attempts}")
                
                # Register failure to circuit-break it
                self.router.report_failure(provider_name)
                
                if attempts >= max_attempts:
                    logger.critical("All LLM provider options failed. Raising gateway error.")
                    raise LLMProviderError(
                        detail=f"Inference gateway failure: {str(e)}",
                        provider=provider_name.value
                    )
                
                # Fetch fallback option
                provider_name, provider_impl = self.router.get_provider(LLMProvider.AUTO, intent)
                logger.info(f"Retrying reasoning generation using fallback provider: '{provider_name}'")

        # 2. Calibrate confidence scores and compile tracing log
        raw_content = response_payload["content"]
        raw_confidence = response_payload["confidence_estimate"]
        
        calibrated_score, l6_trace = self.scorer.calculate_score(raw_content, raw_confidence)

        # Append details to reasoning trace
        full_reasoning_trace = (
            f"--- Layer 5 Orchestration ---\n"
            f"Workflow pattern: {orchestration_plan.coordination_pattern}\n"
            f"Step trace timeline: {len(orchestration_plan.steps)} tasks dispatched.\n\n"
            f"--- Layer 6 Inference Gateway ---\n"
            f"Model called: {response_payload['model_used']}\n"
            f"Router metrics: {l6_trace}\n\n"
        )

        # 3. Parse any structured proposed action blocks in response text
        # Per Doc 12 Section 4.2: Structured proposed action card parsing
        proposed_actions = self._parse_proposed_actions(raw_content)

        # 4. Map statistics DTOs
        usage_dict = response_payload.get("tokens_used", {})
        token_usage = TokenUsage(
            input_tokens=usage_dict.get("input", 0),
            output_tokens=usage_dict.get("output", 0),
            cost_usd=usage_dict.get("cost_usd", 0.0)
        )

        # 5. Compile and return CognitionResult
        result = CognitionResult(
            content=raw_content,
            confidence=calibrated_score,
            reasoning_trace=full_reasoning_trace,
            provider_used=provider_name.value,
            model_name_used=response_payload["model_used"],
            token_usage=token_usage,
            proposed_actions=proposed_actions,
            orchestration_plan=orchestration_plan,
            request_context=request_context
        )

        return result

    def _parse_proposed_actions(self, content: str) -> List[ProposedAction]:
        """
        Scans completion text for JSON proposed action structures.
        """
        proposed_actions = []
        
        # Search for json code blocks containing action_type keys
        json_blocks = re.findall(r"```(?:json)?\n(\{.*?\})```", content, re.DOTALL)
        
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                # Verify keys mapping ProposedAction DTO
                if "action_type" in data and ("tool_id" in data or "tool_input" in data):
                    # Safely compile
                    proposed_actions.append(
                        ProposedAction(
                            action_type=data["action_type"],
                            tool_id=data.get("tool_id", "unknown_tool"),
                            payload=data.get("tool_input", {}),
                            rationale=data.get("rationale", "Proposed during reasoning completion"),
                            risk_self_assessment=data.get("risk_self_assessment", "low")
                        )
                    )
            except Exception as e:
                # Log parser warning and skip block
                logger.warning(f"Failed to parse proposed action JSON block: {e}")
                
        return proposed_actions
