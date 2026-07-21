"""
OCIF Engine Contract — the uniform interface every cognitive engine satisfies.

    initialize()   # load config, dependencies, connect to event bus
    execute(context: CognitiveContext) -> EngineResult
    validate(result: EngineResult) -> bool
    shutdown()     # release resources, flush state

Engines never call each other directly: they communicate only through the
event bus and the shared CognitiveContext (Master Prompt Part B invariants).

Traces to:
  - Axiom Master Prompt Part B (Engine Contract, binding invariants)
"""

import logging
import time
from abc import ABC, abstractmethod

from core.event_bus import event_bus
from core.models.base import utc_now
from ocif.frames import CognitiveContext, EngineName, EngineResult, EngineStatus

logger = logging.getLogger("AxiomOCIF")


class CognitiveEngine(ABC):
    """
    Abstract base for the 8 Octagonal Cognitive Framework engines.

    Subclasses implement `_run(context)` with their engine logic; the public
    `execute()` wrapper handles timing, event bus publication, and trace
    recording so every engine behaves uniformly.
    """

    name: EngineName

    def __init__(self) -> None:
        self._initialized = False

    def initialize(self) -> None:
        """Loads configuration and dependencies. Idempotent."""
        self._initialized = True

    async def execute(self, context: CognitiveContext) -> EngineResult:
        """Executes the engine against the shared CognitiveContext."""
        if not self._initialized:
            self.initialize()

        started = utc_now()
        t0 = time.perf_counter()
        try:
            result = await self._run(context)
        except Exception as exc:  # engines fail closed, kernel decides recovery
            logger.error(f"Engine '{self.name.value}' failed: {exc}", exc_info=True)
            result = EngineResult(
                engine=self.name,
                status=EngineStatus.FAILED,
                summary=f"Engine failure: {exc}",
            )

        result.started_at = started
        result.completed_at = utc_now()
        result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        # OCIFBaseModel serializes enums to their string values on assignment.
        status_value = getattr(result.status, "value", result.status)

        context.engine_trace.append(result)
        context.workflow_state = f"{self.name.value}:{status_value}"

        await event_bus.publish(
            topic=f"ocif.engine.{self.name.value}.completed",
            key=context.correlation_id,
            payload={
                "engine": self.name.value,
                "status": status_value,
                "summary": result.summary,
                "duration_ms": result.duration_ms,
                "user_id": context.user_id,
                "conversation_id": context.conversation_id,
            },
        )
        return result

    @abstractmethod
    async def _run(self, context: CognitiveContext) -> EngineResult:
        """Engine-specific logic. Reads/writes the CognitiveContext."""
        ...

    def validate(self, result: EngineResult) -> bool:
        """Contract-level sanity check of the engine's own result."""
        return result.status in (EngineStatus.COMPLETED, EngineStatus.SKIPPED)

    def shutdown(self) -> None:
        """Releases resources and flushes state."""
        self._initialized = False
