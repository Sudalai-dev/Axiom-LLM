"""Phase 10 — diagram dataset exporter.

AXIOM's own validated, grounded diagram structures become supervised fine-tuning
examples, in exactly the format live inference uses (train/inference parity).
No fabrication: empty store → empty dataset; only grounded RENDERED layers export.
"""

import json

from inference.local_llm import DIAGRAM_SYSTEM_PROMPT
from memory.learning_store import LearningStore
from training.export_diagram_dataset import export_diagram_dataset


def _seed(store):
    store.record(
        record_id="r1", user_id="u1", project="p1", intent="solution_design",
        entities=["Patient", "Record", "Clinician"], subject="patient portal",
        solution_title="Patient Records Portal", confidence=0.9, tradeoffs=[],
        diagrams=[
            {"view": "knowledge", "nodes": ["Patient", "Record"], "diagram_type": "er"},
            {"view": "planning", "nodes": [], "diagram_type": "flowchart"},   # empty → skipped
        ],
    )


def test_export_produces_parity_examples(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "learn.db"))
    _seed(store)
    out = str(tmp_path / "ds.jsonl")

    manifest = export_diagram_dataset(store, out)

    # Only the RENDERED knowledge layer exports; the empty planning layer is skipped.
    assert manifest.examples == 1
    assert manifest.records_with_diagrams == 1
    assert manifest.views == {"knowledge": 1}

    lines = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
    assert len(lines) == 1
    msgs = lines[0]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant"]
    assert msgs[0]["content"] == DIAGRAM_SYSTEM_PROMPT          # inference parity
    # The assistant target is valid JSON structure grounded ONLY in the request.
    target = json.loads(msgs[2]["content"])
    ids = {n["id"].lower() for n in target["nodes"]}
    assert ids == {"patient", "record"}
    assert all("type" in n for n in target["nodes"])
    # A manifest file is written alongside.
    assert json.load(open(out + ".manifest.json", encoding="utf-8"))["examples"] == 1


def test_empty_store_exports_nothing(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "empty.db"))
    out = str(tmp_path / "ds.jsonl")
    manifest = export_diagram_dataset(store, out)
    assert manifest.examples == 0
    assert open(out, encoding="utf-8").read() == ""


def test_export_never_leaks_cross_request_entities(tmp_path):
    """The assistant target must contain only the record's own grounded nodes —
    the exporter reconstructs from stored nodes, never invents."""
    store = LearningStore(db_path=str(tmp_path / "learn.db"))
    _seed(store)
    out = str(tmp_path / "ds.jsonl")
    export_diagram_dataset(store, out)
    blob = open(out, encoding="utf-8").read().lower()
    assert "book" not in blob and "turbine" not in blob   # nothing from other domains
