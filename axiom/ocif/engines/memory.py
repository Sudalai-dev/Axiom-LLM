"""
Memory Engine (Engine 5) — supplies and updates the memory types of Part D.

Maintains an in-process store keyed by (tenant, project, conversation) for
same-process recall (conversation turns, project notes, reasoning/decision
registries), and delegates the durable "has this been solved successfully
before" and explicit user-feedback lookups to a persistent LearningStore
(axiom.memory.learning_store) so they survive process restarts — this is
what lets Axiom "learn" from past conversations and use cases across
sessions, not just within one.
"""

from collections import defaultdict
from typing import Dict, List, Optional

from core.models.base import new_uuid
from memory.learning_store import LearningStore
from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    EngineName,
    EngineResult,
    MemoryFrame,
)

_MAX_TURNS = 20
_MAX_ENTRIES = 50


class MemoryEngine(CognitiveEngine):
    name = EngineName.MEMORY

    def __init__(self, learning_store: Optional[LearningStore] = None) -> None:
        super().__init__()
        self._conversations: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        self._project_memory: Dict[str, List[str]] = defaultdict(list)
        self._reasoning_memory: Dict[str, List[str]] = defaultdict(list)
        self._decision_memory: Dict[str, List[str]] = defaultdict(list)
        self._learning_memory: Dict[str, List[str]] = defaultdict(list)
        self._feedback_memory: Dict[str, List[str]] = defaultdict(list)
        self.learning_store = learning_store or LearningStore()

    def _conv_key(self, context: CognitiveContext) -> str:
        return f"{context.tenant_id}:{context.conversation_id}"

    def _proj_key(self, context: CognitiveContext) -> str:
        return f"{context.tenant_id}:{context.project}"

    async def _run(self, context: CognitiveContext) -> EngineResult:
        conv_key = self._conv_key(context)
        proj_key = self._proj_key(context)

        self._conversations[conv_key].append({"role": "user", "content": context.task})
        self._conversations[conv_key] = self._conversations[conv_key][-_MAX_TURNS:]

        # Durable recall: has anything like this been solved before, across
        # this process's lifetime and every prior run of the platform?
        similar = self.learning_store.find_similar(
            tenant_id=context.tenant_id,
            project=context.project,
            intent=context.intent,
            entities=context.entities,
        )
        learning_entries = [
            f"Prior validated solution '{rec.solution_title}' for a similar "
            f"{rec.intent} request (confidence {rec.confidence:.2f}); "
            f"trade-offs then: {'; '.join(rec.tradeoffs[:2]) or 'none recorded'}."
            for rec in similar
        ]
        feedback_notes = self.learning_store.recent_feedback(context.tenant_id, context.project)
        feedback_entries = [f"User rated a prior response {n.rating:+d}: {n.note}" for n in feedback_notes if n.note]

        # Structured recall (Phase 6): the same recall as `learning`/`feedback`,
        # but keeping each record's title/entities/trade-offs/confidence so the
        # synthesizer can reuse-and-adapt the prior design and let feedback shift
        # the next solution — genuine influence, not a cosmetic sentence.
        recalled = [
            {
                "title": rec.solution_title,
                "intent": rec.intent,
                "confidence": rec.confidence,
                "entities": list(rec.entities),
                "tradeoffs": list(rec.tradeoffs),
                # Phase 6: per-layer diagram STRUCTURE of the prior Blueprint, so
                # the diagram core can reuse-and-adapt it (re-grounded to THIS
                # request) instead of regenerating every layer from scratch.
                "diagrams": list(rec.diagrams),
            }
            for rec in similar
        ]
        feedback_signals = [
            {"rating": n.rating, "note": n.note} for n in feedback_notes if n.note
        ]

        context.memory = MemoryFrame(
            working={
                "correlation_id": context.correlation_id,
                "intent": context.intent,
                "entities": context.entities,
            },
            conversation=list(self._conversations[conv_key]),
            project=list(self._project_memory[proj_key][-_MAX_ENTRIES:]),
            reasoning=list(self._reasoning_memory[proj_key][-_MAX_ENTRIES:]),
            decisions=list(self._decision_memory[proj_key][-_MAX_ENTRIES:]),
            learning=(learning_entries + list(self._learning_memory[proj_key]))[-_MAX_ENTRIES:],
            feedback=(feedback_entries + list(self._feedback_memory[proj_key]))[-_MAX_ENTRIES:],
            recalled=recalled,
            feedback_signals=feedback_signals,
        )

        prior = len(context.memory.reasoning) + len(context.memory.decisions)
        return EngineResult(
            engine=self.name,
            summary=(
                f"Loaded memory: {len(context.memory.conversation)} turns, "
                f"{prior} prior reasoning/decision entries, "
                f"{len(similar)} similar past solutions recalled."
            ),
            payload={
                "conversation_turns": len(context.memory.conversation),
                "prior_entries": prior,
                "similar_solutions_recalled": len(similar),
            },
        )

    # -- post-run persistence (called by the kernel after validation passes) --

    def persist_outcome(self, context: CognitiveContext) -> None:
        """Records the validated outcome into reasoning/decision memory, both
        in-process (fast same-session recall) and durably (learning store)."""
        proj_key = self._proj_key(context)
        conv_key = self._conv_key(context)
        if context.reasoning:
            title = context.reasoning.solution_draft.title
            self._reasoning_memory[proj_key].append(
                f"[{context.intent}] {title}: {context.reasoning.rationale[:200]}"
            )
            self._decision_memory[proj_key].append(
                f"{title} — confidence {context.reasoning.confidence:.2f}; "
                f"trade-offs: {'; '.join(context.reasoning.tradeoffs[:2])}"
            )
            self._conversations[conv_key].append(
                {"role": "assistant", "content": f"Delivered solution: {title}"}
            )
            # Phase 6: persist the validated Blueprint's per-layer structure
            # (view + grounded nodes) so a future similar request can recall it.
            # Only RENDERED layers with real nodes are worth recalling.
            blueprint = (context.metadata or {}).get("blueprint") or {}
            recall_diagrams = [
                {
                    "view": d.get("view"),
                    "nodes": list(d.get("nodes") or []),
                    "diagram_type": d.get("diagram_type"),
                }
                for d in (blueprint.get("diagrams") or [])
                if d.get("status") == "RENDERED" and d.get("nodes")
            ]
            self.learning_store.record(
                record_id=new_uuid(),
                tenant_id=context.tenant_id,
                project=context.project,
                intent=context.intent,
                entities=context.entities,
                subject=context.context.subject if context.context else context.task,
                solution_title=title,
                confidence=context.reasoning.confidence,
                tradeoffs=context.reasoning.tradeoffs,
                diagrams=recall_diagrams,
            )

    def record_feedback(self, tenant_id: str, project: str, rating: int, note: str) -> None:
        self._feedback_memory[f"{tenant_id}:{project}"].append(note)
        self.learning_store.record_feedback(
            note_id=new_uuid(), tenant_id=tenant_id, project=project, rating=rating, note=note
        )
