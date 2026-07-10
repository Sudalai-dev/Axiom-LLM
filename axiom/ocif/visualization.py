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
from ocif.layout import SIZE, label_anchor, ring_positions

# Soft-pastel, Visio/Azure-Architecture-Center-style palette (border, fill) —
# the SVG is rendered as its own light "paper" card floating inside the
# app's dark chat panel, so colors are tuned for a cream background rather
# than the dark-theme neon set this replaced.
_DOMAIN_COLOR = {
    "perception": ("#2196F3", "#E7F5FF"),
    "context": ("#BA68C8", "#F5E8FF"),
    "planning": ("#F9A825", "#FFF5D9"),
    "knowledge": ("#4CAF50", "#E9F7E7"),
    "memory": ("#D4A017", "#FFF7C8"),
    "reasoning": ("#9C27B0", "#F7ECFF"),
    "validation": ("#E91E63", "#FFE8F4"),
    "experience": ("#00ACC1", "#E8F8FF"),
}
_PAGE_BG = "#FFFDF6"
_LINE_COLOR = "#8A8A8A"
_TEXT_COLOR = "#1F2937"
_FONT = "Segoe UI, Calibri, Arial, sans-serif"

# Render-time padding around the shared ring geometry (ocif/layout.py) —
# applied only here, not to the shared constants, since ocif/octagon.py's
# internal cognitive-trace SVG uses the same ring math and must stay
# untouched. Padding gives node labels room so they don't get clipped by
# the viewBox edge, and reserves a clear band above the topmost node so
# the title never overlaps its label.
_PAD_X = 80
_PAD_TOP = 60
_PAD_BOTTOM = 25
_RENDER_W = SIZE + 2 * _PAD_X
_RENDER_H = SIZE + _PAD_TOP + _PAD_BOTTOM


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
        # Render-space positions: the shared ring math (ocif/layout.py) is
        # left untouched (ocif/octagon.py's internal trace SVG depends on
        # it too) — padding is applied only to what gets drawn here.
        positions = {
            domain: (x + _PAD_X, y + _PAD_TOP)
            for domain, (x, y) in zip(DOMAIN_ORDER, ring_positions())
        }

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
                f'stroke="{_LINE_COLOR}" stroke-width="1.5" opacity="0.6" marker-end="url(#arrow)" />'
                f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" font-size="9" '
                f'fill="{_TEXT_COLOR}" font-family="{_FONT}" '
                f'stroke="{_PAGE_BG}" stroke-width="3" paint-order="stroke">{edge.relationship}</text>'
            )

        nodes_svg = []
        for domain in DOMAIN_ORDER:
            node = nodes_by_domain.get(domain)
            if node is None:
                continue
            x, y = positions[domain]
            border, fill = _DOMAIN_COLOR.get(domain, ("#888888", "#F0F0F0"))
            # label_anchor's dx/dy are computed from the un-padded center,
            # so pass the un-shifted coordinates through for that call only.
            anchor, dx, dy = label_anchor(x - _PAD_X, y - _PAD_TOP)
            artifact_count = len(node.artifacts)

            nodes_svg.append(
                f'<g class="solution-node" data-domain="{domain}" role="button" '
                f'tabindex="0" aria-label="{node.label} domain — {artifact_count} artifacts">'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="34" fill="{fill}" '
                f'stroke="{border}" stroke-width="2.5" />'
                f'<text x="{x:.1f}" y="{y+2:.1f}" text-anchor="middle" font-size="10" '
                f'font-weight="700" fill="{border}" font-family="{_FONT}">{artifact_count}</text>'
                f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anchor}" font-size="13" '
                f'font-weight="600" fill="{_TEXT_COLOR}" font-family="{_FONT}">{node.label}</text>'
                f'</g>'
            )

        title = (
            f'<text x="{_RENDER_W / 2:.1f}" y="{_PAD_TOP - 32:.1f}" text-anchor="middle" '
            f'font-size="14" font-weight="700" fill="{_TEXT_COLOR}" font-family="{_FONT}">{model.title}</text>'
        )

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_RENDER_W} {_RENDER_H}" '
            f'width="{_RENDER_W}" height="{_RENDER_H}" '
            'role="img" aria-label="Solution organized across the eight Octagonal domains">'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{_LINE_COLOR}" /></marker></defs>'
            f'<rect x="0" y="0" width="{_RENDER_W}" height="{_RENDER_H}" fill="{_PAGE_BG}" rx="12" />'
            f'<polygon points="{outline_points}" fill="#F6F2FF" fill-opacity="0.5" stroke="#D9C97C" stroke-width="1.5" />'
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
