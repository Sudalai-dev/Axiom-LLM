"""
Validator Module — Axiom Dataset Generation Platform.

Performs schema checking, duplicate detection using record hashes,
missing field identification, and cross-field engineering consistency rules.
"""

import hashlib
import json
from typing import Any, Dict, List, Set, Tuple


REQUIRED_METADATA_FIELDS = {
    "id",
    "version",
    "source",
    "tags",
    "confidence",
    "review_status",
    "created_date",
    "updated_date",
    "approval",
    "domain",
    "industry",
    "intent",
    "complexity",
}


class DatasetValidator:
    """Automates schema, duplicate, and engineering consistency validation."""

    def __init__(self) -> None:
        self.seen_hashes: Set[str] = set()

    def reset_duplicate_check(self) -> None:
        """Clears duplicate checking cache."""
        self.seen_hashes.clear()

    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates a single record against schema, constraints, and consistency rules.
        Returns (is_valid, list_of_errors).
        """
        errors = []

        # 1. Check required metadata fields
        missing = REQUIRED_METADATA_FIELDS - set(record.keys())
        if missing:
            errors.append(f"Missing required metadata fields: {', '.join(missing)}")

        # 2. Check confidence constraints
        confidence = record.get("confidence")
        if confidence is not None:
            try:
                conf_val = float(confidence)
                if not (0.0 <= conf_val <= 1.0):
                    errors.append(f"Confidence value out of bounds (0.0 - 1.0): {conf_val}")
            except (ValueError, TypeError):
                errors.append(f"Confidence value is not a valid float: {confidence}")

        # 3. Check tags type
        tags = record.get("tags")
        if tags is not None and not isinstance(tags, list):
            errors.append("Metadata field 'tags' must be a list of strings")

        # 4. Duplicate check (hashing prompt/input or text content)
        record_content_hash = self._calculate_content_hash(record)
        if record_content_hash in self.seen_hashes:
            errors.append(f"Duplicate record detected (same ID or duplicate content hash: {record_content_hash})")
        else:
            self.seen_hashes.add(record_content_hash)

        # 5. Cross-field engineering consistency rules
        domain = str(record.get("domain", "")).lower()
        industry = str(record.get("industry", "")).lower()
        
        # Checking standards consistency in standard/recommendation fields
        standards = []
        for field in ("standards", "rules", "recommendations", "facts", "recommended_solution", "architecture_overview"):
            val = record.get(field)
            if isinstance(val, list):
                standards.extend([str(item).lower() for item in val])
            elif isinstance(val, str):
                standards.append(val.lower())

        # Only enforce industry-standards consistency when the record actually
        # carries standards/recommendation fields (e.g., solution blueprints,
        # industry classification). Skip for lightweight record types like
        # intent detection that don't carry these fields.
        if standards:
            if "healthcare" in industry:
                if not any(k in " ".join(standards) for k in ("hipaa", "fhir", "hl7", "clinical")):
                    errors.append("Healthcare industry inconsistency: missing HIPAA, FHIR, or HL7 standard mentions")

            if "banking" in industry or "finance" in industry:
                if not any(k in " ".join(standards) for k in ("pci", "ledger", "transaction", "double-entry")):
                    errors.append("Banking/Finance industry inconsistency: missing PCI, ledger, or transaction standards")

            if "industrial" in industry or "manufacturing" in industry:
                if not any(k in " ".join(standards) for k in ("mqtt", "opc", "modbus", "isa-95", "iec-62443")):
                    errors.append("Industrial/Manufacturing industry inconsistency: missing MQTT, OPC, Modbus, or ISA-95 standards")

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_batch(self, records: List[Dict[str, Any]], reset_dups: bool = True) -> Tuple[bool, Dict[int, List[str]]]:
        """
        Validates a list of records in a batch.
        Returns (all_valid, dictionary_of_errors_by_record_index).
        """
        if reset_dups:
            self.reset_duplicate_check()

        batch_errors = {}
        for idx, record in enumerate(records):
            valid, errs = self.validate_record(record)
            if not valid:
                batch_errors[idx] = errs

        all_valid = len(batch_errors) == 0
        return all_valid, batch_errors

    def _calculate_content_hash(self, record: Dict[str, Any]) -> str:
        """Derives a content hash for the record based on unique data fields to avoid identical entries."""
        # Use ID if present, otherwise hash key text fields
        record_id = record.get("id")
        if record_id:
            return record_id

        # Secondary hash based on content fields
        content_keys = ["input", "problem", "solution", "symptoms", "title", "subject", "executive_summary"]
        hash_content = ""
        for k in content_keys:
            val = record.get(k)
            if val:
                if isinstance(val, (list, dict)):
                    hash_content += json.dumps(val, sort_keys=True)
                else:
                    hash_content += str(val)

        if not hash_content:
            hash_content = json.dumps(record, sort_keys=True)

        return hashlib.sha256(hash_content.encode("utf-8")).hexdigest()
