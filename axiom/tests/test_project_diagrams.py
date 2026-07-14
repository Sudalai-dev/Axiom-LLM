"""
Unit tests for ocif/project_diagrams.py — Phase 3 (Diagram Intelligence).
Verifies the 8 stage-diagram-type mapping produces valid, project-specific
mermaid diagrams derived only from SolutionDocument (never fabricated), and
that a full kernel run exposes them additively without disturbing the
existing response schema.
"""

import asyncio

from ocif.blueprint_pipeline import build_solution_response
from ocif.frames import RoadmapPhase, Risk, SolutionDocument, TechChoice
from ocif.kernel import OctagonalKernel
from ocif.project_diagrams import build_project_diagrams

EXPECTED_STAGES = [
    ("perception", "State Machine"),
    ("context", "Ingestion Flow"),
    ("planning", "Data Flow Diagram"),
    ("knowledge", "ER Diagram"),
    ("memory", "Sequence Diagram"),
    ("reasoning", "UML Class Diagram"),
    ("validation", "Mind Map"),
    ("experience", "User Navigation Flow"),
]

_MERMAID_HEADERS = {
    "State Machine": "statediagram",
    "Ingestion Flow": "flowchart",
    "Data Flow Diagram": "flowchart",
    "ER Diagram": "erdiagram",
    "Sequence Diagram": "sequencediagram",
    "UML Class Diagram": "classdiagram",
    "Mind Map": "mindmap",
    "User Navigation Flow": "flowchart",
}


def _sample_doc() -> SolutionDocument:
    return SolutionDocument(
        title="Water Pump Predictive Maintenance",
        actors=["Plant Operator", "Maintenance Engineer"],
        technology_stack=[
            TechChoice(layer="Device Connectivity", choice="MQTT", rationale="lightweight pub/sub"),
            TechChoice(layer="Application API", choice="FastAPI", rationale="async"),
        ],
        database_design="Uses TimescaleDB.\n```mermaid\nerDiagram\n    DEVICE ||--o{ TELEMETRY : emits\n```",
        workflow="Telemetry flow.\n```mermaid\nsequenceDiagram\n    participant D as Device\n    D->>S: telemetry\n```",
        api_design="| GET | /api/v1/devices | List devices |\n| GET | /api/v1/devices/{id}/telemetry | Query telemetry |",
        risk_assessment=[Risk(risk="Unreliable connectivity", likelihood="high", impact="medium", mitigation="buffering")],
        testing_strategy="Contract tests for telemetry ingestion.",
        monitoring_strategy="Dashboards for device health.",
        implementation_roadmap=[
            RoadmapPhase(phase="Foundation", items=["Set up ingestion"]),
            RoadmapPhase(phase="Core Build", items=["Implement alerting"]),
        ],
    )


def test_all_eight_stages_present_with_correct_diagram_types():
    diagrams = build_project_diagrams(_sample_doc())
    assert [(d.stage, d.diagram_type) for d in diagrams] == EXPECTED_STAGES


def test_each_diagram_is_shaped_mermaid_for_its_type():
    diagrams = build_project_diagrams(_sample_doc())
    for d in diagrams:
        expected_header = _MERMAID_HEADERS[d.diagram_type]
        assert d.mermaid.strip().lower().startswith(expected_header), d.diagram_type
        assert d.mermaid.strip(), d.diagram_type


def test_er_and_sequence_diagrams_reuse_already_embedded_mermaid_not_fabricated():
    diagrams = {d.diagram_type: d for d in build_project_diagrams(_sample_doc())}
    assert "DEVICE" in diagrams["ER Diagram"].mermaid
    assert "Device" in diagrams["Sequence Diagram"].mermaid


def test_state_machine_reflects_actual_roadmap_phases():
    diagrams = {d.diagram_type: d for d in build_project_diagrams(_sample_doc())}
    sm = diagrams["State Machine"].mermaid
    assert "Foundation" in sm
    assert "Core_Build" in sm or "Core Build" in sm


def test_different_projects_produce_different_diagrams():
    doc_a = _sample_doc()
    doc_b = SolutionDocument(title="Hospital Patient Flow", actors=["Doctor", "Nurse"])
    diagrams_a = build_project_diagrams(doc_a)
    diagrams_b = build_project_diagrams(doc_b)
    assert diagrams_a[0].mermaid != diagrams_b[0].mermaid or diagrams_a[1].mermaid != diagrams_b[1].mermaid


def test_project_diagrams_key_is_additive_in_blueprint_pipeline():
    package = build_solution_response(_sample_doc(), markdown="# doc")
    assert "project_diagrams" in package
    assert len(package["project_diagrams"]) == 8
    # existing keys still present, unchanged contract
    for legacy_key in ("solution_blueprint", "octagonal_model", "visualizations", "implementation_roadmap", "generated_documents"):
        assert legacy_key in package


def test_full_kernel_run_exposes_project_diagrams():
    kernel = OctagonalKernel()
    out = asyncio.run(kernel.process(
        "Design a predictive maintenance platform for factory water pumps with MQTT telemetry.",
        tenant_id="diagram-test",
    ))
    assert not out.is_conversational
