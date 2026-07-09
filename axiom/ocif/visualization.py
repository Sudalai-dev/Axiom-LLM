"""
Octagonal Visualization Engine.

Takes a normalized OctagonalModel (solution domains + relationships — never
engine execution) and renders it in five interchangeable formats:
interactive SVG, Mermaid, PlantUML, a generic JSON graph model, and a
ReactFlow-compatible graph. Every node represents a SOLUTION DOMAIN;
nothing here ever renders engine names, statuses, durations, or confidence.
"""

import re
from typing import Any, Dict, List

from ocif.domains import DOMAIN_ORDER, OctagonalModel
from ocif.layout import label_anchor, ring_positions

_DOMAIN_COLOR = {
    "perception": "#3b82f6",
    "context": "#8b5cf6",
    "planning": "#f59e0b",
    "knowledge": "#10b981",
    "memory": "#06b6d4",
    "reasoning": "#6366f1",
    "validation": "#ef4444",
    "experience": "#ec4899",
}


class OctagonalVisualizationEngine:
    """Renders an OctagonalModel as SVG / Mermaid / PlantUML / JSON graph / ReactFlow."""

    def generate(self, model: OctagonalModel) -> Dict[str, Any]:
        return {
            "svg": self.build_svg(model),
            "mermaid": self.build_mermaid(model),
            "plantuml": self.build_plantuml(model),
            "json_graph": self.build_json_graph(model),
            "reactflow": self.build_reactflow(model),
        }

    # -- SVG (interactive: each node carries data-domain for client drill-down) --

    def build_svg(self, model: OctagonalModel) -> str:
        nodes_by_domain = {n.domain: n for n in model.nodes}
        positions = {domain: pos for domain, pos in zip(DOMAIN_ORDER, ring_positions())}

        outline_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in positions.values())

        edges_svg = []
        for edge in model.edges:
            if edge.source not in positions or edge.target not in positions:
                continue
            x1, y1 = positions[edge.source]
            x2, y2 = positions[edge.target]
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            edges_svg.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="#818cf8" stroke-width="1.5" opacity="0.5" marker-end="url(#arrow)" />'
                f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" font-size="9" '
                f'fill="#94a3b8" font-family="sans-serif">{edge.relationship}</text>'
            )

        nodes_svg = []
        for domain in DOMAIN_ORDER:
            node = nodes_by_domain.get(domain)
            if node is None:
                continue
            x, y = positions[domain]
            color = _DOMAIN_COLOR.get(domain, "#334155")
            anchor, dx, dy = label_anchor(x, y)
            artifact_count = len(node.artifacts)

            nodes_svg.append(
                f'<g class="solution-node" data-domain="{domain}" role="button" '
                f'tabindex="0" aria-label="{node.label} domain — {artifact_count} artifacts">'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="34" fill="{color}" fill-opacity="0.20" '
                f'stroke="{color}" stroke-width="2.5" />'
                f'<text x="{x:.1f}" y="{y+2:.1f}" text-anchor="middle" font-size="10" '
                f'font-weight="700" fill="{color}" font-family="monospace">{artifact_count}</text>'
                f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anchor}" font-size="13" '
                f'font-weight="600" fill="#e2e8f0" font-family="sans-serif">{node.label}</text>'
                f'</g>'
            )

        title = f'<text x="230" y="26" text-anchor="middle" font-size="13" font-weight="600" fill="#e2e8f0" font-family="sans-serif">{model.title}</text>'

        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 460" width="460" height="460" '
            'role="img" aria-label="Solution organized across the eight Octagonal domains">'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#818cf8" /></marker></defs>'
            f'<polygon points="{outline_points}" fill="#6366f1" fill-opacity="0.04" stroke="#334155" stroke-width="1.5" />'
            + "".join(edges_svg)
            + "".join(nodes_svg)
            + title
            + "</svg>"
        )

    # -- Mermaid ---------------------------------------------------------------

    def build_mermaid(self, model: OctagonalModel) -> str:
        lines = ["flowchart LR"]
        for node in model.nodes:
            lines.append(f'    {node.domain}["{node.label}<br/>{len(node.artifacts)} artifacts"]')
        for edge in model.edges:
            lines.append(f"    {edge.source} -->|{edge.relationship}| {edge.target}")
        return "\n".join(lines)

    # -- PlantUML --------------------------------------------------------------

    def build_plantuml(self, model: OctagonalModel) -> str:
        lines = ["@startuml", f'title {model.title}']
        for node in model.nodes:
            lines.append(f'package "{node.label}" as {node.domain} {{\n}}')
        for edge in model.edges:
            lines.append(f"{edge.source} --> {edge.target} : {edge.relationship}")
        lines.append("@enduml")
        return "\n".join(lines)

    # -- Generic JSON graph model ------------------------------------------------

    def build_json_graph(self, model: OctagonalModel) -> Dict[str, Any]:
        return {
            "graph_id": model.graph_id,
            "solution_id": model.solution_id,
            "title": model.title,
            "nodes": [
                {
                    "id": n.domain,
                    "label": n.label,
                    "description": n.description,
                    "summary": n.summary,
                    "artifact_count": len(n.artifacts),
                    "related_domains": n.related_domains,
                }
                for n in model.nodes
            ],
            "edges": [
                {"source": e.source, "target": e.target, "relationship": e.relationship}
                for e in model.edges
            ],
        }

    # -- ReactFlow-compatible graph -----------------------------------------------

    def build_reactflow(self, model: OctagonalModel) -> Dict[str, Any]:
        positions = {domain: pos for domain, pos in zip(DOMAIN_ORDER, ring_positions())}
        nodes = []
        for n in model.nodes:
            x, y = positions.get(n.domain, (0, 0))
            nodes.append({
                "id": n.domain,
                "type": "default",
                "position": {"x": round(x, 1), "y": round(y, 1)},
                "data": {
                    "label": n.label,
                    "description": n.description,
                    "summary": n.summary,
                    "artifactCount": len(n.artifacts),
                },
            })
        edges = [
            {
                "id": f"{e.source}-{e.target}",
                "source": e.source,
                "target": e.target,
                "label": e.relationship,
                "animated": False,
            }
            for e in model.edges
        ]
        return {"nodes": nodes, "edges": edges}
