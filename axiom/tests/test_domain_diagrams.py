"""Per-domain engineering diagrams: extracted from already-embedded mermaid
content or generated deterministically from already-structured fields —
never fabricated, never engine-execution vocabulary."""

from ocif.frames import RoadmapPhase, Risk, SolutionDocument, TechChoice
from ocif.solution_mapping import SolutionMappingEngine


def make_rich_document() -> SolutionDocument:
    return SolutionDocument(
        title="Rich Solution",
        actors=["Plant Operator", "System Administrator"],
        technology_stack=[TechChoice(layer="Backend", choice="FastAPI", rationale="Async-first")],
        implementation_roadmap=[
            RoadmapPhase(phase="Phase 1 — Foundation (weeks 1-2)", items=["Setup"]),
            RoadmapPhase(phase="Phase 2 — Core (weeks 3-4)", items=["Build"]),
        ],
        risk_assessment=[Risk(risk="Load spikes", likelihood="medium", impact="high", mitigation="Autoscale")],
        architecture_overview="Text.\n```mermaid\nflowchart LR\n A-->B\n```",
        database_design="Text.\n```mermaid\nerDiagram\n A||--o{B: has\n```",
        deployment_architecture="Text.\n```mermaid\nflowchart TB\n X-->Y\n```",
        workflow="Text.\n```mermaid\nsequenceDiagram\n A->>B: msg\n```",
    )


def test_perception_gets_system_context_diagram_from_actors_and_stack():
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "perception")
    assert len(node.diagrams) == 1
    assert node.diagrams[0].title == "System Context"
    assert "Plant Operator" in node.diagrams[0].content
    assert "FastAPI" in node.diagrams[0].content


def test_context_gets_workflow_diagram_extracted():
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "context")
    assert len(node.diagrams) == 1
    assert "sequenceDiagram" in node.diagrams[0].content


def test_planning_gets_timeline_diagram_from_roadmap():
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "planning")
    assert len(node.diagrams) == 1
    diagram = node.diagrams[0].content
    assert "Phase 1" in diagram
    assert "-->" in diagram


def test_knowledge_gets_dependency_diagram_from_tech_stack():
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "knowledge")
    assert len(node.diagrams) == 1
    assert "FastAPI" in node.diagrams[0].content


def test_memory_gets_both_architecture_and_er_diagrams_extracted():
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "memory")
    assert len(node.diagrams) == 2
    contents = [d.content for d in node.diagrams]
    assert any("flowchart" in c for c in contents)
    assert any("erDiagram" in c for c in contents)


def test_validation_gets_risk_quadrant_diagram():
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "validation")
    assert len(node.diagrams) == 1
    assert "quadrantChart" in node.diagrams[0].content
    assert "Load spikes" in node.diagrams[0].content


def test_experience_gets_deployment_diagram_extracted():
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "experience")
    assert len(node.diagrams) == 1
    assert "flowchart TB" in node.diagrams[0].content


def test_no_diagram_is_fabricated_when_source_content_is_absent():
    """An empty SolutionDocument must never produce a diagram claiming to
    represent architecture/ER/deployment content that doesn't exist."""
    empty = SolutionDocument(title="Empty")
    model = SolutionMappingEngine().map(empty)
    for node in model.nodes:
        assert node.diagrams == [], f"{node.domain} fabricated a diagram with no source content"


def test_reasoning_node_has_no_synthetic_diagram_by_design():
    """Reasoning's current fields (recommended_solution/api_design/final
    recommendations) carry no embedded diagrams — verify we don't fake one."""
    model = SolutionMappingEngine().map(make_rich_document())
    node = next(n for n in model.nodes if n.domain == "reasoning")
    assert node.diagrams == []
