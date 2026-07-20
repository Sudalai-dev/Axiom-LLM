"""Local-LLM enhancement layer (self-hosted, opt-in).

Verifies the hybrid contract: the deterministic document is ALWAYS produced;
when a local model is available it adds a reasoning ("thinking") stream and
rewrites two narrative sections; when it is disabled/unreachable or returns
junk, the output stays byte-for-byte deterministic. No network — a fake client
stands in for Ollama.
"""

import asyncio
import json

from core.config import LLMConfig
from inference.local_llm import LocalLLMClient, _extract_json_object
from ocif.engines.engineering_intelligence import EngineeringIntelligenceEngine
from ocif.frames import (
    CognitiveContext,
    ContextFrame,
    Plan,
    ProjectUnderstandingFrame,
)


class _FakeLLM:
    """Stands in for LocalLLMClient without touching the network."""

    def __init__(self, obj, avail=True):
        self._obj = obj
        self._avail = avail
        self.config = LLMConfig(enabled=True, model="qwen2.5:3b")

    def available(self):
        return self._avail

    def chat_json(self, system, user, **kw):
        return self._obj

    def chat(self, system, user, **kw):
        return json.dumps(self._obj) if self._obj else None


_TASK = "Design a hospital patient records portal for clinicians."


def _run(engine, task=_TASK):
    ctx = CognitiveContext(task=task, tenant_id="t1", user_id="u1")
    ctx.context = ContextFrame(
        intent="solution_design", entities=["patient", "record"],
        domain_entities=["patient", "record"], actors=["Clinician"], use_cases=[], subject=task,
    )
    ctx.plan = Plan(functional_requirements=[], non_functional_requirements=[])
    ctx.project_understanding = ProjectUnderstandingFrame(industry="healthcare")
    asyncio.run(engine._run(ctx))
    return ctx.reasoning


def test_llm_enhances_prose_and_adds_thinking():
    obj = {
        "thinking": "I weighed a monolith against services; given the PHI scope I favour strong "
                    "tenant isolation and encryption first.",
        "executive_summary": "A clinician-facing patient records portal centred on patient and "
                             "record entities, with encryption-first PHI handling throughout.",
        "recommended_solution": "Adopt a modular service with row-level tenant isolation; patient "
                                "and record data is encrypted at rest and in transit.",
    }
    r = _run(EngineeringIntelligenceEngine(llm_client=_FakeLLM(obj)))
    assert r.thinking.startswith("I weighed")
    assert "patient records portal" in r.solution_draft.executive_summary
    assert r.solution_draft.recommended_solution.startswith("Adopt a modular service")
    assert r.provider_used.startswith("local-llm")


def test_llm_unavailable_stays_deterministic():
    det = _run(EngineeringIntelligenceEngine(llm_client=_FakeLLM({}, avail=False)))
    assert det.thinking == ""
    assert det.provider_used == "internal-synthesizer"
    # A pure-deterministic run (no client wired) must match exactly.
    baseline = _run(EngineeringIntelligenceEngine())
    assert det.solution_draft.executive_summary == baseline.solution_draft.executive_summary
    assert det.solution_draft.recommended_solution == baseline.solution_draft.recommended_solution


def test_llm_junk_output_is_ignored():
    junk = {"thinking": "x", "executive_summary": "short", "recommended_solution": ""}
    r = _run(EngineeringIntelligenceEngine(llm_client=_FakeLLM(junk)))
    baseline = _run(EngineeringIntelligenceEngine(llm_client=_FakeLLM({}, avail=False)))
    assert r.thinking == ""                       # too short → rejected
    assert r.provider_used == "internal-synthesizer"
    assert r.solution_draft.executive_summary == baseline.solution_draft.executive_summary


def test_llm_structured_fields_never_touched_by_enhancement():
    """Even with a fully-formed LLM response, structured content stays from the
    deterministic engine — the LLM can't fabricate architecture."""
    obj = {
        "thinking": "Reasoning about the data model and encryption posture for this portal.",
        "executive_summary": "An enhanced, request-specific executive summary for the portal.",
        "recommended_solution": "An enhanced, request-specific recommended solution for the portal.",
    }
    enhanced = _run(EngineeringIntelligenceEngine(llm_client=_FakeLLM(obj)))
    baseline = _run(EngineeringIntelligenceEngine(llm_client=_FakeLLM({}, avail=False)))
    assert enhanced.solution_draft.technology_stack == baseline.solution_draft.technology_stack
    assert enhanced.solution_draft.database_design == baseline.solution_draft.database_design
    assert enhanced.solution_draft.architecture_overview == baseline.solution_draft.architecture_overview


def test_client_disabled_is_unavailable_and_silent():
    c = LocalLLMClient(LLMConfig(enabled=False))
    assert c.available() is False
    assert c.chat("system", "user") is None


def test_extract_json_object_tolerates_fences_and_noise():
    assert _extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json_object('here it is {"a": 2} trailing prose') == {"a": 2}
    assert _extract_json_object('no json at all') is None
