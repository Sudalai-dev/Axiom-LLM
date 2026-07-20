"""
Diagram Brain — generates AXIOM's 8-layer Blueprint with per-layer observability.

Phase 2 (this file's initial form): deterministic generation — it wraps the
per-layer builders (ocif/blueprint.py) and records a ``diagram_usage`` entry per
layer (provider, latency, node/edge counts, mermaid validity, discard reason).
Phase 4 adds the local-model structure proposal + grounding guard on top,
recorded through the SAME usage records, so the observability lands first and
the behavioural change is measured against it.

Nothing here fabricates: diagrams come from the deterministic builders (grounded
in the request's entities) and any invalid syntax is recorded and dropped to an
honest EMPTY rather than shipped.
"""

import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from ocif.blueprint import build_blueprint
from ocif.blueprint_config import AXIOM_BLUEPRINT_VIEWS
from ocif.frames import Blueprint, Diagram, SolutionDocument

# Closed vocabulary of reasons a proposed diagram is discarded (invariant: never
# swallow failures silently — every drop is recorded with one of these).
DIAGRAM_DISCARD_REASONS = frozenset({
    "no_json", "invalid_structure", "ungrounded_node", "empty", "timeout", "exception",
})

_MERMAID_HEADERS = (
    "flowchart", "graph", "stateDiagram", "sequenceDiagram",
    "classDiagram", "erDiagram", "mindmap",
)
_EDGE_RE = re.compile(r"--+>|==+>|\.\.>|->>|--x|--o|\|\|--|}o--|--o\{|-->")


def validate_mermaid(code: str) -> bool:
    """Deterministic structural guard — not a full parser. Rejects obviously
    broken output before it can ship: must be non-empty, start with a known
    diagram header, have a body line, and have balanced brackets/quotes."""
    if not code or not code.strip():
        return False
    lines = [ln for ln in code.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    if not any(lines[0].strip().startswith(h) for h in _MERMAID_HEADERS):
        return False
    if code.count("[") != code.count("]"):
        return False
    if code.count("(") != code.count(")"):
        return False
    if code.count('"') % 2 != 0:
        return False
    return True


def _edge_count(code: str) -> int:
    return len(_EDGE_RE.findall(code or ""))


@dataclass
class LayerUsage:
    """One per-layer diagram-generation observation (→ trace.diagram_usage)."""
    view: str
    provider: str
    latency_ms: float
    node_count: int
    edge_count: int
    mermaid_valid: bool
    status: str
    discard_reason: Optional[str] = None


class DiagramBrain:
    """Builds the Blueprint and its per-layer usage record.

    ``llm_client`` is accepted now (Phase 2) but only used in Phase 4, where the
    model proposes diagram structure and this class emits it deterministically
    through a grounding guard, falling back to the deterministic builder per
    layer on any failure."""

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self.llm_client = llm_client

    def generate(self, doc: SolutionDocument) -> Tuple[Blueprint, List[Dict[str, Any]]]:
        """Return (Blueprint, diagram_usage). Deterministic in Phase 2."""
        deterministic = {d.view: d for d in build_blueprint(doc).diagrams}
        diagrams: List[Diagram] = []
        usage: List[Dict[str, Any]] = []

        for view in AXIOM_BLUEPRINT_VIEWS:
            t0 = time.perf_counter()
            diagram = deterministic.get(view.key) or Diagram(
                view=view.key, label=view.label, diagram_type=view.diagram_type, status="EMPTY",
            )
            valid = validate_mermaid(diagram.code)
            discard: Optional[str] = None
            # A RENDERED diagram whose mermaid doesn't validate must not ship —
            # record the discard and fall back to an honest EMPTY.
            if diagram.status == "RENDERED" and not valid:
                discard = "invalid_structure"
                diagram = Diagram(
                    view=view.key, label=view.label, diagram_type=view.diagram_type,
                    status="EMPTY", grounded=True, provider_used=diagram.provider_used,
                )
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            diagrams.append(diagram)
            usage.append(asdict(LayerUsage(
                view=view.key,
                provider=diagram.provider_used,
                latency_ms=latency_ms,
                node_count=len(diagram.nodes),
                edge_count=_edge_count(diagram.code),
                mermaid_valid=validate_mermaid(diagram.code),
                status=diagram.status,
                discard_reason=discard,
            )))

        return Blueprint(diagrams=diagrams), usage
