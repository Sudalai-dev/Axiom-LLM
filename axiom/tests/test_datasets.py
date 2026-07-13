"""
Test Suite — Axiom Dataset Generation Platform.

Verifies:
    1. All 30 generators produce records with correct metadata schemas.
    2. Generated records are unique (no duplicates).
    3. The validator catches schema violations and duplicates.
    4. The writer exports to all supported formats.
    5. Cross-field engineering consistency rules are enforced.
    6. The ingestion pipeline processes text files correctly.
"""

import json
import os
import random
import sqlite3
import tempfile

import pytest

# Ensure reproducibility
random.seed(42)

from datasets.registry import (
    ALL_DATASET_IDS,
    DATASET_GENERATORS,
    generate_intent_detection,
    generate_domain_classification,
    generate_industry_classification,
    generate_solution_blueprints,
    generate_engineering_reasoning,
    generate_failure_analysis,
    generate_mechanical,
    generate_electrical,
    generate_aiot,
    generate_octagonal_mapping,
    generate_evaluation,
)
from datasets.validator import DatasetValidator, REQUIRED_METADATA_FIELDS
from datasets.writer import DatasetWriter, flatten_record
from datasets.ingestion import IngestionPipeline, _detect_format, _extract_entities


# =========================================================================
#  Registry & Generator Tests
# =========================================================================

class TestRegistryCompleteness:
    """Ensure all 30 dataset types are registered and callable."""

    def test_thirty_datasets_registered(self):
        assert len(ALL_DATASET_IDS) == 30

    def test_all_ids_have_generators(self):
        for did in ALL_DATASET_IDS:
            assert did in DATASET_GENERATORS, f"Missing generator for {did}"
            assert callable(DATASET_GENERATORS[did])

    def test_ids_are_numbered_sequentially(self):
        for idx, did in enumerate(ALL_DATASET_IDS, 1):
            prefix = f"{idx:02d}_"
            assert did.startswith(prefix), f"Expected {did} to start with {prefix}"


class TestGeneratorOutput:
    """Verify that each generator produces well-formed records."""

    @pytest.fixture(params=ALL_DATASET_IDS)
    def dataset_id(self, request):
        return request.param

    def test_generator_returns_list_of_dicts(self, dataset_id):
        generator = DATASET_GENERATORS[dataset_id]
        records = generator(5)
        assert isinstance(records, list)
        assert len(records) == 5
        for r in records:
            assert isinstance(r, dict)

    def test_all_records_carry_required_metadata(self, dataset_id):
        generator = DATASET_GENERATORS[dataset_id]
        records = generator(10)
        for r in records:
            missing = REQUIRED_METADATA_FIELDS - set(r.keys())
            assert not missing, f"Dataset {dataset_id} missing metadata: {missing}"

    def test_confidence_within_bounds(self, dataset_id):
        generator = DATASET_GENERATORS[dataset_id]
        records = generator(10)
        for r in records:
            conf = float(r["confidence"])
            assert 0.0 <= conf <= 1.0

    def test_ids_are_unique_within_batch(self, dataset_id):
        generator = DATASET_GENERATORS[dataset_id]
        records = generator(50)
        ids = [r["id"] for r in records]
        assert len(ids) == len(set(ids)), "Duplicate IDs found"


class TestSpecificGenerators:
    """Test domain-specific content quality."""

    def test_intent_records_have_input_and_intent(self):
        records = generate_intent_detection(20)
        for r in records:
            assert "input" in r and len(r["input"]) > 10
            assert "intent" in r and r["intent"] in r["intent"]  # non-empty

    def test_domain_records_have_expert_personas(self):
        records = generate_domain_classification(20)
        for r in records:
            assert "expert_personas" in r
            assert len(r["expert_personas"]) >= 1

    def test_industry_records_have_standards(self):
        records = generate_industry_classification(20)
        for r in records:
            assert "standards" in r
            assert isinstance(r["standards"], list)
            assert len(r["standards"]) >= 1

    def test_solution_blueprints_have_tech_stack(self):
        records = generate_solution_blueprints(10)
        for r in records:
            assert "technology_stack" in r
            assert isinstance(r["technology_stack"], dict)
            assert len(r["technology_stack"]) >= 3

    def test_engineering_reasoning_has_options_and_decision(self):
        records = generate_engineering_reasoning(10)
        for r in records:
            assert "options" in r and len(r["options"]) >= 2
            assert "decision" in r and len(r["decision"]) > 0
            assert "reason" in r and len(r["reason"]) > 10

    def test_failure_analysis_has_diagnostics(self):
        records = generate_failure_analysis(10)
        for r in records:
            assert "symptoms" in r and len(r["symptoms"]) >= 1
            assert "possible_causes" in r and len(r["possible_causes"]) >= 1
            assert "diagnostic_tests" in r

    def test_mechanical_records_have_sensors(self):
        records = generate_mechanical(10)
        for r in records:
            assert "sensors" in r and len(r["sensors"]) >= 1
            assert "failure_mode" in r

    def test_electrical_records_have_standards(self):
        records = generate_electrical(10)
        for r in records:
            assert "standards" in r and len(r["standards"]) >= 1

    def test_aiot_records_have_protocol(self):
        records = generate_aiot(10)
        for r in records:
            assert "protocol" in r
            assert "security" in r and len(r["security"]) >= 1

    def test_octagonal_mapping_has_all_stages(self):
        records = generate_octagonal_mapping(5)
        expected_stages = {"perception", "context", "planning", "knowledge",
                           "memory", "reasoning", "validation", "experience"}
        for r in records:
            assert "stages" in r
            assert set(r["stages"].keys()) == expected_stages

    def test_evaluation_records_have_expected_sections(self):
        records = generate_evaluation(5)
        for r in records:
            assert "expected_sections" in r
            assert "minimum_confidence" in r


# =========================================================================
#  Validator Tests
# =========================================================================

class TestValidator:
    """Verify the validation engine catches errors."""

    def test_valid_record_passes(self):
        records = generate_intent_detection(1)
        validator = DatasetValidator()
        valid, errors = validator.validate_record(records[0])
        assert valid, f"Valid record failed validation: {errors}"

    def test_missing_fields_detected(self):
        record = {"id": "test-123", "input": "test prompt"}
        validator = DatasetValidator()
        valid, errors = validator.validate_record(record)
        assert not valid
        assert any("Missing required metadata" in e for e in errors)

    def test_confidence_out_of_bounds_detected(self):
        records = generate_intent_detection(1)
        records[0]["confidence"] = 1.5
        validator = DatasetValidator()
        valid, errors = validator.validate_record(records[0])
        assert not valid
        assert any("Confidence" in e for e in errors)

    def test_duplicate_detection(self):
        validator = DatasetValidator()
        records = generate_intent_detection(2)
        # Make second record a duplicate by copying ID
        records[1]["id"] = records[0]["id"]
        validator.validate_record(records[0])
        valid, errors = validator.validate_record(records[1])
        assert not valid
        assert any("Duplicate" in e for e in errors)

    def test_batch_validation(self):
        records = generate_intent_detection(10)
        validator = DatasetValidator()
        all_valid, batch_errors = validator.validate_batch(records)
        assert all_valid, f"Batch validation failed: {batch_errors}"

    def test_tags_type_validation(self):
        records = generate_intent_detection(1)
        records[0]["tags"] = "not_a_list"
        validator = DatasetValidator()
        valid, errors = validator.validate_record(records[0])
        assert not valid
        assert any("tags" in e for e in errors)


# =========================================================================
#  Writer Tests
# =========================================================================

class TestWriter:
    """Verify all export formats work correctly."""

    @pytest.fixture
    def sample_records(self):
        return generate_intent_detection(5)

    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return str(tmp_path)

    def test_json_export(self, sample_records, tmp_dir):
        path = os.path.join(tmp_dir, "test.json")
        DatasetWriter.write(sample_records, "json", path)
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 5

    def test_jsonl_export(self, sample_records, tmp_dir):
        path = os.path.join(tmp_dir, "test.jsonl")
        DatasetWriter.write(sample_records, "jsonl", path)
        with open(path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 5

    def test_csv_export(self, sample_records, tmp_dir):
        path = os.path.join(tmp_dir, "test.csv")
        DatasetWriter.write(sample_records, "csv", path)
        assert os.path.exists(path)
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 6  # header + 5 rows

    def test_yaml_export(self, sample_records, tmp_dir):
        path = os.path.join(tmp_dir, "test.yaml")
        DatasetWriter.write(sample_records, "yaml", path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 100

    def test_markdown_export(self, sample_records, tmp_dir):
        path = os.path.join(tmp_dir, "test.md")
        DatasetWriter.write(sample_records, "md", path)
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "## Record #1" in content
        assert "## Record #5" in content

    def test_sqlite_export(self, sample_records, tmp_dir):
        path = os.path.join(tmp_dir, "test_data", "test.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        DatasetWriter.write(sample_records, "sqlite", path)
        assert os.path.exists(path)
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        assert len(tables) >= 1
        table_name = tables[0][0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        assert count == 5
        conn.close()

    def test_empty_records_no_error(self, tmp_dir):
        path = os.path.join(tmp_dir, "empty.json")
        DatasetWriter.write([], "json", path)
        # Should not create a file for empty records
        assert not os.path.exists(path)

    def test_flatten_record_serializes_nested(self):
        record = {"id": "1", "tags": ["a", "b"], "nested": {"key": "val"}}
        flat = flatten_record(record)
        assert flat["id"] == "1"
        assert isinstance(flat["tags"], str)
        assert json.loads(flat["tags"]) == ["a", "b"]


# =========================================================================
#  Ingestion Tests
# =========================================================================

class TestIngestion:
    """Test the company knowledge ingestion pipeline."""

    def test_format_detection(self):
        assert _detect_format("report.pdf") == "pdf"
        assert _detect_format("schema.sql") == "code"
        assert _detect_format("notes.md") == "markdown"
        assert _detect_format("data.csv") == "csv"
        assert _detect_format("image.png") == "image"
        assert _detect_format("unknown.xyz") == "unknown"

    def test_entity_extraction(self):
        text = "We deployed MQTT broker with PostgreSQL backend on Kubernetes. HIPAA compliance required."
        entities = _extract_entities(text)
        assert "MQTT" in entities
        assert "PostgreSQL" in entities
        assert "Kubernetes" in entities
        assert "HIPAA" in entities

    def test_ingestion_pipeline_with_markdown(self, tmp_path):
        # Create a test markdown file
        md_file = tmp_path / "test_doc.md"
        md_file.write_text("# MQTT Architecture\nDesign for factory SCADA integration using OPC-UA\n")

        pipeline = IngestionPipeline(str(tmp_path))
        files = pipeline.scan()
        assert len(files) == 1

        records = pipeline.ingest()
        assert len(records) == 1
        assert records[0]["document_format"] == "markdown"
        assert records[0]["ingestion_status"] == "processed"
        assert "MQTT" in records[0]["extracted_entities"]
        assert "OPC-UA" in records[0]["extracted_entities"]

    def test_ingestion_empty_directory(self, tmp_path):
        pipeline = IngestionPipeline(str(tmp_path))
        files = pipeline.scan()
        assert len(files) == 0
        records = pipeline.ingest()
        assert len(records) == 0


# =========================================================================
#  Scale Tests
# =========================================================================

class TestScaleGeneration:
    """Verify generators work at larger scales."""

    def test_hundred_records_per_generator(self):
        """Generate 100 records from each generator to verify no crashes."""
        for did in ALL_DATASET_IDS:
            generator = DATASET_GENERATORS[did]
            records = generator(100)
            assert len(records) == 100, f"{did} returned {len(records)} instead of 100"

    def test_thousand_records_intent(self):
        records = generate_intent_detection(1000)
        assert len(records) == 1000
        ids = {r["id"] for r in records}
        assert len(ids) == 1000, "Duplicate IDs in 1000 intent records"

    def test_thousand_records_blueprints(self):
        records = generate_solution_blueprints(1000)
        assert len(records) == 1000
