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

    def generate(
        self, doc: SolutionDocument, recalled: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Blueprint, List[Dict[str, Any]]]:
        """Return (Blueprint, diagram_usage).

        Per layer, in order of precedence:
          1. RECALL — if a prior validated solution (``recalled``) has a diagram
             for this layer whose nodes ALL re-ground in THIS request's entities,
             reuse that structure deterministically (fast, consistent, no model
             call). Nodes are re-grounded so a prior request's entities can never
             leak in.
          2. LOCAL MODEL — if available, propose structure, guard every node,
             emit mermaid deterministically, validate.
          3. DETERMINISTIC BUILDER — the always-available fallback.
        Any failure at 1/2 falls through to the next. Every outcome (including
        the provider actually used: recall | local-llm:<model> | internal-builder)
        is recorded in diagram_usage."""
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

            prims = AXIOM_LAYER_PRIMITIVES.get(view.key, ())
            allowed = dict(canonical)   # real entities/actors ∪ this layer's primitives
            for p in prims:
                allowed[p.lower()] = p

            recalled_diagram = self._try_recall_layer(doc, view, allowed, recalled)
            if recalled_diagram is not None:
                diagram = recalled_diagram          # reused prior structure, re-grounded
            elif llm_ok:
                proposed, discard = self._try_llm_layer(doc, view, allowed, prims)
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

    @staticmethod
    def _edges_from_relationships(doc, allowed, node_set) -> List[Dict[str, str]]:
        """Typed edges from THIS request's relationships, restricted to the given
        grounded node set (used when reusing a recalled structure)."""
        edges: List[Dict[str, str]] = []
        for r in (getattr(doc, "relationships", None) or []):
            if not isinstance(r, dict):
                continue
            s = allowed.get((r.get("source") or "").strip().lower())
            t = allowed.get((r.get("target") or "").strip().lower())
            if s and t and s != t and s.lower() in node_set and t.lower() in node_set:
                edges.append({"source": s, "target": t, "type": str(r.get("type", "") or "")})
        return edges

    def _try_recall_layer(self, doc, view, allowed, recalled) -> Optional[Diagram]:
        """Reuse a prior validated diagram's STRUCTURE for this layer when every
        one of its nodes re-grounds in THIS request (so no prior-request entity
        can leak). Edges are re-derived from THIS request's relationships and the
        mermaid is re-emitted deterministically — never replayed from storage.
        Returns a grounded Diagram or None (caller falls through to LLM/builder)."""
        for rec in (recalled or []):
            for d in (rec.get("diagrams") or []):
                if not isinstance(d, dict) or d.get("view") != view.key:
                    continue
                raw = [n for n in (d.get("nodes") or []) if n]
                if not raw or any(n.strip().lower() not in allowed for n in raw):
                    continue  # empty, or a node that doesn't re-ground here
                node_names, seen = [], set()
                for n in raw:
                    canon = allowed[n.strip().lower()]
                    if canon.lower() not in seen:
                        seen.add(canon.lower())
                        node_names.append(canon)
                node_set = {n.lower() for n in node_names}
                edges = self._edges_from_relationships(doc, allowed, node_set)
                code = emit_mermaid(view.diagram_type, node_names, edges)
                if validate_mermaid(code):
                    return Diagram(
                        view=view.key, label=view.label, diagram_type=view.diagram_type,
                        code=code, nodes=node_names, provider_used="recall",
                        grounded=True, status="RENDERED",
                    )
        return None

    def _try_llm_layer(self, doc, view, allowed, prims) -> Tuple[Optional[Diagram], Optional[str]]:
        """Propose → guard → emit for one layer. Returns (Diagram, None) on
        success or (None, discard_reason) so the caller falls back. ``allowed``
        is the grounding map (real entities/actors ∪ this layer's primitives)."""
        from inference.local_llm import propose_diagram_structure

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
