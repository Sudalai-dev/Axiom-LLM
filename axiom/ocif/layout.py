"""Shared octagon ring-layout geometry, used by both the internal
cognitive-trace SVG (axiom.ocif.octagon) and the user-facing solution
visualization (axiom.ocif.visualization). Pure math, no rendering."""

import math
from typing import List, Tuple

SIZE = 460
CENTER = SIZE / 2
RADIUS = 165
NODE_R = 30


def vertex_position(index: int, total: int = 8, center: float = CENTER, radius: float = RADIUS) -> Tuple[float, float]:
    """Vertex i sits at angle -90° + i*(360/total), i.e. starting at the top, clockwise."""
    angle = math.radians(-90 + index * (360 / total))
    x = center + radius * math.cos(angle)
    y = center + radius * math.sin(angle)
    return x, y


def ring_positions(total: int = 8, center: float = CENTER, radius: float = RADIUS) -> List[Tuple[float, float]]:
    return [vertex_position(i, total, center, radius) for i in range(total)]


def label_anchor(x: float, y: float, center: float = CENTER, node_r: float = NODE_R) -> Tuple[str, float, float]:
    """Returns (text-anchor, dx, dy) so a node's label never overlaps the octagon interior."""
    if x < center - 5:
        anchor, dx = "end", -(node_r + 8)
    elif x > center + 5:
        anchor, dx = "start", node_r + 8
    else:
        anchor, dx = "middle", 0.0
    dy = -(node_r + 18) if y < center else (node_r + 26)
    return anchor, dx, dy
