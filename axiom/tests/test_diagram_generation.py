"""Phase 4 — diagram generation core (qwen structure → deterministic mermaid).

The model proposes diagram STRUCTURE as JSON; the emitter renders valid mermaid
deterministically; a guard rejects any ungrounded node and the layer falls back
to the deterministic builder. Nothing ships raw from the model.
"""

import json

from core.config import LLMConfig
from ocif.blueprint_config import BLUEPRINT_VIEW_KEYS
from ocif.diagram_brain import DiagramBrain, validate_mermaid
from ocif.entity_typing import build_typed_entities, derive_relationships
from ocif.engines.engineering_intelligence import SolutionSynthesizer
from ocif.frames import ContextFrame, KnowledgeFrame, Plan, ProjectUnderstandingFrame
from ocif.mermaid_emit import emit_mermaid


class _FakeDiagramLLM:
    def __init__(self, struct, model="axiom-qwen2.5:3b"):
        self._struct = struct
        self.config = LLMConfig(enabled=True, model=model)

    def available(self):
        return True

    def chat_json(self, system, user, **kw):
        return self._struct

    def chat(self, system, user, **kw):
        return json.dumps(self._struct)


def _doc(entities=("Patient", "Record"), actors=("Clinician",), industry="healthcare"):
    te = build_typed_entities(list(entities), list(actors))
    rel = derive_relationships(te)
    frame = ContextFrame(
        intent="solution_design", entities=list(entities), domain_entities=list(entities),
        typed_entities=te, relationships=rel, actors=list(actors), use_cases=[],
    )
    return SolutionSynthesizer().synthesize(
        frame, Plan(functional_requirements=[], non_functional_requirements=[]),
        KnowledgeFrame(), None, ProjectUnderstandingFrame(industry=industry),
    )


# -- emitter -----------------------------------------------------------------

def test_emitter_produces_valid_mermaid_for_every_type():
    nodes = ["Patient", "Record"]
    edges = [{"source": "Patient", "target": "Record", "type": "stores"}]
    for dtype in ("flowchart", "sequence", "state", "class", "er", "mindmap"):
        code = emit_mermaid(dtype, nodes, edges)
        assert validate_mermaid(code), f"{dtype} produced invalid mermaid:\n{code}"
    assert emit_mermaid("flowchart", [], []) == ""       # no nodes → empty
    assert emit_mermaid("unknown_type", nodes, edges) == ""


def test_emitter_handles_digit_leading_and_symbol_names():
    """class/ER ids must never start with a digit or be empty — both are invalid
    mermaid identifiers. Names like '3D Scanner' or '###' must still emit valid
    diagrams."""
    nodes = ["3D Scanner", "###", "Patient"]
    edges = [{"source": "3D Scanner", "target": "Patient", "type": "uses"}]
    for dtype in ("class", "er"):
        code = emit_mermaid(dtype, nodes, edges)
        assert validate_mermaid(code), f"{dtype} produced invalid mermaid:\n{code}"


# -- generation core ---------------------------------------------------------

def test_grounded_model_structure_is_used_and_valid():
    struct = {
        "nodes": [{"id": "Patient", "type": "data_object"}, {"id": "Clinician", "type": "actor"}],
        "edges": [{"source": "Clinician", "target": "Patient", "type": "uses"}],
    }
    bp, usage = DiagramBrain(llm_client=_FakeDiagramLLM(struct)).generate(_doc())
    assert len(bp.diagrams) == len(BLUEPRINT_VIEW_KEYS)
    # The model-grounded diagrams are used (provider local-llm) and valid.
    assert any(d.provider_used.startswith("local-llm") for d in bp.diagrams)
    for d in bp.diagrams:
        if d.status == "RENDERED":
            assert validate_mermaid(d.code)
            for n in d.nodes:                      # every node grounded
                assert n.lower() in {"patient", "clinician", "record"}
    assert any(u["provider"].startswith("local-llm") for u in usage)


def test_ungrounded_node_is_rejected_and_falls_back():
    struct = {"nodes": [{"id": "Patient"}, {"id": "Hacker"}], "edges": []}  # Hacker not an entity
    bp, usage = DiagramBrain(llm_client=_FakeDiagramLLM(struct)).generate(_doc())
    # Strict guard → every layer rejects and falls back to the deterministic builder.
    assert all(d.provider_used == "internal-builder" for d in bp.diagrams)
    assert any(u["discard_reason"] == "ungrounded_node" for u in usage)


def test_no_llm_degrades_to_eight_deterministic_diagrams():
    bp, usage = DiagramBrain(llm_client=None).generate(_doc())
    assert len(bp.diagrams) == 8
    assert all(d.provider_used == "internal-builder" for d in bp.diagrams)


def test_recalled_structure_is_reused_and_reground_without_llm():
    """Phase 6: a prior validated diagram whose nodes re-ground in THIS request
    is reused deterministically (provider 'recall'), with no model call."""
    recalled = [{
        "title": "Patient Records Portal",
        "diagrams": [{"view": "knowledge", "nodes": ["Patient", "Record"], "diagram_type": "er"}],
    }]
    bp, usage = DiagramBrain(llm_client=None).generate(
        _doc(entities=["Patient", "Record"], actors=["Clinician"]), recalled=recalled
    )
    knowledge = next(d for d in bp.diagrams if d.view == "knowledge")
    assert knowledge.provider_used == "recall"
    assert knowledge.status == "RENDERED"
    assert {n.lower() for n in knowledge.nodes} <= {"patient", "record"}
    assert validate_mermaid(knowledge.code)
    assert any(u["provider"] == "recall" for u in usage)


def test_recalled_structure_rejected_when_nodes_dont_reground():
    """A recalled diagram whose nodes are NOT entities of the current request
    must be rejected (no cross-request leakage) — the layer falls back to the
    deterministic builder, never 'recall'."""
    recalled = [{
        "title": "Library Catalog",
        "diagrams": [{"view": "knowledge", "nodes": ["Book", "Member"], "diagram_type": "er"}],
    }]
    bp, _ = DiagramBrain(llm_client=None).generate(
        _doc(entities=["Patient", "Record"], actors=["Clinician"]), recalled=recalled
    )
    assert all(d.provider_used != "recall" for d in bp.diagrams)
    all_nodes = {n.lower() for d in bp.diagrams for n in d.nodes}
    assert "book" not in all_nodes and "member" not in all_nodes


def test_model_diagrams_are_grounded_only_in_request_entities():
    """A node the model returns that isn't in THIS request's entities can never
    appear — cross-request leakage is impossible via the guard."""
    struct = {
        "nodes": [{"id": "Book", "type": "data_object"}],  # from a DIFFERENT domain
        "edges": [],
    }
    bp, _ = DiagramBrain(llm_client=_FakeDiagramLLM(struct)).generate(
        _doc(entities=["Patient", "Record"], actors=["Clinician"])
    )
    all_nodes = {n.lower() for d in bp.diagrams for n in d.nodes}
    assert "book" not in all_nodes  # ungrounded → rejected everywhere
