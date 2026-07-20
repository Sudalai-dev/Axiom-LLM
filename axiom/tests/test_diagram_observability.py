"""Phase 2 — per-layer diagram-generation observability.

Every layer's diagram carries a usage record (provider, latency, node/edge
counts, mermaid validity, status, discard reason). Failures are never swallowed:
an invalid diagram is recorded with a discard reason and dropped to EMPTY.
"""

import asyncio

from ocif import OctagonalKernel
from ocif.blueprint_config import BLUEPRINT_VIEW_KEYS
from ocif.diagram_brain import (
    DIAGRAM_DISCARD_REASONS,
    DiagramBrain,
    validate_mermaid,
)
from ocif.engines.engineering_intelligence import SolutionSynthesizer
from ocif.frames import ContextFrame, KnowledgeFrame, Plan, ProjectUnderstandingFrame

ENGINEERING_REQUEST = "Design an MQTT-based industrial sensor alerting platform for a factory"


def _doc(entities=("Sensor", "Gateway", "Alert")):
    synth = SolutionSynthesizer()
    frame = ContextFrame(
        intent="solution_design", entities=list(entities), domain_entities=list(entities),
        actors=["Operator"], use_cases=[],
    )
    return synth.synthesize(
        frame, Plan(functional_requirements=[], non_functional_requirements=[]),
        KnowledgeFrame(), None, ProjectUnderstandingFrame(industry="industrial_iot"),
    )


def test_validate_mermaid_rejects_broken_syntax():
    assert validate_mermaid("flowchart LR\n    a[\"X\"] --> b[\"Y\"]") is True
    assert validate_mermaid("") is False
    assert validate_mermaid("not a diagram") is False          # no header
    assert validate_mermaid("flowchart LR") is False           # header only, no body
    assert validate_mermaid('flowchart LR\n    a["X --> b') is False  # unbalanced


def test_diagram_usage_populated_per_layer():
    blueprint, usage = DiagramBrain().generate(_doc())
    assert len(usage) == len(BLUEPRINT_VIEW_KEYS)
    assert [u["view"] for u in usage] == BLUEPRINT_VIEW_KEYS
    for u in usage:
        assert u["provider"] == "internal-builder"
        assert u["latency_ms"] >= 0
        assert "node_count" in u and "edge_count" in u
        assert isinstance(u["mermaid_valid"], bool)
        assert u["status"] in ("RENDERED", "EMPTY")
        assert u["discard_reason"] is None or u["discard_reason"] in DIAGRAM_DISCARD_REASONS


def test_invalid_diagram_is_recorded_as_discard_not_shipped(monkeypatch):
    """If a builder ever yields invalid mermaid, the usage records the discard
    reason and the diagram drops to EMPTY rather than shipping broken syntax."""
    import ocif.diagram_brain as db
    from ocif.frames import Blueprint, Diagram

    def _bad_blueprint(doc):
        return Blueprint(diagrams=[
            Diagram(view=v, label=v.title(), diagram_type="flowchart",
                    code="flowchart LR\n    a[\"unbalanced --> b", nodes=["a"], status="RENDERED")
            for v in BLUEPRINT_VIEW_KEYS
        ])

    monkeypatch.setattr(db, "build_blueprint", _bad_blueprint)
    blueprint, usage = DiagramBrain().generate(_doc())
    assert all(u["discard_reason"] == "invalid_structure" for u in usage)
    assert all(d.status == "EMPTY" for d in blueprint.diagrams)


def test_kernel_surfaces_blueprint_and_diagram_usage_in_trace():
    kernel = OctagonalKernel()
    out = asyncio.run(kernel.process(ENGINEERING_REQUEST, tenant_id="t1", user_id="u1"))
    assert not out.is_conversational
    # Blueprint on the output (primary), usage on the output + the admin trace.
    assert out.blueprint is not None
    assert len(out.blueprint["diagrams"]) == len(BLUEPRINT_VIEW_KEYS)
    assert len(out.diagram_usage) == len(BLUEPRINT_VIEW_KEYS)
    assert len(out.trace.diagram_usage) == len(BLUEPRINT_VIEW_KEYS)
