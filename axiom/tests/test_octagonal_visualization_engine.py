"""Octagonal Visualization Engine: renders an OctagonalModel as SVG, Mermaid,
PlantUML, a generic JSON graph, and a ReactFlow-compatible graph. Nodes must
represent solution domains, never AI engines or execution status."""

from ocif.domains import SolutionDomain
from ocif.frames import RoadmapPhase, SolutionDocument
from ocif.solution_mapping import SolutionMappingEngine
from ocif.visualization import OctagonalVisualizationEngine


def make_model():
    doc = SolutionDocument(
        title="Test Solution",
        implementation_roadmap=[RoadmapPhase(phase="Phase 1", items=["Task A"])],
    )
    return SolutionMappingEngine().map(doc)


def test_generate_returns_all_five_formats():
    bundle = OctagonalVisualizationEngine().generate(make_model())
    assert set(bundle.keys()) == {"svg", "mermaid", "plantuml", "json_graph", "reactflow"}


def test_svg_has_eight_interactive_nodes_with_drilldown_hooks():
    svg = OctagonalVisualizationEngine().build_svg(make_model())
    assert svg.startswith("<svg")
    assert svg.count('class="solution-node"') == 8
    assert svg.count('data-domain="') == 8
    for domain in SolutionDomain:
        assert f'data-domain="{domain.value}"' in svg
    # No engine execution vocabulary anywhere in the solution SVG.
    lowered = svg.lower()
    for leaked in ("completed", "skipped", "failed", "duration", "confidence"):
        assert leaked not in lowered


def test_mermaid_is_a_flowchart_with_labeled_edges():
    mermaid = OctagonalVisualizationEngine().build_mermaid(make_model())
    assert mermaid.startswith("flowchart")
    for domain in SolutionDomain:
        assert domain.value in mermaid
    assert "-->|" in mermaid


def test_plantuml_declares_all_domains_and_relationships():
    plantuml = OctagonalVisualizationEngine().build_plantuml(make_model())
    assert plantuml.startswith("@startuml")
    assert plantuml.rstrip().endswith("@enduml")
    for domain in SolutionDomain:
        assert f'as {domain.value}' in plantuml
    assert "-->" in plantuml


def test_json_graph_model_shape():
    graph = OctagonalVisualizationEngine().build_json_graph(make_model())
    assert len(graph["nodes"]) == 8
    assert all({"id", "label", "artifact_count", "related_domains"} <= set(n.keys()) for n in graph["nodes"])
    assert graph["edges"]
    assert all({"source", "target", "relationship"} <= set(e.keys()) for e in graph["edges"])


def test_reactflow_graph_shape():
    rf = OctagonalVisualizationEngine().build_reactflow(make_model())
    assert len(rf["nodes"]) == 8
    for node in rf["nodes"]:
        assert "position" in node and {"x", "y"} <= set(node["position"].keys())
        assert "data" in node and "label" in node["data"]
    for edge in rf["edges"]:
        assert {"id", "source", "target", "label"} <= set(edge.keys())


def test_nodes_represent_domains_not_engines():
    """Explicit mission requirement: 'Each of the eight nodes represents a
    solution domain, not an AI engine.' Verify no engine-trace vocabulary
    (status/duration/timeline execution words) appears in any format."""
    bundle = OctagonalVisualizationEngine().generate(make_model())
    combined = " ".join([
        bundle["svg"], bundle["mermaid"], bundle["plantuml"], str(bundle["json_graph"]), str(bundle["reactflow"]),
    ]).lower()
    for leaked in ("engine", "cognitive", "reasoning trace", "chain-of-thought", "chain of thought"):
        assert leaked not in combined
