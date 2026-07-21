# Fine-tuning AXIOM's local diagram model (offline, admin-run)

AXIOM ships with a deterministic diagram engine that never needs a model. The
optional local model (`axiom-qwen2.5:3b` via Ollama) only *proposes* per-layer
diagram structure; the emitter and grounding guard stay deterministic. This
runbook improves that proposal step by fine-tuning the base model on AXIOM's
**own validated, grounded output**.

Nothing here runs inside the serving platform. It is a deliberate, human-run
pipeline. Config lives in [`training/finetune_config.json`](../training/finetune_config.json).

## Pipeline

```
LearningStore (validated diagrams, Phase 6)
  → export dataset          (training/export_diagram_dataset.py)      Phase 10
  → QLoRA fine-tune          (peft + trl on the base model)
  → merge adapter            (peft merge_and_unload)
  → convert + quantize GGUF  (llama.cpp)
  → Ollama Modelfile         (inference/axiom.Modelfile)
  → HUMAN APPROVAL           (governance gate — Phase 12, no auto-promote)
  → ollama create            (promote to axiom-qwen2.5:3b)
```

### 1. Export the dataset (Phase 10)

```bash
python -m training.export_diagram_dataset --out data/diagram_dataset.jsonl
```

Produces chat-JSONL in the exact format inference uses (system =
`DIAGRAM_SYSTEM_PROMPT`, user = the facts packet, assistant = the grounded
structure) plus `…​.manifest.json`. Only validated, grounded layers are
exported — no fabrication. Require at least `dataset.min_examples` (200) rows.

### 2. QLoRA fine-tune

Install the trainer toolchain in a **separate** environment (GPU box), not in
the serving venv:

```bash
pip install "transformers>=4.44" "peft>=0.12" "trl>=0.9" "bitsandbytes>=0.43" datasets accelerate
```

Load 4-bit (`qlora.quantization: nf4`), attach a LoRA adapter to the
`target_modules`, and train with the `train` block hyperparameters on the
exported JSONL. Fixed `seed: 7` for reproducibility.

### 3. Merge → GGUF → quantize

```bash
# merge the LoRA adapter into the base weights (peft merge_and_unload) → merged_dir
python llama.cpp/convert_hf_to_gguf.py artifacts/axiom-diagram-merged \
  --outfile artifacts/axiom-diagram.f16.gguf
./llama.cpp/llama-quantize artifacts/axiom-diagram.f16.gguf \
  artifacts/axiom-diagram.Q4_K_M.gguf Q4_K_M
```

### 4. Build the Ollama model

Point [`inference/axiom.Modelfile`](../inference/axiom.Modelfile) at the GGUF
(`FROM ./artifacts/axiom-diagram.Q4_K_M.gguf`) and:

```bash
ollama create axiom-qwen2.5:3b -f inference/axiom.Modelfile
```

Serving picks it up via `OCIF_LLM_MODEL=axiom-qwen2.5:3b` (still off by default —
`OCIF_LLM_ENABLED=true` to turn it on). If the model regresses, the deterministic
engine remains the guaranteed fallback.

## Governance gate (Phase 12 — no auto-retrain)

Promotion is **human-gated**. Record provenance with
[`training/model_manifest.py`](../training/model_manifest.py): base model,
dataset + its manifest, hyperparameters, and — required — `approved_by` /
`approval_ref`. `ModelManifest.is_promotable()` returns False until a human has
approved and the dataset is non-empty. No script in this repo triggers training
or `ollama create` automatically; each step above is run by an operator.
