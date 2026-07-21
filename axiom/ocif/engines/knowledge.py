"""
Knowledge Engine (Engine 4) — optional knowledge retrieval and integration.

Executes only when the Plan marks knowledge as required. Retrieval is
delegated to an injected retriever (bridged to the platform's hybrid RAG
service). Fail-soft: on any error or when no retriever is configured, an
honest empty frame is produced — sources are never fabricated.
"""

import inspect
import logging
from typing import Any, Callable, List, Optional

from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    EngineName,
    EngineResult,
    EngineStatus,
    KnowledgeFrame,
    KnowledgeSource,
)

logger = logging.getLogger("AxiomOCIF.Knowledge")

# A retriever takes (query: str, user_id: str) and returns a list of dicts:
# [{"doc_id": ..., "title": ..., "text": ...}, ...]. May be sync or async.
Retriever = Callable[[str, str], Any]


class KnowledgeEngine(CognitiveEngine):
    name = EngineName.KNOWLEDGE

    def __init__(self, retriever: Optional[Retriever] = None) -> None:
        super().__init__()
        self.retriever = retriever

    async def _run(self, context: CognitiveContext) -> EngineResult:
        if not (context.plan and context.plan.required_knowledge):
            context.knowledge = KnowledgeFrame()
            return EngineResult(
                engine=self.name,
                status=EngineStatus.SKIPPED,
                summary="Knowledge retrieval not required by plan.",
            )

        query = context.context.subject if context.context else context.task
        sources: List[KnowledgeSource] = []

        if self.retriever is not None:
            try:
                raw = self.retriever(query, context.user_id)
                if inspect.isawaitable(raw):
                    raw = await raw
                for item in (raw or [])[:8]:
                    sources.append(
                        KnowledgeSource(
                            doc_id=str(item.get("doc_id", "")),
                            title=str(item.get("title", "Untitled source")),
                            excerpt=str(item.get("text", ""))[:500],
                        )
                    )
            except Exception as exc:
                # Fail-soft: retrieval failure never blocks reasoning and
                # never produces invented sources.
                logger.warning(f"Knowledge retrieval failed (fail-soft): {exc}")

        if sources:
            facts = [f"{s.title}: {s.excerpt[:200]}" for s in sources]
            context.knowledge = KnowledgeFrame(
                knowledge_used=True,
                facts=facts,
                sources=sources,
                confidence=min(0.9, 0.5 + 0.05 * len(sources)),
                notes=f"Grounded on {len(sources)} internal knowledge sources.",
            )
        else:
            context.knowledge = KnowledgeFrame(
                knowledge_used=False,
                notes="No relevant knowledge found; solved from engineering reasoning alone.",
            )

        return EngineResult(
            engine=self.name,
            summary=f"Retrieved {len(sources)} sources for grounding.",
            payload={"source_count": len(sources)},
        )
