"""
Model manifest (Phase 11).

A small, dependency-free provenance record for a fine-tuned AXIOM diagram model:
what base model + which dataset + which hyperparameters produced it, and — the
governance hook (Phase 12) — WHO approved its promotion. A model without a
recorded human approver is never considered promotable: ``is_promotable()``
returns False, so no automated pipeline can ship a model nobody signed off on.

Offline / admin-run. Not imported by the serving platform.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ModelManifest:
    model_name: str                       # e.g. "axiom-qwen2.5:3b"
    base_model: str                       # e.g. "Qwen/Qwen2.5-3B-Instruct"
    dataset_path: str
    dataset_examples: int
    dataset_manifest: Dict[str, Any] = field(default_factory=dict)  # Phase-10 export manifest
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    gguf_quantization: str = ""
    created_at: str = ""                  # ISO-8601, supplied by the caller (no wall-clock here)
    # Governance (Phase 12): promotion requires a human sign-off.
    approved_by: Optional[str] = None
    approval_ref: Optional[str] = None    # e.g. the governance ModelChangeProposal id
    notes: str = ""

    def is_promotable(self) -> bool:
        """True only when a human has approved this model AND it was trained on a
        non-empty dataset. Guards against auto-promoting an unreviewed model."""
        return bool(self.approved_by) and self.dataset_examples > 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def write_manifest(path: str, manifest: ModelManifest) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest.to_dict(), fh, indent=2)


def load_manifest(path: str) -> ModelManifest:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return ModelManifest(**data)
