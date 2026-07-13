"""
Generator CLI — Axiom Dataset Generation Platform.

Command-line interface for generating, validating, and exporting engineering
datasets at configurable scale.

Usage:
    python -m datasets.generator --dataset all --count 1000 --format json
    python -m datasets.generator --dataset 01_intent_detection --count 5000 --format csv jsonl sqlite
    python -m datasets.generator --dataset 07_solution_blueprints --count 10000 --format parquet
    python -m datasets.generator --list
    python -m datasets.generator --ingest /path/to/company/docs --format json

Options:
    --dataset    Dataset ID or 'all'. Use --list to see available IDs.
    --count      Number of records to generate per dataset (default: 1000).
    --format     One or more output formats: json, jsonl, csv, yaml, md, sqlite, parquet.
    --output-dir Base output directory (default: datasets/).
    --validate   Run validation on generated records before writing.
    --seed       Random seed for reproducible generation.
    --list       List all available dataset IDs and exit.
    --ingest     Path to a directory of company documents to ingest.
"""

import argparse
import os
import random
import sys
import time
from typing import List

from datasets.registry import ALL_DATASET_IDS, DATASET_GENERATORS
from datasets.validator import DatasetValidator
from datasets.writer import DatasetWriter


FORMAT_EXTENSIONS = {
    "json": ".json",
    "jsonl": ".jsonl",
    "csv": ".csv",
    "yaml": ".yaml",
    "md": ".md",
    "markdown": ".md",
    "sqlite": ".db",
    "db": ".db",
    "parquet": ".parquet",
}


def _resolve_format(fmt: str) -> str:
    """Normalize format name to canonical key."""
    return fmt.strip().lower().replace("markdown", "md")


def generate_dataset(dataset_id: str, count: int, output_dir: str,
                     formats: List[str], validate: bool = True) -> dict:
    """Generate a single dataset and write to requested formats.
    Returns a summary dict with counts and timing."""
    generator = DATASET_GENERATORS.get(dataset_id)
    if generator is None:
        print(f"  [ERROR] Unknown dataset ID: {dataset_id}")
        return {"dataset": dataset_id, "status": "error", "reason": "unknown_id"}

    print(f"  Generating {count:,} records for {dataset_id}...")
    t0 = time.time()
    records = generator(count)
    gen_time = time.time() - t0
    print(f"    Generated {len(records):,} records in {gen_time:.2f}s")

    # Validation
    validation_errors = {}
    if validate:
        validator = DatasetValidator()
        all_valid, batch_errors = validator.validate_batch(records)
        if not all_valid:
            validation_errors = batch_errors
            print(f"    [WARN] {len(batch_errors)} records have validation issues")
        else:
            print(f"    [OK] All records passed validation")

    # Write to each requested format
    dataset_dir = os.path.join(output_dir, dataset_id)
    os.makedirs(dataset_dir, exist_ok=True)

    for fmt in formats:
        fmt_key = _resolve_format(fmt)
        ext = FORMAT_EXTENSIONS.get(fmt_key, f".{fmt_key}")
        file_path = os.path.join(dataset_dir, f"data{ext}")

        try:
            DatasetWriter.write(records, fmt_key, file_path)
            file_size = os.path.getsize(file_path)
            print(f"    Written {fmt_key.upper():>8}: {file_path} ({file_size:,} bytes)")
        except Exception as e:
            print(f"    [ERROR] Failed to write {fmt_key}: {e}")

    return {
        "dataset": dataset_id,
        "status": "success",
        "record_count": len(records),
        "generation_time_s": round(gen_time, 2),
        "validation_errors": len(validation_errors),
        "formats_written": formats,
    }


def run_ingestion(source_dir: str, output_dir: str, formats: List[str]) -> None:
    """Run the company knowledge ingestion pipeline."""
    from datasets.ingestion import IngestionPipeline

    print(f"\n{'='*60}")
    print(f"  COMPANY KNOWLEDGE INGESTION")
    print(f"  Source: {source_dir}")
    print(f"{'='*60}")

    pipeline = IngestionPipeline(source_dir)
    file_paths = pipeline.scan()
    print(f"  Found {len(file_paths)} supported files")

    if not file_paths:
        print("  No supported files found. Exiting.")
        return

    records = pipeline.ingest(file_paths)
    print(f"  Ingested {len(records)} records")

    dataset_dir = os.path.join(output_dir, "26_company_knowledge")
    os.makedirs(dataset_dir, exist_ok=True)

    for fmt in formats:
        fmt_key = _resolve_format(fmt)
        ext = FORMAT_EXTENSIONS.get(fmt_key, f".{fmt_key}")
        file_path = os.path.join(dataset_dir, f"ingested{ext}")
        DatasetWriter.write(records, fmt_key, file_path)
        print(f"    Written {fmt_key.upper():>8}: {file_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="axiom-dataset-generator",
        description="AXIOM Engineering Dataset Generation Platform",
    )
    parser.add_argument("--dataset", type=str, default="all",
                        help="Dataset ID to generate (e.g. '01_intent_detection') or 'all'")
    parser.add_argument("--count", type=int, default=1000,
                        help="Number of records to generate per dataset")
    parser.add_argument("--format", nargs="+", default=["json"],
                        help="Output formats: json, jsonl, csv, yaml, md, sqlite, parquet")
    parser.add_argument("--output-dir", type=str, default="datasets",
                        help="Base output directory")
    parser.add_argument("--validate", action="store_true", default=True,
                        help="Validate generated records")
    parser.add_argument("--no-validate", action="store_true",
                        help="Skip validation")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible generation")
    parser.add_argument("--list", action="store_true",
                        help="List all available dataset IDs and exit")
    parser.add_argument("--ingest", type=str, default=None,
                        help="Path to company documents directory to ingest")

    args = parser.parse_args()

    if args.list:
        print("\nAvailable Dataset IDs:")
        print("-" * 40)
        for did in ALL_DATASET_IDS:
            print(f"  {did}")
        print(f"\nTotal: {len(ALL_DATASET_IDS)} datasets")
        return

    if args.seed is not None:
        random.seed(args.seed)
        print(f"Random seed set to {args.seed}")

    validate = not args.no_validate

    # Ingestion mode
    if args.ingest:
        run_ingestion(args.ingest, args.output_dir, args.format)
        return

    # Generation mode
    if args.dataset == "all":
        dataset_ids = ALL_DATASET_IDS
    else:
        dataset_ids = [d.strip() for d in args.dataset.split(",")]

    print(f"\n{'='*60}")
    print(f"  AXIOM ENGINEERING DATASET GENERATION PLATFORM")
    print(f"  Datasets:    {len(dataset_ids)}")
    print(f"  Count/each:  {args.count:,}")
    print(f"  Formats:     {', '.join(args.format)}")
    print(f"  Output:      {os.path.abspath(args.output_dir)}")
    print(f"  Validation:  {'enabled' if validate else 'disabled'}")
    print(f"{'='*60}\n")

    total_start = time.time()
    summaries = []

    for idx, did in enumerate(dataset_ids, 1):
        print(f"[{idx}/{len(dataset_ids)}] {did}")
        summary = generate_dataset(did, args.count, args.output_dir, args.format, validate)
        summaries.append(summary)
        print()

    total_time = time.time() - total_start
    total_records = sum(s.get("record_count", 0) for s in summaries)
    total_errors = sum(s.get("validation_errors", 0) for s in summaries)

    print(f"{'='*60}")
    print(f"  GENERATION COMPLETE")
    print(f"  Total records:  {total_records:,}")
    print(f"  Total time:     {total_time:.2f}s")
    print(f"  Records/second: {total_records / max(total_time, 0.01):,.0f}")
    print(f"  Validation issues: {total_errors:,}")
    print(f"{'='*60}")

    # Write generation metadata
    import json
    meta_dir = os.path.join(args.output_dir, "metadata")
    os.makedirs(meta_dir, exist_ok=True)
    meta_path = os.path.join(meta_dir, "generation_report.json")
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_records": total_records,
        "total_time_seconds": round(total_time, 2),
        "datasets": summaries,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report written to: {meta_path}")


if __name__ == "__main__":
    main()
