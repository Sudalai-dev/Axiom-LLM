"""
Blueprint builder — assembles AXIOM's diagrams-only output.

Maps the deterministic per-layer diagrams (ocif/project_diagrams.py) onto the
locked view contract (ocif/blueprint_config.py), producing exactly one grounded
``Diagram`` per OCIF layer. This is the deterministic path (provider
``internal-builder``); Phase 4 will let the local model propose diagram
structure while still emitting through the same contract and grounding guard.

Grounding (invariant B2/B3): a diagram's ``nodes`` are the request's real
extracted entities (domain entities + actors) that actually appear in the
diagram — never invented. A layer with no such entities present is marked
``EMPTY`` rather than filled with generic placeholders.
"""

from typing import List

from ocif.blueprint_config import AXIOM_BLUEPRINT_VIEWS
from ocif.frames import Blueprint, Diagram, SolutionDocument
from ocif.project_diagrams import build_project_diagrams


def _grounded_nodes(code: str, doc: SolutionDocument) -> List[str]:
    """The request's real entities/actors that appear in this diagram — the
    grounded node set. Order-preserving, de-duplicated, case-insensitive match."""
    if not code:
        return []
    pool = list(dict.fromkeys((doc.domain_entities or []) + (doc.actors or [])))
    low = code.lower()
    return [e for e in pool if e and e.lower() in low]


def build_blueprint(doc: SolutionDocument) -> Blueprint:
    """Build the 8-diagram Blueprint (one per configured OCIF layer) from a
    finished SolutionDocument. Never fabricates: a layer with no diagram content
    is emitted as an honest EMPTY entry so the response always has exactly the
    configured number of views."""
    by_stage = {d.stage: d for d in build_project_diagrams(doc)}
    diagrams: List[Diagram] = []
    for view in AXIOM_BLUEPRINT_VIEWS:
        pd = by_stage.get(view.key)
        code = (pd.mermaid if pd else "") or ""
        # A diagram with only its header line (e.g. "flowchart LR") is empty.
        has_body = len(code.strip().splitlines()) > 1
        nodes = _grounded_nodes(code, doc)
        diagrams.append(Diagram(
            view=view.key,
            label=view.label,
            diagram_type=view.diagram_type,
            code=code,
            nodes=nodes,
            provider_used="internal-builder",
            grounded=True,   # deterministic builders derive from validated fields only
            status="RENDERED" if has_body else "EMPTY",
        ))
    return Blueprint(diagrams=diagrams)
