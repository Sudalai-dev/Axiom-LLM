"""
Blueprint view configuration — the single source of truth for AXIOM's
diagram-only output contract.

AXIOM's user-facing response is an Octagonal Blueprint: exactly one diagram per
OCIF layer. The layer set here is LOCKED to the real cognitive engines
(``EngineName`` in ocif/frames.py) — Perception · Context · Planning · Knowledge
· Memory · Reasoning · Validation · Experience — not an invented set. Every
value the diagram pipeline needs (which views, their order, the mermaid diagram
type per view, and the per-view transformation intent used to prompt the diagram
model) lives here as named config, validated at import, so there are no magic
literals scattered through the code paths.

Swap the whole set (e.g. to a SyRS taxonomy) by editing ``AXIOM_BLUEPRINT_VIEWS``
and ``AXIOM_VIEW_DIAGRAM_INTENT`` here, or override the order at deploy time with
the ``AXIOM_BLUEPRINT_VIEWS`` env var (comma-separated view keys). No other code
change is required.
"""

import os
from dataclasses import dataclass
from typing import Dict, List

from ocif.frames import EngineName


@dataclass(frozen=True)
class BlueprintView:
    """One OCIF layer's diagram spec."""
    key: str            # canonical layer key (must be an EngineName value)
    label: str          # human-facing octagon label
    diagram_type: str   # mermaid family the deterministic emitter renders
    intent: str         # what THIS layer's diagram shows (drives Phase-4 prompting)


# Mermaid diagram families AXIOM's deterministic emitter can render. The view
# config's diagram_type must be one of these (validated below).
AXIOM_DIAGRAM_TYPES = frozenset({
    "flowchart", "sequence", "state", "er", "class", "mindmap",
})

# The 8 views, in OCIF pipeline order. diagram_type is aligned with what the
# deterministic builders in ocif/project_diagrams.py already emit, so the
# contract holds whether a diagram comes from the model (Phase 4) or the
# deterministic fallback.
AXIOM_BLUEPRINT_VIEWS: List[BlueprintView] = [
    BlueprintView("perception", "Perception", "state",
                  "How the request's entities enter and are recognised — the delivery lifecycle states they move through."),
    BlueprintView("context", "Context", "flowchart",
                  "How actors and inputs feed the system — entities flowing from sources into intake."),
    BlueprintView("planning", "Planning", "flowchart",
                  "How data moves end-to-end across the entities — the request's dataflow."),
    BlueprintView("knowledge", "Knowledge", "er",
                  "The core data model — the request's entities and the relationships between them."),
    BlueprintView("memory", "Memory", "sequence",
                  "The runtime interaction sequence between the request's actors and services."),
    BlueprintView("reasoning", "Reasoning", "class",
                  "The solution structure — the request's entities modelled as cooperating components."),
    BlueprintView("validation", "Validation", "mindmap",
                  "Coverage of the entities across risk, testing and monitoring concerns."),
    BlueprintView("experience", "Experience", "flowchart",
                  "How actors navigate and operate the system — the user/operational journey."),
]

# Per-view transformation intent, keyed by view (drives the Phase-4 facts packet).
AXIOM_VIEW_DIAGRAM_INTENT: Dict[str, str] = {v.key: v.intent for v in AXIOM_BLUEPRINT_VIEWS}


def _apply_env_override(views: List[BlueprintView]) -> List[BlueprintView]:
    """Optional deploy-time reordering/subsetting via AXIOM_BLUEPRINT_VIEWS
    (comma-separated view keys). Unknown keys are rejected at validation."""
    raw = os.getenv("AXIOM_BLUEPRINT_VIEWS", "").strip()
    if not raw:
        return views
    wanted = [k.strip() for k in raw.split(",") if k.strip()]
    by_key = {v.key: v for v in views}
    missing = [k for k in wanted if k not in by_key]
    if missing:
        raise ValueError(f"AXIOM_BLUEPRINT_VIEWS names unknown view(s): {missing}")
    return [by_key[k] for k in wanted]


def _validate(views: List[BlueprintView]) -> None:
    """Fail fast at import if the view config is inconsistent with the real
    OCIF layer set — the contract must never drift onto invented layers."""
    engine_values = {e.value for e in EngineName}
    keys = [v.key for v in views]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate blueprint view keys: {keys}")
    bad_layers = [k for k in keys if k not in engine_values]
    if bad_layers:
        raise ValueError(
            f"Blueprint views must be real OCIF layers {sorted(engine_values)}; "
            f"got unknown: {bad_layers}"
        )
    bad_types = [v.diagram_type for v in views if v.diagram_type not in AXIOM_DIAGRAM_TYPES]
    if bad_types:
        raise ValueError(f"Unknown diagram_type(s) {bad_types}; allowed: {sorted(AXIOM_DIAGRAM_TYPES)}")


AXIOM_BLUEPRINT_VIEWS = _apply_env_override(AXIOM_BLUEPRINT_VIEWS)
_validate(AXIOM_BLUEPRINT_VIEWS)

# Convenience accessors (no literals at call sites).
BLUEPRINT_VIEW_KEYS: List[str] = [v.key for v in AXIOM_BLUEPRINT_VIEWS]
BLUEPRINT_VIEWS_BY_KEY: Dict[str, BlueprintView] = {v.key: v for v in AXIOM_BLUEPRINT_VIEWS}
BLUEPRINT_VIEW_COUNT: int = len(AXIOM_BLUEPRINT_VIEWS)
