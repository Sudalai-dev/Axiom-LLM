"""
Octagonal Kernel — executes the internal cognitive graph.

    Perception -> Context -> [Project Understanding] -> Planning
        -> (Knowledge, iff plan requires) -> Memory -> Reasoning -> Validation
                --fails--> regenerate / re-plan
                                       |
                                    passes
                                       v
                                  Experience -> Solution Document

Project Understanding is a classification step (industry, business domain,
system type, ...), not one of the 8 Octagonal engines — the "8" is a
literal geometric invariant elsewhere (ocif/octagon.py, ocif/layout.py,
core/engine_registry.py's register_cognitive_engines), so this runs as a
plain classifier call rather than a formal CognitiveEngine, the same way
Reasoning calls into SolutionSynthesizer without that being a separate
engine either. Planning and Reasoning consume its output
(context.project_understanding) instead of reading raw request text.

Binding invariants enforced here:
  - No engine skips a downstream engine; Reasoning never emits directly.
  - Knowledge retrieval is optional, reasoning is not.
  - Fail-closed: an invalid solution is regenerated/re-planned, never shipped
    with a disclaimer.
  - Trivial clarifying questions short-circuit BEFORE Reasoning and receive a
    conversational reply — the only permitted non-solution output.
  - The octagonal machinery is internal: callers receive a KernelOutput and
    decide (based on caller-side authorization) whether the CognitiveTrace is
    ever exposed.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field

from core.models.base import OCIFBaseModel, new_uuid
from ocif.engine import CognitiveEngine
from ocif.engines import (
    ContextEngine,
    ExperienceEngine,
    KnowledgeEngine,
    MemoryEngine,
    PerceptionEngine,
    PlanningEngine,
    EngineeringIntelligenceEngine,
    ValidationEngine,
)
from ocif.engines.project_understanding import ProjectUnderstandingEngine
from ocif.frames import (
    CognitiveContext,
    CognitiveTrace,
    EngineStatus,
)

logger = logging.getLogger("AxiomOCIF.Kernel")

_MAX_RECOVERY_ATTEMPTS = 2


class KernelOutput(OCIFBaseModel):
    """Result envelope returned to callers. Callers gate trace exposure."""
    solution_id: str = Field(default_factory=new_uuid)
    conversation_id: str = ""
    correlation_id: str = ""
    is_conversational: bool = False
    conversational_reply: str = ""
    solution_markdown: str = ""
    solution_json: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Dict[str, str]] = Field(default_factory=list)
    confidence: float = 0.0
    trace: Optional[CognitiveTrace] = None
    # Real inference usage for metering (0 on the deterministic synthesizer path).
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    provider_used: str = ""
    model_used: str = ""
    # Optional local-LLM reasoning stream (user-facing; empty on the pure
    # deterministic path). Scrubbed of internal engine vocabulary by Validation.
    reasoning_thinking: str = ""


class OctagonalKernel:
    """Central orchestrator of the 8-engine cognitive graph."""

    def __init__(
        self,
        perception: Optional[PerceptionEngine] = None,
        context_engine: Optional[ContextEngine] = None,
        project_understanding: Optional[ProjectUnderstandingEngine] = None,
        planning: Optional[PlanningEngine] = None,
        knowledge: Optional[KnowledgeEngine] = None,
        memory: Optional[MemoryEngine] = None,
        reasoning: Optional[EngineeringIntelligenceEngine] = None,
        validation: Optional[ValidationEngine] = None,
        experience: Optional[ExperienceEngine] = None,
    ) -> None:
        self.perception = perception or PerceptionEngine()
        self.context_engine = context_engine or ContextEngine()
        self.project_understanding = project_understanding or ProjectUnderstandingEngine()
        self.planning = planning or PlanningEngine()
        self.knowledge = knowledge or KnowledgeEngine()
        self.memory = memory or MemoryEngine()
        self.reasoning = reasoning or EngineeringIntelligenceEngine()
        self.validation = validation or ValidationEngine()
        self.experience = experience or ExperienceEngine()

    @property
    def engines(self) -> List[CognitiveEngine]:
        return [
            self.perception, self.context_engine, self.planning, self.knowledge,
            self.memory, self.reasoning, self.validation, self.experience,
        ]

    def initialize(self) -> None:
        for engine in self.engines:
            engine.initialize()

    def shutdown(self) -> None:
        for engine in self.engines:
            engine.shutdown()

    async def process(
        self,
        message: str,
        *,
        user_id: str = "anonymous",
        tenant_id: str = "default",
        project: str = "default",
        conversation_id: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> KernelOutput:
        """Runs one request through the octagonal graph (fully deterministic —
        AXIOM's own brain, no external LLM)."""
        context = CognitiveContext(
            user_id=user_id,
            tenant_id=tenant_id,
            project=project,
            conversation_id=conversation_id or new_uuid(),
            task=message,
            metadata={"attachments": attachments or []},
        )

        # 1. Perception (mandatory ingress)
        result = await self.perception.execute(context)
        if result.status == EngineStatus.FAILED:
            return self._conversational(
                context,
                context.perception.rejection_reason
                or "The request could not be accepted as submitted.",
            )

        # 2. Context / intent understanding
        await self.context_engine.execute(context)

        # Trivial clarifications never reach Reasoning (permitted short-circuit).
        if context.context.is_trivial:
            return self._conversational(context, self._trivial_reply(message))

        # Deep project/industry classification — runs once per conversation
        # (cached), before Planning, so Planning/Reasoning consume a real
        # understanding of what the project is instead of raw request text.
        context.project_understanding = await self.project_understanding.classify(context)

        # 3-7. Planning -> Knowledge -> Memory -> Reasoning -> Validation,
        # with bounded fail-closed recovery: regenerate first, then re-plan.
        attempt = 0
        while True:
            await self.planning.execute(context)
            await self.knowledge.execute(context)   # skips itself if not required
            await self.memory.execute(context)
            await self.reasoning.execute(context)
            validation_result = await self.validation.execute(context)

            if context.validation and context.validation.passed:
                break

            attempt += 1
            logger.warning(
                f"Validation failed (attempt {attempt}): {context.validation.issues if context.validation else 'unknown'}"
            )
            if attempt > _MAX_RECOVERY_ATTEMPTS:
                # Fail closed: no invalid solution leaves the kernel.
                return self._conversational(
                    context,
                    "I could not produce a solution that passes internal validation for this "
                    "request. Please add detail about the goal, constraints, or environment and try again.",
                )

        # 8. Experience — the only path to user-facing output.
        await self.experience.execute(context)
        self.memory.persist_outcome(context)

        knowledge_frame = context.knowledge
        citations = [
            {"doc_id": s.doc_id, "title": s.title, "excerpt_ref": s.excerpt[:120]}
            for s in (knowledge_frame.sources if knowledge_frame else [])
        ]

        usage = context.metadata.get("llm_usage", {}) or {}
        reasoning = context.reasoning
        return KernelOutput(
            solution_id=context.reasoning.solution_draft.solution_id,
            conversation_id=context.conversation_id,
            correlation_id=context.correlation_id,
            is_conversational=False,
            solution_markdown=context.execution_state["solution_markdown"],
            solution_json=context.execution_state["solution_json"],
            citations=citations,
            confidence=context.confidence,
            trace=ExperienceEngine.build_trace(context),
            input_tokens=int(usage.get("input", 0) or 0),
            output_tokens=int(usage.get("output", 0) or 0),
            cost_usd=float(usage.get("cost_usd", 0.0) or 0.0),
            provider_used=getattr(reasoning, "provider_used", "") or "",
            model_used=getattr(reasoning, "model_used", "") or "",
            reasoning_thinking=getattr(reasoning, "thinking", "") or "",
        )

    # -- helpers ------------------------------------------------------------

    def _conversational(self, context: CognitiveContext, reply: str) -> KernelOutput:
        return KernelOutput(
            conversation_id=context.conversation_id,
            correlation_id=context.correlation_id,
            is_conversational=True,
            conversational_reply=reply,
            confidence=context.confidence,
            trace=ExperienceEngine.build_trace(context),
        )

    @staticmethod
    def _trivial_reply(message: str) -> str:
        lowered = message.lower()
        if any(k in lowered for k in ("who are you", "what can you do", "help")):
            return (
                "I am AXIOM, an AI Engineering Solution Architecture platform. Describe an "
                "engineering problem, product idea, or AIoT use case — for example, "
                "\"Design an MQTT-based sensor alerting platform for a factory\" — and I will "
                "deliver a complete, implementation-ready solution: architecture, technology "
                "stack, data and API design, security, deployment, testing, roadmap, and risks."
            )
        return (
            "Hello! I turn engineering problems and use cases into complete solution designs. "
            "Describe what you want to build — the more context on goals, scale, and "
            "constraints, the sharper the solution."
        )
