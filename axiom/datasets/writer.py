"""
Writer Module — Axiom Dataset Generation Platform.

Handles exporting lists of structured dataset records into CSV, JSON, JSONL,
YAML, Markdown, SQLite, and Parquet. It creates output directories dynamically
and flattens nested structures for table-compatible formats (CSV, SQLite).
"""

import os
import json
import csv
import sqlite3
from typing import Any, Dict, List, Optional

# Optional imports for Parquet support
try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False


def flatten_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Flattens nested dictionaries and lists into JSON-serialized strings for tabular formats."""
    flat = {}
    for k, v in record.items():
        if isinstance(v, (dict, list)):
            flat[k] = json.dumps(v)
        else:
            flat[k] = v
    return flat


def dump_yaml(data: Any, indent: int = 0) -> str:
    """Pure-python minimal YAML dumper to avoid external pyyaml dependencies."""
    lines = []
    spaces = " " * indent
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{spaces}{k}:")
                lines.append(dump_yaml(v, indent + 2))
            else:
                # Escape strings if they contain newlines or quotes
                if isinstance(v, str) and ("\n" in v or ":" in v or "#" in v):
                    lines.append(f'{spaces}{k}: "{v}"')
                else:
                    lines.append(f"{spaces}{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{spaces}-")
                lines.append(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{spaces}- {item}")
    return "\n".join(lines)


class DatasetWriter:
    """Handles writing structured records to various formats."""

    @staticmethod
    def write(records: List[Dict[str, Any]], format_type: str, file_path: str) -> None:
        """Writes records in the specified format to the target file path."""
        if not records:
            return

        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        format_type = format_type.strip().lower()

        if format_type == "json":
            DatasetWriter.write_json(records, file_path)
        elif format_type == "jsonl":
            DatasetWriter.write_jsonl(records, file_path)
        elif format_type == "csv":
            DatasetWriter.write_csv(records, file_path)
        elif format_type == "yaml":
            DatasetWriter.write_yaml(records, file_path)
        elif format_type == "markdown" or format_type == "md":
            DatasetWriter.write_markdown(records, file_path)
        elif format_type == "sqlite" or format_type == "db":
            DatasetWriter.write_sqlite(records, file_path)
        elif format_type == "parquet":
            DatasetWriter.write_parquet(records, file_path)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

    @staticmethod
    def write_json(records: List[Dict[str, Any]], file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    @staticmethod
    def write_jsonl(records: List[Dict[str, Any]], file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def write_csv(records: List[Dict[str, Any]], file_path: str) -> None:
        flat_records = [flatten_record(r) for r in records]
        headers = list(flat_records[0].keys())
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(flat_records)

    @staticmethod
    def write_yaml(records: List[Dict[str, Any]], file_path: str) -> None:
        content = dump_yaml(records)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")

    @staticmethod
    def write_markdown(records: List[Dict[str, Any]], file_path: str) -> None:
        """Writes records as readable, documentation-style markdown files."""
        lines = ["# Generated Engineering Dataset", ""]
        for idx, record in enumerate(records, 1):
            lines.append(f"## Record #{idx} (ID: {record.get('id', 'N/A')})")
            lines.append(f"- **Intent**: {record.get('intent', 'N/A')}")
            lines.append(f"- **Domain**: {record.get('domain', 'N/A')}")
            lines.append(f"- **Industry**: {record.get('industry', 'N/A')}")
            lines.append(f"- **Complexity**: {record.get('complexity', 'N/A')}")
            lines.append(f"- **Confidence**: {record.get('confidence', 'N/A')}")
            lines.append("")
            
            # Print remaining fields
            for k, v in record.items():
                if k in ("id", "intent", "domain", "industry", "complexity", "confidence"):
                    continue
                lines.append(f"### {k.capitalize().replace('_', ' ')}")
                if isinstance(v, list):
                    for item in v:
                        lines.append(f"- {item}")
                elif isinstance(v, dict):
                    lines.append("```json")
                    lines.append(json.dumps(v, indent=2, ensure_ascii=False))
                    lines.append("```")
                else:
                    lines.append(str(v))
                lines.append("")
            lines.append("---")
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    @staticmethod
    def write_sqlite(records: List[Dict[str, Any]], file_path: str) -> None:
        """Inserts records into a structured SQLite database."""
        flat_records = [flatten_record(r) for r in records]
        headers = list(flat_records[0].keys())

        # Determine table name based on parent folder or default to 'dataset_records'
        table_name = os.path.basename(os.path.dirname(file_path)) or "dataset_records"
        if table_name.strip().isdigit() or not table_name:
            table_name = "records"
            
        # SQLite sanitization: remove leading digits/underscores, replace invalid chars
        import re as _re
        table_name = table_name.replace("-", "_").replace(" ", "_")
        table_name = _re.sub(r"^\d+_?", "", table_name)  # strip leading "07_" etc.
        if not table_name:
            table_name = "records"

        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()

        # Build CREATE TABLE dynamically
        cols = []
        for h in headers:
            cols.append(f'"{h}" TEXT')
        create_sql = f'CREATE TABLE IF NOT EXISTS {table_name} ({", ".join(cols)})'
        cursor.execute(create_sql)

        # Clear existing table data to prevent duplicate inserts on regenerate
        cursor.execute(f"DELETE FROM {table_name}")

        # Build INSERT
        placeholders = ", ".join(["?"] * len(headers))
        cols_name = ", ".join([f'"{h}"' for h in headers])
        insert_sql = f"INSERT INTO {table_name} ({cols_name}) VALUES ({placeholders})"

        values = []
        for r in flat_records:
            values.append(tuple(str(r.get(h, "")) for h in headers))

        cursor.executemany(insert_sql, values)
        conn.commit()
        conn.close()

    @staticmethod
    def write_parquet(records: List[Dict[str, Any]], file_path: str) -> None:
        """Saves records as a Parquet binary dataset. Falls back to CSV/JSON warning if dependencies are missing."""
        if not HAS_PARQUET:
            logger.warning(
                f"Skipping Parquet generation for {file_path}. "
                "Optional dependencies 'pandas' and 'pyarrow' are missing. "
                "To enable, run: pip install pandas pyarrow"
            )
            # Safe fallback: write JSON and CSV versions beside it
            DatasetWriter.write_json(records, file_path + ".fallback.json")
            return

        flat_records = [flatten_record(r) for r in records]
        df = pd.DataFrame(flat_records)
        # Convert all columns to string to handle heterogeneous schemas easily
        for col in df.columns:
            df[col] = df[col].astype(str)
            
        table = pa.Table.from_pandas(df)
        pq.write_table(table, file_path)
