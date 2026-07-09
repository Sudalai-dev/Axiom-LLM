"""
Octagon Visualization — renders the 8-engine execution as an actual octagon
diagram (SVG), one vertex per engine, in execution order.

This is a developer/admin-mode-only artifact (Master Prompt "framework stays
internal" directive) — it visualizes *how* Axiom reasoned, never shown to a
normal end user. Pure stdlib (math + string templating), no image/plotting
dependency, so it renders identically server-side and matches the project's
existing "pure-python, no heavy deps" convention.
"""

import math
from typing import List, Optional

from ocif.frames import EngineResult, EngineStatus

# Fixed execution-order ring — 8 engines, 8 vertices, in Master Prompt Part B order.
ENGINE_ORDER = [
    "perception", "context", "planning", "knowledge",
    "memory", "reasoning", "validation", "experience",
]

_STATUS_COLOR = {
    EngineStatus.COMPLETED.value: "#10b981",
    EngineStatus.SKIPPED.value: "#64748b",
    EngineStatus.FAILED.value: "#ef4444",
}
_STATUS_LABEL = {
    "perception": "Perception",
    "context": "Context",
    "planning": "Planning",
    "knowledge": "Knowledge",
    "memory": "Memory",
    "reasoning": "Reasoning",
    "validation": "Validation",
    "experience": "Experience",
}

_SIZE = 460
_CENTER = _SIZE / 2
_RADIUS = 165
_NODE_R = 30


def _vertex_position(index: int, total: int = 8) -> "tuple[float, float]":
    """Vertex i sits at angle -90° + i*(360/total), i.e. starting at the top, clockwise."""
    angle = math.radians(-90 + index * (360 / total))
    x = _CENTER + _RADIUS * math.cos(angle)
    y = _CENTER + _RADIUS * math.sin(angle)
    return x, y


def build_octagon_svg(
    engine_timeline: List[EngineResult],
    confidence: float = 0.0,
    total_duration_ms: Optional[float] = None,
) -> str:
    """
    Renders the octagonal execution as an SVG string: 8 vertices (one per
    engine, in execution order) on the octagon's own edges, colored by
    status, labeled with elapsed time, with the sequential execution path
    highlighted and a center badge summarizing confidence/total duration.
    """
    results_by_engine = {
        (r.engine.value if hasattr(r.engine, "value") else r.engine): r
        for r in engine_timeline
    }
    if total_duration_ms is None:
        total_duration_ms = sum(r.duration_ms for r in engine_timeline)

    positions = [_vertex_position(i) for i in range(8)]

    # Octagon outline (connects all 8 vertices in ring order)
    outline_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in positions)

    # Sequential execution edges — highlighted solid when both ends ran,
    # dashed+dim when the destination engine was skipped (e.g. Knowledge).
    edges = []
    for i in range(8):
        x1, y1 = positions[i]
        x2, y2 = positions[(i + 1) % 8]
        dest_name = ENGINE_ORDER[(i + 1) % 8]
        dest_result = results_by_engine.get(dest_name)
        skipped = dest_result is not None and dest_result.status == EngineStatus.SKIPPED
        stroke = "#475569" if skipped else "#818cf8"
        dash = ' stroke-dasharray="4,4"' if skipped else ""
        edges.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="2"{dash} opacity="0.8" />'
        )

    nodes = []
    for i, name in enumerate(ENGINE_ORDER):
        x, y = positions[i]
        result = results_by_engine.get(name)
        status = (result.status.value if result and hasattr(result.status, "value") else (result.status if result else "pending")) or "pending"
        color = _STATUS_COLOR.get(status, "#334155")
        duration = f"{result.duration_ms:.0f}ms" if result else "—"
        label = _STATUS_LABEL[name]

        # Label anchor flips so text never overlaps the octagon interior
        label_dx = 0
        if x < _CENTER - 5:
            anchor, label_dx = "end", -(_NODE_R + 8)
        elif x > _CENTER + 5:
            anchor, label_dx = "start", _NODE_R + 8
        else:
            anchor, label_dx = "middle", 0
        label_dy = -(_NODE_R + 18) if y < _CENTER else (_NODE_R + 26)

        nodes.append(
            f'<g>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{_NODE_R}" fill="{color}" '
            f'fill-opacity="0.18" stroke="{color}" stroke-width="2.5" />'
            f'<text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" font-size="11" '
            f'font-weight="600" fill="{color}" font-family="monospace">{i + 1}</text>'
            f'<text x="{x + label_dx:.1f}" y="{y + label_dy:.1f}" text-anchor="{anchor}" '
            f'font-size="13" font-weight="600" fill="#e2e8f0" font-family="sans-serif">{label}</text>'
            f'<text x="{x + label_dx:.1f}" y="{y + label_dy + 15:.1f}" text-anchor="{anchor}" '
            f'font-size="11" fill="#94a3b8" font-family="monospace">{status} · {duration}</text>'
            f'</g>'
        )

    pct = round(confidence * 100)
    center_badge = (
        f'<circle cx="{_CENTER}" cy="{_CENTER}" r="52" fill="#111827" stroke="#6366f1" stroke-width="1.5" opacity="0.9" />'
        f'<text x="{_CENTER}" y="{_CENTER - 8:.1f}" text-anchor="middle" font-size="20" font-weight="700" '
        f'fill="#e2e8f0" font-family="sans-serif">{pct}%</text>'
        f'<text x="{_CENTER}" y="{_CENTER + 10:.1f}" text-anchor="middle" font-size="10" '
        f'fill="#94a3b8" font-family="sans-serif">confidence</text>'
        f'<text x="{_CENTER}" y="{_CENTER + 25:.1f}" text-anchor="middle" font-size="10" '
        f'fill="#64748b" font-family="monospace">{total_duration_ms:.0f}ms total</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SIZE} {_SIZE}" '
        f'width="{_SIZE}" height="{_SIZE}" role="img" aria-label="Octagonal Cognitive Framework execution trace">'
        f'<rect width="{_SIZE}" height="{_SIZE}" fill="none" />'
        f'<polygon points="{outline_points}" fill="#6366f1" fill-opacity="0.04" '
        f'stroke="#334155" stroke-width="1.5" />'
        + "".join(edges)
        + center_badge
        + "".join(nodes)
        + "</svg>"
    )
    return svg
