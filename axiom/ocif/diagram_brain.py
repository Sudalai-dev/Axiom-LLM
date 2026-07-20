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
from ocif.blueprint_config import AXIOM_BLUEPRINT_VIEWS, AXIOM_LAYER_PRIMITIVES
from ocif.frames import Blueprint, Diagram, SolutionDocument
from ocif.mermaid_emit import emit_mermaid

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
        """Return (Blueprint, diagram_usage).

        Per layer: if the local model is available, it proposes diagram STRUCTURE
        (grounded on the request's typed entities); this class guards it (every
        node must be a real entity or a permitted primitive), emits mermaid
        deterministically, and validates it. On any failure — no JSON, ungrounded
        node, empty, invalid syntax — the layer falls back to the deterministic
        builder. Every outcome is recorded in diagram_usage."""
        deterministic = {d.view: d for d in build_blueprint(doc).diagrams}
        canonical = self._canonical_names(doc)
        try:
            llm_ok = bool(self.llm_client and self.llm_client.available())
        except Exception:  # noqa: BLE001
            llm_ok = False

        diagrams: List[Diagram] = []
        usage: List[Dict[str, Any]] = []

        for view in AXIOM_BLUEPRINT_VIEWS:
            t0 = time.perf_counter()
            diagram = deterministic.get(view.key) or Diagram(
                view=view.key, label=view.label, diagram_type=view.diagram_type, status="EMPTY",
            )
            discard: Optional[str] = None

            if llm_ok:
                proposed, discard = self._try_llm_layer(doc, view, canonical)
                if proposed is not None:
                    diagram = proposed  # model-grounded diagram accepted

            # A RENDERED diagram whose mermaid doesn't validate must never ship.
            if diagram.status == "RENDERED" and not validate_mermaid(diagram.code):
                discard = discard or "invalid_structure"
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

    @staticmethod
    def _canonical_names(doc: SolutionDocument) -> Dict[str, str]:
        """Lowercased-name → canonical-name for every real entity/actor. The
        grounding set the guard checks node ids against."""
        canon: Dict[str, str] = {}
        for e in (getattr(doc, "typed_entities", None) or []):
            name = e.get("name") if isinstance(e, dict) else str(e)
            if name and name.lower() not in canon:
                canon[name.lower()] = name
        for name in (list(doc.domain_entities or []) + list(doc.actors or [])):
            if name and name.lower() not in canon:
                canon[name.lower()] = name
        return canon

    def _try_llm_layer(self, doc, view, canonical) -> Tuple[Optional[Diagram], Optional[str]]:
        """Propose → guard → emit for one layer. Returns (Diagram, None) on
        success or (None, discard_reason) so the caller falls back."""
        from inference.local_llm import propose_diagram_structure

        prims = AXIOM_LAYER_PRIMITIVES.get(view.key, ())
        try:
            struct = propose_diagram_structure(
                self.llm_client, layer=view.key, intent=view.intent,
                diagram_type=view.diagram_type,
                typed_entities=list(getattr(doc, "typed_entities", None) or []),
                relationships=list(getattr(doc, "relationships", None) or []),
                allowed_primitives=list(prims),
            )
        except Exception:  # noqa: BLE001 — fail soft to deterministic
            return None, "exception"
        if not struct:
            return None, "no_json"

        # Grounding set = real entities/actors ∪ this layer's permitted primitives.
        allowed = dict(canonical)
        for p in prims:
            allowed[p.lower()] = p

        node_names: List[str] = []
        seen = set()
        for n in struct.get("nodes", []):
            nid = (n.get("id") if isinstance(n, dict) else str(n)) or ""
            key = nid.strip().lower()
            if not key:
                continue
            if key not in allowed:
                return None, "ungrounded_node"   # strict guard → whole layer falls back
            canon = allowed[key]
            if canon.lower() not in seen:
                seen.add(canon.lower())
                node_names.append(canon)
        if not node_names:
            return None, "empty"

        node_set = {n.lower() for n in node_names}
        edges: List[Dict[str, str]] = []
        for e in struct.get("edges", []):
            if not isinstance(e, dict):
                continue
            s = allowed.get((e.get("source") or "").strip().lower())
            t = allowed.get((e.get("target") or "").strip().lower())
            if s and t and s != t and s.lower() in node_set and t.lower() in node_set:
                edges.append({"source": s, "target": t, "type": str(e.get("type", "") or "")})

        code = emit_mermaid(view.diagram_type, node_names, edges)
        if not validate_mermaid(code):
            return None, "invalid_structure"

        model = getattr(getattr(self.llm_client, "config", None), "model", "local-llm")
        return Diagram(
            view=view.key, label=view.label, diagram_type=view.diagram_type,
            code=code, nodes=node_names, provider_used=f"local-llm:{model}",
            grounded=True, status="RENDERED",
        ), None
