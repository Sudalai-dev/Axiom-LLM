"""
Solution Mapping Engine.

Receives the completed Solution Blueprint (SolutionDocument) and classifies
every solution component into one or more of the eight Octagonal domains,
builds relationships between domains, and produces a normalized
OctagonalModel. Operates ONLY on the already-validated, user-facing
SolutionDocument — it has no access to CognitiveContext, engine results, or
any internal reasoning frame, so it structurally cannot leak cognitive
execution traces.

Each node also ships its own engineering diagram where one can be derived
honestly from the blueprint: diagrams already embedded in a section's
markdown (architecture/ER/deployment/workflow) are extracted, and a small
number of new diagrams (actor/context map, technology dependency graph,
roadmap timeline, risk quadrant) are generated deterministically from
already-present structured fields — nothing is fabricated.
"""

import re
from typing import List, Optional

from ocif.domains import (
    DOMAIN_DESCRIPTIONS,
    DOMAIN_LABELS,
    DOMAIN_ORDER,
    DOMAIN_RELATIONSHIPS,
    DomainArtifact,
    DomainDiagram,
    DomainEdge,
    OctagonalModel,
    SolutionDomainNode,
)
from ocif.frames import SolutionDocument

_SUMMARY_LEN = 180
_MERMAID_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def _summarize(text: str) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:_SUMMARY_LEN] + ("…" if len(text) > _SUMMARY_LEN else "")


def _summarize_artifacts(artifacts: List[DomainArtifact]) -> str:
    for artifact in artifacts:
        if artifact.type == "text" and artifact.content:
            return _summarize(str(artifact.content))
    if artifacts:
        first = artifacts[0]
        if first.type == "list" and isinstance(first.content, list) and first.content:
            return _summarize(str(first.content[0]))
        if first.type == "table" and isinstance(first.content, list) and first.content:
            return f"{len(first.content)} item(s) in {first.title}"
    return "No content in this domain for this solution."


def _extract_mermaid(title: str, text: str) -> Optional[DomainDiagram]:
    """Pulls the first ```mermaid fenced block already embedded in a
    section's markdown, if any. Never fabricates — returns None if absent."""
    match = _MERMAID_BLOCK.search(text or "")
    if not match:
        return None
    return DomainDiagram(title=title, type="mermaid", content=match.group(1).strip())


class SolutionMappingEngine:
    """Classifies a SolutionDocument's content into the 8 Octagonal domains."""

    def map(self, doc: SolutionDocument) -> OctagonalModel:
        nodes = [
            self._build_node(
                "perception",
                artifacts=[
                    DomainArtifact(title="Executive Summary", type="text", content=doc.executive_summary),
                    DomainArtifact(title="Problem Statement", type="text", content=doc.problem_statement),
                    DomainArtifact(title="Actors & Stakeholders", type="list", content=list(doc.actors)),
                ],
                diagrams=self._perception_diagrams(doc),
            ),
            self._build_node(
                "context",
                artifacts=[
                    DomainArtifact(title="Requirements Analysis", type="text", content=doc.requirements_analysis),
                    DomainArtifact(title="Workflow", type="text", content=doc.workflow),
                ],
                diagrams=self._filter_diagrams([
                    _extract_mermaid("Workflow", doc.workflow),
                ]),
            ),
            self._build_node(
                "planning",
                artifacts=[
                    DomainArtifact(
                        title="Implementation Roadmap", type="table",
                        content=[{"phase": p.phase, "items": p.items} for p in doc.implementation_roadmap],
                    ),
                ],
                diagrams=self._filter_diagrams([self._planning_timeline_diagram(doc)]),
            ),
            self._build_node(
                "knowledge",
                artifacts=[
                    DomainArtifact(
                        title="Technology Stack", type="table",
                        content=[{"layer": t.layer, "choice": t.choice, "rationale": t.rationale} for t in doc.technology_stack],
                    ),
                ],
                diagrams=self._filter_diagrams([self._knowledge_dependency_diagram(doc)]),
            ),
            self._build_node(
                "memory",
                artifacts=[
                    DomainArtifact(title="Architecture Overview", type="text", content=doc.architecture_overview),
                    DomainArtifact(title="Component Design", type="text", content=doc.component_design),
                    DomainArtifact(title="Database Design", type="text", content=doc.database_design),
                ],
                diagrams=self._filter_diagrams([
                    _extract_mermaid("Architecture Overview", doc.architecture_overview),
                    _extract_mermaid("Database Design (ER Diagram)", doc.database_design),
                ]),
            ),
            self._build_node(
                "reasoning",
                artifacts=[
                    DomainArtifact(title="Recommended Solution", type="text", content=doc.recommended_solution),
                    DomainArtifact(title="API Design", type="text", content=doc.api_design),
                    DomainArtifact(title="Final Recommendations", type="text", content=doc.final_recommendations),
                ],
                diagrams=[],
            ),
            self._build_node(
                "validation",
                artifacts=[
                    DomainArtifact(
                        title="Risk Assessment", type="table",
                        content=[{"risk": r.risk, "likelihood": r.likelihood, "impact": r.impact, "mitigation": r.mitigation} for r in doc.risk_assessment],
                    ),
                    DomainArtifact(title="Testing Strategy", type="text", content=doc.testing_strategy),
                    DomainArtifact(title="Security Architecture", type="text", content=doc.security_architecture),
                ],
                diagrams=self._filter_diagrams([self._risk_quadrant_diagram(doc)]),
            ),
            self._build_node(
                "experience",
                artifacts=[
                    DomainArtifact(title="Deployment Architecture", type="text", content=doc.deployment_architecture),
                    DomainArtifact(title="Monitoring Strategy", type="text", content=doc.monitoring_strategy),
                    DomainArtifact(title="Future Enhancements", type="list", content=list(doc.future_enhancements)),
                ],
                diagrams=self._filter_diagrams([
                    _extract_mermaid("Deployment Architecture", doc.deployment_architecture),
                ]),
            ),
        ]

        edges = [DomainEdge(**rel) for rel in DOMAIN_RELATIONSHIPS]

        return OctagonalModel(
            solution_id=doc.solution_id,
            title=doc.title,
            nodes=nodes,
            edges=edges,
        )

    # -- diagram generators (deterministic, derived only from SolutionDocument) --

    def _perception_diagrams(self, doc: SolutionDocument) -> List[DomainDiagram]:
        """System Context diagram: actors -> system -> external technology entities."""
        if not doc.actors and not doc.technology_stack:
            return []
        lines = ["flowchart LR"]
        actor_ids = []
        for i, actor in enumerate(doc.actors[:6]):
            aid = f"A{i}"
            actor_ids.append(aid)
            lines.append(f'    {aid}(["{actor}"])')
        lines.append('    SYS["System Under Design"]')
        for aid in actor_ids:
            lines.append(f"    {aid} --> SYS")
        for i, t in enumerate(doc.technology_stack[:6]):
            eid = f"E{i}"
            lines.append(f'    SYS --> {eid}["{t.choice}"]')
        return self._filter_diagrams([DomainDiagram(title="System Context", type="mermaid", content="\n".join(lines))])

    def _planning_timeline_diagram(self, doc: SolutionDocument) -> Optional[DomainDiagram]:
        """Phase dependency/timeline chain — no fabricated calendar dates,
        just the already-generated phase order and labels."""
        if not doc.implementation_roadmap:
            return None
        lines = ["flowchart LR"]
        ids = [f"P{i}" for i in range(len(doc.implementation_roadmap))]
        for pid, phase in zip(ids, doc.implementation_roadmap):
            label = phase.phase.replace('"', "'")
            lines.append(f'    {pid}["{label}"]')
        for a, b in zip(ids, ids[1:]):
            lines.append(f"    {a} --> {b}")
        return DomainDiagram(title="Implementation Timeline", type="mermaid", content="\n".join(lines))

    def _knowledge_dependency_diagram(self, doc: SolutionDocument) -> Optional[DomainDiagram]:
        """Technology/layer dependency graph from the tech stack table."""
        if not doc.technology_stack:
            return None
        lines = ["flowchart TD"]
        for i, t in enumerate(doc.technology_stack):
            layer_id, choice_id = f"L{i}", f"C{i}"
            layer = t.layer.replace('"', "'")
            choice = t.choice.replace('"', "'")
            lines.append(f'    {layer_id}["{layer}"] --> {choice_id}["{choice}"]')
        return DomainDiagram(title="Technology Dependency Map", type="mermaid", content="\n".join(lines))

    def _risk_quadrant_diagram(self, doc: SolutionDocument) -> Optional[DomainDiagram]:
        """Likelihood x impact quadrant chart from the already-structured risk list."""
        if not doc.risk_assessment:
            return None
        axis_map = {"low": 0.2, "medium": 0.5, "high": 0.85}
        lines = [
            "quadrantChart",
            "    title Risk Likelihood vs Impact",
            "    x-axis Low Impact --> High Impact",
            "    y-axis Low Likelihood --> High Likelihood",
        ]
        for r in doc.risk_assessment:
            x = axis_map.get(r.impact.lower(), 0.5)
            y = axis_map.get(r.likelihood.lower(), 0.5)
            label = r.risk[:40].replace("[", "(").replace("]", ")")
            lines.append(f"    {label}: [{x:.2f}, {y:.2f}]")
        return DomainDiagram(title="Risk Quadrant", type="mermaid", content="\n".join(lines))

    def _filter_diagrams(self, diagrams: List[Optional[DomainDiagram]]) -> List[DomainDiagram]:
        return [d for d in diagrams if d is not None]

    # -- node assembly --------------------------------------------------------

    def _build_node(
        self, domain: str, artifacts: List[DomainArtifact], diagrams: List[DomainDiagram]
    ) -> SolutionDomainNode:
        related = sorted({
            (edge["target"] if edge["source"] == domain else edge["source"])
            for edge in DOMAIN_RELATIONSHIPS
            if edge["source"] == domain or edge["target"] == domain
        })
        return SolutionDomainNode(
            domain=domain,
            label=DOMAIN_LABELS[domain],
            description=DOMAIN_DESCRIPTIONS[domain],
            summary=_summarize_artifacts(artifacts),
            artifacts=artifacts,
            diagrams=diagrams,
            related_domains=related,
        )
