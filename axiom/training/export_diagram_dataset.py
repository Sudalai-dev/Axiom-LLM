"""
Diagram dataset exporter (Phase 10).

Turns AXIOM's OWN validated, grounded diagram structures — persisted in the
learning store by every accepted solution (Phase 6) — into a supervised
fine-tuning dataset for the local diagram model. Each example is a chat triple
in EXACTLY the format live inference uses (inference.local_llm.DIAGRAM_SYSTEM_PROMPT
+ diagram_facts_prompt), so a model trained on it behaves identically at serving
time.

No fabrication: only RENDERED layers with real grounded nodes are exported; the
target structure is reconstructed deterministically from the stored node set
(typed via ocif.entity_typing) plus edges re-derived from those same nodes. An
empty store yields an empty dataset, never invented examples.

Offline / admin-run. Not imported by the serving platform. CLI:

    python -m training.export_diagram_dataset --out data/diagram_dataset.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from inference.local_llm import DIAGRAM_SYSTEM_PROMPT, diagram_facts_prompt
from memory.learning_store import LearningStore
from ocif.blueprint_config import AXIOM_LAYER_PRIMITIVES, BLUEPRINT_VIEWS_BY_KEY
from ocif.entity_typing import build_typed_entities, classify_entity, derive_relationships


@dataclass
class ExportManifest:
    """Provenance of one export run (written next to the dataset)."""
    examples: int = 0
    records_seen: int = 0
    records_with_diagrams: int = 0
    views: Dict[str, int] = field(default_factory=dict)
    source: str = "learning_store"
    format: str = "chat-jsonl"       # {"messages":[system,user,assistant]} per line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "examples": self.examples,
            "records_seen": self.records_seen,
            "records_with_diagrams": self.records_with_diagrams,
            "views": dict(self.views),
            "source": self.source,
            "format": self.format,
        }


def _target_structure(nodes: List[str], relationships: List[Dict[str, str]]) -> Dict[str, Any]:
    """The assistant target: the grounded node set (typed) + edges restricted to
    those nodes. Deterministic — mirrors what the guard would accept."""
    node_set = {n.lower() for n in nodes}
    edges = [
        {"source": r["source"], "target": r["target"], "type": r.get("type", "")}
        for r in relationships
        if r.get("source", "").lower() in node_set and r.get("target", "").lower() in node_set
        and r["source"] != r["target"]
    ]
    return {
        "nodes": [{"id": n, "type": classify_entity(n)} for n in nodes],
        "edges": edges,
    }


def _examples_for_record(record) -> List[Dict[str, Any]]:
    """Build one chat example per RENDERED, grounded layer of a learning record."""
    typed = build_typed_entities(list(record.entities or []), actors=[])
    relationships = derive_relationships(typed)
    out: List[Dict[str, Any]] = []
    for diagram in (record.diagrams or []):
        view = diagram.get("view")
        nodes = [n for n in (diagram.get("nodes") or []) if n]
        spec = BLUEPRINT_VIEWS_BY_KEY.get(view)
        if not view or not nodes or spec is None:
            continue  # skip empty/unknown layers — never fabricate
        user = diagram_facts_prompt(
            layer=view,
            intent=spec.intent,
            diagram_type=diagram.get("diagram_type") or spec.diagram_type,
            typed_entities=typed,
            relationships=relationships,
            allowed_primitives=list(AXIOM_LAYER_PRIMITIVES.get(view, ())),
        )
        target = _target_structure(nodes, relationships)
        out.append({
            "messages": [
                {"role": "system", "content": DIAGRAM_SYSTEM_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
            ],
            "view": view,
        })
    return out


def export_diagram_dataset(
    store: LearningStore,
    out_path: str,
    *,
    user_id: Optional[str] = None,
    project: Optional[str] = None,
) -> ExportManifest:
    """Export validated diagram structures from ``store`` to ``out_path`` (JSONL).

    Optionally scope to one user/project; by default exports every record. Writes
    a ``<out_path>.manifest.json`` alongside. Returns the manifest.
    """
    manifest = ExportManifest()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as fh:
        for record in store.iter_records(user_id=user_id, project=project):
            manifest.records_seen += 1
            if not record.diagrams:
                continue
            manifest.records_with_diagrams += 1
            for ex in _examples_for_record(record):
                view = ex.pop("view")
                fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
                manifest.examples += 1
                manifest.views[view] = manifest.views.get(view, 0) + 1

    with open(out_path + ".manifest.json", "w", encoding="utf-8") as mf:
        json.dump(manifest.to_dict(), mf, indent=2)
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export AXIOM's validated diagram structures as a fine-tuning dataset.")
    parser.add_argument("--out", default="data/diagram_dataset.jsonl", help="Output JSONL path")
    parser.add_argument("--db", default=None, help="LearningStore DB path (default: AXIOM_DATA_DIR/learning_memory.db)")
    parser.add_argument("--user", default=None, help="Restrict to one user_id")
    parser.add_argument("--project", default=None, help="Restrict to one project")
    args = parser.parse_args(argv)

    store = LearningStore(db_path=args.db)
    manifest = export_diagram_dataset(store, args.out, user_id=args.user, project=args.project)
    print(f"Wrote {manifest.examples} example(s) from {manifest.records_with_diagrams} "
          f"record(s) -> {args.out}")
    print(f"Manifest: {args.out}.manifest.json")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
