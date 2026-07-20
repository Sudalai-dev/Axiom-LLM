"""Phase 1 — the diagrams-only Blueprint contract.

AXIOM's primary output is a Blueprint of exactly one diagram per OCIF layer,
built on the REAL engine layer set (Perception..Experience), with every node
grounded in the request's entities. The prose SolutionDocument is retained but
behind a config flag.
"""

from core.config import OutputConfig, settings
from ocif.blueprint import build_blueprint
from ocif.blueprint_config import (
    AXIOM_DIAGRAM_TYPES,
    BLUEPRINT_VIEW_COUNT,
    BLUEPRINT_VIEW_KEYS,
)
from ocif.blueprint_pipeline import build_solution_response
from ocif.engines.engineering_intelligence import SolutionSynthesizer
from ocif.frames import (
    Blueprint,
    ContextFrame,
    EngineName,
    KnowledgeFrame,
    Plan,
    ProjectUnderstandingFrame,
)

_ENGINE_VALUES = {e.value for e in EngineName}


def _doc(entities, actors=("User",), industry="generic_software"):
    synth = SolutionSynthesizer()
    frame = ContextFrame(
        intent="solution_design", entities=list(entities), domain_entities=list(entities),
        actors=list(actors), use_cases=[],
    )
    return synth.synthesize(
        frame, Plan(functional_requirements=[], non_functional_requirements=[]),
        KnowledgeFrame(), None, ProjectUnderstandingFrame(industry=industry),
    )


def test_config_views_are_real_ocif_layers():
    # The view set is locked to the real engines, in a valid count, with known types.
    assert BLUEPRINT_VIEW_COUNT == 8
    assert set(BLUEPRINT_VIEW_KEYS) <= _ENGINE_VALUES
    assert len(set(BLUEPRINT_VIEW_KEYS)) == 8
    # The fabricated directive names must NOT be present.
    for bogus in ("capture", "normalization", "enrichment", "synthesis", "cognition", "prescription"):
        assert bogus not in BLUEPRINT_VIEW_KEYS


def test_blueprint_has_exactly_one_diagram_per_layer():
    bp = build_blueprint(_doc(["Patient", "Bed", "Ward"], actors=["Clinician"], industry="healthcare"))
    assert isinstance(bp, Blueprint)
    assert [d.view for d in bp.diagrams] == BLUEPRINT_VIEW_KEYS  # exactly 8, in order
    for d in bp.diagrams:
        assert d.diagram_type in AXIOM_DIAGRAM_TYPES
        assert d.provider_used == "internal-builder"
        assert d.grounded is True
        assert d.status in ("RENDERED", "EMPTY")


def test_blueprint_nodes_are_grounded_in_request_entities():
    bp = build_blueprint(_doc(["Patient", "Bed", "Ward", "Clinician"], actors=["Clinician"], industry="healthcare"))
    all_nodes = {n.lower() for d in bp.diagrams for n in d.nodes}
    # Every node traces to a real request entity/actor — nothing invented.
    grounded_pool = {"patient", "bed", "ward", "clinician"}
    assert all_nodes <= grounded_pool
    # And at least one diagram actually surfaced the request's entities.
    assert all_nodes  # non-empty for a concrete request


def test_blueprint_has_no_prose_fields():
    bp = build_blueprint(_doc(["Widget"]))
    # The Blueprint contract carries ONLY diagrams — no narrative attributes.
    assert set(bp.model_dump().keys()) == {"diagrams"}


def test_two_unrelated_requests_produce_structurally_different_blueprints():
    hospital = build_blueprint(_doc(["Patient", "Bed", "Ward"], actors=["Clinician"], industry="healthcare"))
    library = build_blueprint(_doc(["Book", "Member", "Loan"], actors=["Librarian"], industry="generic_software"))
    h = {d.view: d.code for d in hospital.diagrams}
    l = {d.view: d.code for d in library.diagrams}
    # The data-model (knowledge/ER) view must differ structurally between them.
    assert h["knowledge"] != l["knowledge"]


def test_pipeline_package_includes_blueprint():
    package = build_solution_response(_doc(["Patient", "Bed"], industry="healthcare"), markdown="# ignored")
    assert "blueprint" in package
    assert len(package["blueprint"]["diagrams"]) == 8


def test_prose_disabled_by_default():
    # Diagrams-only is the default posture; prose is opt-in.
    assert settings.output.prose_enabled is False
    assert OutputConfig().prose_enabled is False
