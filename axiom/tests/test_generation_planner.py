"""
Phase 5 (Dynamic Planning Engine) tests — GenerationPlanner decides what
should be generated (documents/diagrams/reports/images/architecture) from
Project Intelligence alone, and is surfaced only in the developer-mode trace
(never in the normal user-facing response), matching how domains/experts/
standards provenance already works.
"""

import asyncio

from ocif.engines.engineering_intelligence import EngineeringIntelligenceEngine
from ocif.engines.generation_planner import GenerationPlanner
from ocif.engines.industry_patterns import select_pattern
from ocif.frames import CognitiveContext, ContextFrame, Plan, ProjectUnderstandingFrame
from ocif.kernel import OctagonalKernel


def test_generation_planner_surfaces_all_five_planner_outputs():
    understanding = ProjectUnderstandingFrame(
        industry="industrial_iot",
        architecture_style="Event-driven, edge-to-cloud",
        deployment_model="Hybrid (edge gateway + cloud)",
        system_type="Edge-to-cloud telemetry and alerting system",
        recommended_documents=["Sensor Architecture", "Telemetry Flow"],
        recommended_diagrams=["Device connectivity diagram"],
        required_images=["Device topology diagram image"],
        required_reports=["Remaining Useful Life Report"],
    )
    pattern = select_pattern(understanding)
    plan = GenerationPlanner().plan(understanding, pattern)

    assert plan.document_focus == ["Sensor Architecture", "Telemetry Flow"]
    assert plan.diagram_focus == ["Device connectivity diagram"]
    assert plan.report_plan == ["Remaining Useful Life Report"]
    assert "no image-generation engine is wired yet" in plan.image_plan[0]
    assert plan.architecture_plan["architecture_style"] == "Event-driven, edge-to-cloud"
    assert plan.architecture_plan["key_components"]


def test_generation_planner_safe_with_no_understanding():
    pattern = select_pattern(None)
    plan = GenerationPlanner().plan(None, pattern)
    assert plan.document_focus == []
    assert plan.image_plan == []
    assert plan.architecture_plan["architecture_style"] == ""


def test_generation_plan_surfaced_in_engineering_intelligence_metadata():
    engine = EngineeringIntelligenceEngine()
    context = CognitiveContext(task="Design a factory predictive maintenance platform.")
    context.context = ContextFrame(intent="solution_design", entities=[], actors=["Plant Operator"])
    context.plan = Plan(functional_requirements=[], non_functional_requirements=[])
    context.project_understanding = ProjectUnderstandingFrame(
        industry="industrial_iot",
        recommended_documents=["Sensor Architecture"],
    )
    asyncio.run(engine._run(context))
    intel = context.metadata["engineering_intelligence"]
    assert "generation_plan" in intel
    assert intel["generation_plan"]["document_focus"] == ["Sensor Architecture"]


def test_generation_plan_never_reaches_normal_user_response():
    kernel = OctagonalKernel()
    out = asyncio.run(kernel.process(
        "Design a predictive maintenance platform for factory water pumps.",
        user_id="plan-test",
    ))
    assert "generation_plan" not in out.solution_markdown
    assert "generation_plan" not in out.solution_json
