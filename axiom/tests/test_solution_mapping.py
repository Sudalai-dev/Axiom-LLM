"""Solution Mapping Engine: classifies a finished SolutionDocument into the
eight Octagonal domains — never touches internal cognitive frames."""

import inspect

from ocif.domains import DOMAIN_ORDER, OctagonalModel, SolutionDomain
from ocif.frames import Risk, RoadmapPhase, SolutionDocument, TechChoice
from ocif.solution_mapping import SolutionMappingEngine


def make_document() -> SolutionDocument:
    return SolutionDocument(
        title="Factory Sensor Alerting Platform",
        executive_summary="Summary text.",
        problem_statement="Problem text.",
        requirements_analysis="Requirements text.",
        recommended_solution="Recommended approach text.",
        architecture_overview="Architecture text.",
        technology_stack=[TechChoice(layer="Backend", choice="FastAPI", rationale="Async-first")],
        component_design="Component text.",
        database_design="Database text.",
        api_design="API text.",
        workflow="Workflow text.",
        security_architecture="Security text.",
        deployment_architecture="Deployment text.",
        monitoring_strategy="Monitoring text.",
        testing_strategy="Testing text.",
        implementation_roadmap=[RoadmapPhase(phase="Phase 1 (weeks 1-2)", items=["Do X", "Do Y"])],
        risk_assessment=[Risk(risk="Load spikes", likelihood="medium", impact="high", mitigation="Autoscale")],
        future_enhancements=["Add predictive maintenance"],
        final_recommendations="Final text.",
    )


def test_solution_mapping_engine_signature_is_document_only():
    """Structural guarantee: the engine cannot see CognitiveContext or any
    internal reasoning frame — its only possible input is a SolutionDocument."""
    sig = inspect.signature(SolutionMappingEngine.map)
    params = [p for name, p in sig.parameters.items() if name != "self"]
    assert len(params) == 1
    assert params[0].annotation is SolutionDocument


def test_maps_to_exactly_eight_domains_matching_enum():
    model = SolutionMappingEngine().map(make_document())
    assert isinstance(model, OctagonalModel)
    domains = [n.domain for n in model.nodes]
    assert domains == DOMAIN_ORDER
    assert set(domains) == {d.value for d in SolutionDomain}


def test_every_solution_document_field_is_classified_somewhere():
    doc = make_document()
    model = SolutionMappingEngine().map(doc)
    all_content = []
    for node in model.nodes:
        for artifact in node.artifacts:
            if artifact.content:
                all_content.append(str(artifact.content))
    blob = " ".join(all_content)
    for expected_text in (
        "Summary text.", "Problem text.", "Requirements text.", "Recommended approach text.",
        "Architecture text.", "Component text.", "Database text.", "API text.", "Workflow text.",
        "Security text.", "Deployment text.", "Monitoring text.", "Testing text.", "Final text.",
    ):
        assert expected_text in blob, f"missing: {expected_text}"
    assert any("FastAPI" in c for n in model.nodes for c in [str(a.content) for a in n.artifacts])
    assert any("Load spikes" in c for n in model.nodes for c in [str(a.content) for a in n.artifacts])
    assert any("Add predictive maintenance" in c for n in model.nodes for c in [str(a.content) for a in n.artifacts])


def test_planning_knowledge_validation_domains_match_mission_examples():
    doc = make_document()
    model = SolutionMappingEngine().map(doc)
    by_domain = {n.domain: n for n in model.nodes}

    planning_titles = {a.title for a in by_domain["planning"].artifacts}
    assert "Implementation Roadmap" in planning_titles

    knowledge_titles = {a.title for a in by_domain["knowledge"].artifacts}
    assert "Technology Stack" in knowledge_titles

    validation_titles = {a.title for a in by_domain["validation"].artifacts}
    assert {"Risk Assessment", "Testing Strategy", "Security Architecture"} <= validation_titles


def test_builds_relationships_between_domains():
    model = SolutionMappingEngine().map(make_document())
    assert len(model.edges) >= 8
    domain_set = {d.value for d in SolutionDomain}
    for edge in model.edges:
        assert edge.source in domain_set
        assert edge.target in domain_set
        assert edge.relationship

    for node in model.nodes:
        assert node.related_domains, f"{node.domain} has no related domains"
        assert node.domain not in node.related_domains


def test_node_summaries_are_populated_and_never_empty():
    model = SolutionMappingEngine().map(make_document())
    for node in model.nodes:
        assert node.summary
        assert node.label
        assert node.description
