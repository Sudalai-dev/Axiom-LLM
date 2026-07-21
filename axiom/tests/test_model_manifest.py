"""Phase 11 — model manifest provenance + promotion gate.

A fine-tuned model is promotable only when a human approved it AND it was
trained on real data — no automated pipeline can ship an unreviewed model.
"""

import json

from training.model_manifest import ModelManifest, load_manifest, write_manifest


def _m(**over):
    base = dict(
        model_name="axiom-qwen2.5:3b",
        base_model="Qwen/Qwen2.5-3B-Instruct",
        dataset_path="data/diagram_dataset.jsonl",
        dataset_examples=1319,
        created_at="2026-07-21T00:00:00+00:00",
    )
    base.update(over)
    return ModelManifest(**base)


def test_unapproved_model_is_not_promotable():
    assert _m(approved_by=None).is_promotable() is False


def test_approved_model_with_data_is_promotable():
    m = _m(approved_by="admin", approval_ref="mcp-123")
    assert m.is_promotable() is True


def test_approved_but_empty_dataset_is_not_promotable():
    assert _m(approved_by="admin", dataset_examples=0).is_promotable() is False


def test_manifest_round_trips(tmp_path):
    m = _m(approved_by="admin", hyperparameters={"lora_r": 16}, gguf_quantization="Q4_K_M")
    path = str(tmp_path / "model_manifest.json")
    write_manifest(path, m)
    loaded = load_manifest(path)
    assert loaded == m
    assert json.load(open(path, encoding="utf-8"))["approved_by"] == "admin"
