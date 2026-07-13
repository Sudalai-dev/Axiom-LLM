"""
Axiom Dataset Generation Platform.

Enterprise-grade engineering dataset generator for AXIOM's Engineering
Intelligence Engine, Knowledge Engine, Memory Engine, and future fine-tuning.

Submodules:
    registry    — Seed vocabularies, templates, and 30 dataset generators
    writer      — Multi-format exporters (JSON, JSONL, CSV, YAML, MD, SQLite, Parquet)
    validator   — Schema checking, duplicate detection, cross-field consistency
    ingestion   — Company knowledge document processing pipeline
    generator   — CLI orchestrator

Usage:
    python -m datasets.generator --help
    python -m datasets.generator --dataset all --count 1000 --format json csv
"""

from datasets.registry import ALL_DATASET_IDS, DATASET_GENERATORS
from datasets.writer import DatasetWriter
from datasets.validator import DatasetValidator
from datasets.ingestion import IngestionPipeline

__all__ = [
    "ALL_DATASET_IDS",
    "DATASET_GENERATORS",
    "DatasetWriter",
    "DatasetValidator",
    "IngestionPipeline",
]
