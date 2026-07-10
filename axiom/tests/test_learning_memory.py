"""Persistent learning memory: LearningStore durability + Memory Engine recall."""

import asyncio

from memory.learning_store import LearningStore
from ocif.engines.memory import MemoryEngine
from ocif.engines.perception import PerceptionEngine
from ocif.engines.context import ContextEngine
from ocif.engines.planning import PlanningEngine
from ocif.engines.reasoning import ReasoningEngine
from ocif.engines.validation import ValidationEngine
from ocif.frames import CognitiveContext


def run(coro):
    return asyncio.run(coro)


def make_store(tmp_path):
    return LearningStore(db_path=str(tmp_path / "learning_memory.db"))


def test_learning_store_persists_and_recalls_similar_records(tmp_path):
    store = make_store(tmp_path)

    store.record(
        record_id="rec-1", tenant_id="t1", project="p1", intent="aiot_engineering",
        entities=["MQTT", "PostgreSQL"], subject="Design a sensor alert platform",
        solution_title="Edge-to-Cloud Event-Driven AIoT Architecture",
        confidence=0.81, tradeoffs=["Chose MQTT over raw sockets"],
    )

    # A durable store must survive being re-opened against the same file.
    reopened = LearningStore(db_path=store.db_path)
    similar = reopened.find_similar(
        tenant_id="t1", project="p1", intent="aiot_engineering", entities=["MQTT"]
    )
    assert len(similar) == 1
    assert similar[0].solution_title == "Edge-to-Cloud Event-Driven AIoT Architecture"
    assert reopened.count(tenant_id="t1") == 1


def test_learning_store_finds_nothing_for_unrelated_entities(tmp_path):
    store = make_store(tmp_path)
    store.record(
        record_id="rec-1", tenant_id="t1", project="p1", intent="aiot_engineering",
        entities=["MQTT"], subject="x", solution_title="Y", confidence=0.7, tradeoffs=[],
    )
    similar = store.find_similar(
        tenant_id="t1", project="p1", intent="general_engineering", entities=["React"]
    )
    assert similar == []


def test_learning_store_records_and_returns_feedback(tmp_path):
    store = make_store(tmp_path)
    store.record_feedback(note_id="fb-1", tenant_id="t1", project="p1", rating=1, note="Great answer")
    notes = store.recent_feedback(tenant_id="t1", project="p1")
    assert len(notes) == 1
    assert notes[0].rating == 1
    assert "Great answer" in notes[0].note


def _run_engines_through_reasoning(context: CognitiveContext, memory_engine: MemoryEngine):
    run(PerceptionEngine().execute(context))
    run(ContextEngine().execute(context))
    run(PlanningEngine().execute(context))
    run(memory_engine.execute(context))
    run(ReasoningEngine().execute(context))
    run(ValidationEngine().execute(context))


def test_memory_engine_recalls_persisted_solution_across_instances(tmp_path):
    """A brand-new MemoryEngine (simulating a process restart) must still
    recall a solution validated by a *different* MemoryEngine instance,
    because recall is backed by the durable LearningStore, not in-process state."""
    store = make_store(tmp_path)

    first_memory = MemoryEngine(learning_store=store)
    ctx1 = CognitiveContext(
        task="Design an MQTT-based industrial sensor alerting platform for a factory",
        tenant_id="t1", project="p1",
    )
    _run_engines_through_reasoning(ctx1, first_memory)
    assert ctx1.validation.passed
    first_memory.persist_outcome(ctx1)
    assert store.count(tenant_id="t1") == 1

    # Simulate a fresh process: new MemoryEngine, same durable store.
    second_memory = MemoryEngine(learning_store=store)
    ctx2 = CognitiveContext(
        task="Design an MQTT-based alerting system for warehouse sensors",
        tenant_id="t1", project="p1",
    )
    run(PerceptionEngine().execute(ctx2))
    run(ContextEngine().execute(ctx2))
    run(PlanningEngine().execute(ctx2))
    result = run(second_memory.execute(ctx2))

    assert result.payload["similar_solutions_recalled"] >= 1
    assert any("Prior validated solution" in entry for entry in ctx2.memory.learning)


def test_reasoning_tolerates_missing_project_understanding(tmp_path):
    """This file's manual engine chain (_run_engines_through_reasoning) never
    calls ProjectUnderstandingEngine, so context.project_understanding stays
    None — Reasoning/SolutionSynthesizer/_build_prompt must all degrade
    gracefully to today's generic behavior rather than raising."""
    store = make_store(tmp_path)
    memory = MemoryEngine(learning_store=store)
    ctx = CognitiveContext(task="Design a simple internal tool", tenant_id="t9", project="p9")
    _run_engines_through_reasoning(ctx, memory)

    assert ctx.project_understanding is None
    assert ctx.validation is not None and ctx.validation.passed
    assert ctx.reasoning.solution_draft.title


def test_reasoning_confidence_increases_with_learning_recall(tmp_path):
    """Confidence should be at least as high when relevant learning memory
    is present, reflecting that Axiom has solved something similar before."""
    from ocif.frames import ContextFrame, KnowledgeFrame, Plan

    reasoning = ReasoningEngine()
    frame = ContextFrame(intent="aiot_engineering", entities=["MQTT"], subject="x")
    plan = Plan()
    knowledge = KnowledgeFrame()

    base = reasoning._score_confidence(frame, knowledge, "internal-synthesizer", learning=None)
    boosted = reasoning._score_confidence(
        frame, knowledge, "internal-synthesizer",
        learning=["Prior validated solution 'X' for a similar aiot_engineering request (confidence 0.80)."],
    )
    assert boosted > base
