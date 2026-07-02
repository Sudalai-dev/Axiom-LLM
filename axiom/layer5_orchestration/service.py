"""
OCIF Orchestration Service Wrapper — Layer 5.

Acts as the entrypoint for the Layer 5 Agent Runtime, coordinating multi-agent task execution
timelines and prompt construction templates before dispatching to model inference gateways.

Traces to:
  - Document 6 (LLD) Section 5: Orchestration Service
  - Document 13 (Agent Design) Section 3: Agent runtime context
"""

import logging
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.models.knowledge import EnrichedContext
from axiom.core.models.orchestration import OrchestrationPlan
from axiom.layer5_orchestration.prompt_builder import PromptBuilder
from axiom.layer5_orchestration.agent_graph import AgentGraphRuntime

logger = logging.getLogger("AxiomOrchestrationService")


class OrchestrationService:
    """
    Unified coordinator for the Layer 5 Agent Orchestration Layer.
    """

    def __init__(self) -> None:
        self.prompt_builder = PromptBuilder()
        self.agent_runtime = AgentGraphRuntime()

    async def execute_orchestration(
        self,
        db: AsyncSession,
        enriched_context: EnrichedContext,
        query: str
    ) -> Tuple[OrchestrationPlan, str]:
        """
        Runs the agent runtime graph, analyzes tools required, calculates execution risks,
        renders the prompt template payload, and compiles the final completion inputs.
        """
        logger.info(f"Initiating Layer 5 Orchestration. Correlation ID: {enriched_context.request_context.correlation_id}")

        # 1. Run collaborative agent graph execution timeline
        # (This populates tool outputs, step histories, and determines if side-effects are blocked)
        coordination_pattern = enriched_context.context_frame.request_context.metadata.get("coordination_pattern", "sequential")
        
        from axiom.core.models.base import CoordinationPattern
        try:
            pattern_enum = CoordinationPattern(coordination_pattern.lower())
        except ValueError:
            pattern_enum = CoordinationPattern.SEQUENTIAL

        orchestration_plan = await self.agent_runtime.run_agents(
            db=db,
            enriched_context=enriched_context,
            coordination_pattern=pattern_enum
        )

        # 2. Build the provider-agnostic system prompt content
        # (This merges RAG documents context, entity relationships, memory turns, and RBAC profiles)
        system_prompt = self.prompt_builder.build_system_prompt(enriched_context, query)

        return orchestration_plan, system_prompt
