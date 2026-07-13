"""Unit tests for the Engineering Intelligence Engine and pre-inference pipeline."""

import asyncio
import pytest

from ocif.engine import CognitiveEngine
from ocif.engines.engineering_intelligence import (
    EngineeringIntelligenceEngine,
    IntentAnalyzer,
    DomainClassifier,
    IndustryClassifier,
    ExpertSelector,
    KnowledgePackLoader,
    DiagramPlanner,
    DeliverablePlanner,
    UseCaseExpander,
    BlueprintOptimizer,
)
from ocif.frames import (
    CognitiveContext,
    ContextFrame,
    EngineStatus,
    Plan,
    ProjectUnderstandingFrame,
    SolutionDocument,
    TechChoice,
)


def test_engineering_intelligence_compliance():
    """Verifies compliance with the CognitiveEngine interface."""
    engine = EngineeringIntelligenceEngine()
    assert isinstance(engine, CognitiveEngine)
    engine.initialize()
    assert engine._initialized
    engine.shutdown()
    assert not engine._initialized


def test_intent_analyzer():
    analyzer = IntentAnalyzer()
    
    # Test Failure/Troubleshooting keyword detection
    assert analyzer.analyze("The AC unit is broken and leaking water", "general_engineering") == "FAILURE_ANALYSIS"
    
    # Test Database design detection
    assert analyzer.analyze("Create a postgres schema for the ledger", "general_engineering") == "DATABASE_DESIGN"
    
    # Test default fallback
    assert analyzer.analyze("Design a web app", "solution_design") == "SOLUTION_DESIGN"


def test_domain_classifier():
    classifier = DomainClassifier()
    
    # Test multi-domain classification
    domains = classifier.classify("An MQTT telemetry feed writing to a PostgreSQL database with anomaly detection")
    assert "Industrial IoT" in domains
    # PostgreSQL & database match Database Engineering
    assert "Database Engineering" in domains
    # Anomaly detection matches Artificial Intelligence
    assert "Artificial Intelligence" in domains


def test_industry_classifier():
    classifier = IndustryClassifier()
    
    # Test Healthcare mappings
    name, standards = classifier.classify("healthcare")
    assert name == "Healthcare"
    assert any("HIPAA" in std for std in standards)
    assert any("FHIR" in std for std in standards)

    # Test Banking/Finance mappings
    name, standards = classifier.classify("banking_fintech")
    assert name == "Finance & Banking"
    assert any("PCI-DSS" in std for std in standards)


def test_expert_selector():
    selector = ExpertSelector()
    experts = selector.select(["Industrial IoT", "Cybersecurity", "DevOps"])
    assert "Industrial IoT Architect" in experts
    assert "Security Architect" in experts
    assert "Cloud & DevOps Architect" in experts


def test_knowledge_pack_loader():
    loader = KnowledgePackLoader()
    packs = loader.load(["Industrial IoT", "Database Engineering"], "industrial_iot")
    pack_names = [p["name"] for p in packs]
    assert any("Industrial IoT" in name for name in pack_names)
    assert any("Data Storage" in name for name in pack_names)


def test_diagram_planner():
    planner = DiagramPlanner()
    diagrams = planner.plan(["Industrial IoT", "Database Engineering"], "DATABASE_DESIGN")
    assert any("Topology" in d or "Ingestion" in d for d in diagrams)
    assert "Entity-Relationship (ER) Schema Diagram" in diagrams


def test_deliverable_planner():
    planner = DeliverablePlanner()
    assert "Root Cause Analysis (RCA) Report" in planner.plan("FAILURE_ANALYSIS")
    assert "Database Schema Specification" in planner.plan("DATABASE_DESIGN")


def test_use_case_expander():
    expander = UseCaseExpander()
    res = expander.expand("Need a water pump control loop", ["Industrial IoT"], "Manufacturing")
    assert "business_goals" in res
    assert "scalability_strategy" in res
    assert "recovery_strategy" in res


def test_blueprint_optimizer():
    optimizer = BlueprintOptimizer()
    
    doc = SolutionDocument(
        title="Test Doc",
        executive_summary="This is a test TODO placeholder that has insert here",
        problem_statement="Test statement",
        actors=["User"],
        requirements_analysis="Requirements details",
        recommended_solution="Solution details",
        architecture_overview="Overview details with a mermaid diagram\n```mermaid\nflowchart LR\n A --> B\n```",
        technology_stack=[
            TechChoice(layer="DB", choice="Postgres", rationale="Good"),
            TechChoice(layer="DB", choice="Postgres", rationale="Good")  # duplicate
        ],
        component_design="Components details",
        database_design="Database details",
        api_design="API details\n| GET | /endpoint | Description |",
        workflow="Workflow details",
        security_architecture="Security details",
        deployment_architecture="Deployment details",
        monitoring_strategy="Monitoring details",
        testing_strategy="Testing details",
        implementation_roadmap=[],
        risk_assessment=[],
        future_enhancements=["Future detail", "Future detail"],  # duplicate
        final_recommendations="Final recommendations"
    )

    opt_doc, final_conf = optimizer.optimize(doc, ["Software Engineering"], 0.65)
    
    # Verify duplicates removed
    assert len(opt_doc.technology_stack) == 1
    assert len(opt_doc.future_enhancements) == 1
    # Verify placeholders cleaned
    assert "TODO" not in opt_doc.executive_summary
    assert "insert here" not in opt_doc.executive_summary
    # Verify high confidence/completeness
    assert final_conf > 0.70


def test_engineering_intelligence_e2e():
    """Runs the EngineeringIntelligenceEngine end-to-end using synthesizer."""
    engine = EngineeringIntelligenceEngine()
    
    context = CognitiveContext(
        task="Design a secure medical records system compliant with HIPAA for clinical encounters.",
        tenant_id="t1",
        user_id="u1"
    )
    
    # Populate preliminary context frames (simulate previous engine pipeline runs)
    context.context = ContextFrame(
        intent="solution_design",
        entities=["HIPAA", "EHR"],
        actors=["Clinician", "System Administrator"],
        use_cases=[]
    )
    context.plan = Plan(
        functional_requirements=[],
        non_functional_requirements=[]
    )
    context.project_understanding = ProjectUnderstandingFrame(
        industry="healthcare",
        business_domain="Healthcare Records System",
        domain_expert_persona="Healthcare Solutions Architect"
    )

    # Run the engine
    result = asyncio.run(engine._run(context))
    assert result.status == EngineStatus.COMPLETED
    assert context.reasoning is not None
    assert context.reasoning.solution_draft is not None
    assert context.reasoning.confidence > 0.60
    assert "engineering_intelligence" in context.metadata
    
    intel = context.metadata["engineering_intelligence"]
    assert "domains" in intel
    assert "experts" in intel
    assert "standards" in intel
    assert any("HIPAA" in std for std in intel["standards"])
