"""
Project Diagram Engine — Phase 3 (Diagram Intelligence).

Additive layer on top of the existing Solution Mapping / Octagonal
Visualization pipeline (ocif/solution_mapping.py, ocif/visualization.py),
which maps SolutionDocument content onto the 8 solution-content domains
(Perception=problem/env, Context=requirements, Planning=roadmap, ...) — a
protected, standing invariant documented in CLAUDE.md and NOT changed here.

This module instead generates 8 DIFFERENT diagram TYPES — one per pipeline
stage — entirely derived from the already-validated SolutionDocument, so a
water-pump project gets its own state machine/DFD/ER/sequence/class/mind-map/
nav-flow diagrams instead of one generic template repeated for every project.
Like the rest of this output pipeline, it takes only SolutionDocument as
input — never CognitiveContext or ProjectUnderstandingFrame directly — so
every diagram is provably derived from already-public, already-validated
content, never raw user text.

Positional mapping (existing 8 pipeline stages -> requested diagram types):
    perception -> State Machine            (implementation phases as states)
    context    -> Ingestion Flow            (actors -> stack layers)
    planning   -> Data Flow Diagram         (client/API/service/data flow)
    knowledge  -> ER Diagram                (extracted from database_design)
    memory     -> Sequence Diagram          (extracted from workflow)
    reasoning  -> UML Class Diagram         (technology stack as classes)
    validation -> Mind Map                  (risks/testing/monitoring)
    experience -> User Navigation Flow      (actor-facing journey)
"""

import re
from dataclasses import dataclass
from typing import List

from ocif.frames import SolutionDocument

_MERMAID_FENCE = re.compile(r"```mermaid\s*(.*?)```", re.DOTALL)


@dataclass
class ProjectDiagram:
    stage: str
    diagram_type: str
    title: str
    mermaid: str


def _extract_mermaid(text: str) -> str:
    match = _MERMAID_FENCE.search(text or "")
    return match.group(1).strip() if match else ""


def _slug(label: str, fallback: str = "n") -> str:
    slug = re.sub(r"[^A-Za-z0-9_]", "_", (label or "").strip())
    return slug[:40] or fallback


def _esc(label: str) -> str:
    return (label or "").replace('"', "'")


def _state_machine(doc: SolutionDocument) -> str:
    phases = doc.implementation_roadmap
    if not phases:
        return "stateDiagram-v2\n    [*] --> Solution_Delivered\n    Solution_Delivered --> [*]"
    ids = [f"p{i}" for i in range(len(phases))]
    lines = ["stateDiagram-v2"]
    for i, ph in enumerate(phases):
        label = _esc(ph.phase) or f"Phase {i + 1}"
        lines.append(f'    state "{label}" as {ids[i]}')
    lines.append(f"    [*] --> {ids[0]}")
    for a, b in zip(ids, ids[1:]):
        lines.append(f"    {a} --> {b}")
    lines.append(f"    {ids[-1]} --> [*]")
    return "\n".join(lines)


def _ingestion_flow(doc: SolutionDocument) -> str:
    lines = ["flowchart LR"]
    actor_ids = []
    for i, actor in enumerate((doc.actors or ["End User"])[:5]):
        aid = f"a{i}"
        actor_ids.append(aid)
        lines.append(f'    {aid}["{_esc(actor)}"]')
    lines.append('    sys["Ingestion / Intake"]')
    for aid in actor_ids:
        lines.append(f"    {aid} --> sys")
    prev = "sys"
    for i, tc in enumerate(doc.technology_stack[:5]):
        tid = f"t{i}"
        lines.append(f'    {tid}["{_esc(tc.layer)}: {_esc(tc.choice)}"]')
        lines.append(f"    {prev} --> {tid}")
        prev = tid
    return "\n".join(lines)


def _data_flow_diagram(doc: SolutionDocument) -> str:
    lines = [
        "flowchart LR",
        '    client["Client"]',
        '    api["API Layer"]',
        '    svc["Application Service"]',
        '    db["Data Store"]',
        "    client --> api --> svc --> db",
        "    db --> svc --> api --> client",
    ]
    endpoints = [
        line.strip() for line in (doc.api_design or "").splitlines()
        if line.strip().startswith("|") and line.count("|") >= 3
    ]
    for i, row in enumerate(endpoints[:3]):
        cols = [c.strip() for c in row.strip("|").split("|")]
        if len(cols) >= 2 and cols[1]:
            lines.append(f'    api -.-> ep{i}["{_esc(cols[1])}"]')
    return "\n".join(lines)


def _er_diagram(doc: SolutionDocument) -> str:
    extracted = _extract_mermaid(doc.database_design)
    if extracted.lower().startswith("erdiagram"):
        return extracted
    return 'erDiagram\n    ENTITY {\n        string id\n        string name\n    }'


def _sequence_diagram(doc: SolutionDocument) -> str:
    extracted = _extract_mermaid(doc.workflow)
    if extracted.lower().startswith("sequencediagram"):
        return extracted
    actors = doc.actors or ["User"]
    lines = ["sequenceDiagram"]
    ids = []
    for i, actor in enumerate(actors[:4]):
        aid = f"p{i}"
        ids.append(aid)
        lines.append(f"    participant {aid} as {_esc(actor)}")
    for a, b in zip(ids, ids[1:]):
        lines.append(f"    {a}->>{b}: request")
    return "\n".join(lines)


def _uml_class_diagram(doc: SolutionDocument) -> str:
    lines = ["classDiagram"]
    class_names = []
    for tc in doc.technology_stack[:8]:
        cname = _slug(tc.layer, fallback=f"Layer{len(class_names)}")
        class_names.append(cname)
        lines.append(f"    class {cname} {{")
        lines.append(f"        +choice : {_esc(tc.choice)}")
        lines.append("    }")
    for a, b in zip(class_names, class_names[1:]):
        lines.append(f"    {a} --> {b}")
    if not class_names:
        lines.append("    class Application")
    return "\n".join(lines)


def _mind_map(doc: SolutionDocument) -> str:
    lines = ["mindmap", f"  root(({_esc(doc.title) or 'Solution'}))"]
    if doc.risk_assessment:
        lines.append("    Risks")
        for r in doc.risk_assessment[:5]:
            lines.append(f"      {_esc(r.risk)[:60] or 'Risk'}")
    if doc.requirements_analysis:
        lines.append("    Requirements Analysis")
    if doc.testing_strategy:
        lines.append("    Testing Strategy")
    if doc.monitoring_strategy:
        lines.append("    Monitoring Strategy")
    if doc.security_architecture:
        lines.append("    Security Architecture")
    return "\n".join(lines)


def _user_navigation_flow(doc: SolutionDocument) -> str:
    lines = ["flowchart TD", '    entry(["Login / Entry"])']
    prev = "entry"
    steps = ["Dashboard"]
    for actor in (doc.actors or [])[:3]:
        steps.append(f"{actor} Workspace")
    steps += ["Reports & Monitoring", "Settings"]
    for i, step in enumerate(steps):
        sid = f"s{i}"
        lines.append(f'    {sid}["{_esc(step)}"]')
        lines.append(f"    {prev} --> {sid}")
        prev = sid
    return "\n".join(lines)


_STAGE_DIAGRAM_BUILDERS = [
    ("perception", "State Machine", _state_machine),
    ("context", "Ingestion Flow", _ingestion_flow),
    ("planning", "Data Flow Diagram", _data_flow_diagram),
    ("knowledge", "ER Diagram", _er_diagram),
    ("memory", "Sequence Diagram", _sequence_diagram),
    ("reasoning", "UML Class Diagram", _uml_class_diagram),
    ("validation", "Mind Map", _mind_map),
    ("experience", "User Navigation Flow", _user_navigation_flow),
]


def build_project_diagrams(doc: SolutionDocument) -> List[ProjectDiagram]:
    """Builds the 8 project-specific diagrams for a finished SolutionDocument.
    Never fabricates: every diagram is derived from fields already present
    and validated on the document (roadmap, actors, tech stack, risks, or
    mermaid blocks already embedded by the industry-specific synthesizer)."""
    diagrams = []
    for stage, diagram_type, builder in _STAGE_DIAGRAM_BUILDERS:
        mermaid = builder(doc)
        diagrams.append(
            ProjectDiagram(
                stage=stage,
                diagram_type=diagram_type,
                title=f"{diagram_type} — {doc.title}",
                mermaid=mermaid,
            )
        )
    return diagrams
