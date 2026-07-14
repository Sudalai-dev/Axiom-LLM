"""
Unit tests for the DomainProfile registry (ocif/engines/domain_profiles.py)
and the enrichment it feeds into project_understanding.classify_rule_based —
Phase 1 (Project Intelligence Engine) closes the gap where the offline
fallback classifier shipped empty physical_assets/logical_assets/apis/
sensors/devices/communication_protocols/databases/relationships for most
industries.
"""

from ocif.engines.domain_profiles import DOMAIN_PROFILES, get_domain_profile
from ocif.engines.project_understanding import _INDUSTRY_DEFAULTS, classify_rule_based
from ocif.engines.industry_patterns import PATTERNS_BY_KEY
from ocif.frames import CognitiveContext, ContextFrame, PerceptionFrame


def _classify(text: str):
    ctx = CognitiveContext(task=text)
    ctx.perception = PerceptionFrame(raw_text=text, normalized_text=text)
    ctx.context = ContextFrame(subject=text, entities=[], actors=[])
    return classify_rule_based(ctx)


def test_every_industry_default_has_a_domain_profile():
    for industry in _INDUSTRY_DEFAULTS:
        assert industry in DOMAIN_PROFILES, f"missing DomainProfile for {industry}"


def test_every_industry_pattern_has_a_domain_profile():
    for key in PATTERNS_BY_KEY:
        assert key in DOMAIN_PROFILES, f"missing DomainProfile for {key}"


def test_get_domain_profile_falls_back_to_generic():
    profile = get_domain_profile("totally_unknown_industry_xyz")
    assert profile.key == "generic_software"


def test_healthcare_fallback_populates_detection_fields():
    frame = _classify("We run a hospital and need to manage patient appointments and doctor schedules.")
    assert frame.industry == "healthcare"
    assert frame.physical_assets, "physical_assets should not be empty for healthcare"
    assert frame.logical_assets, "logical_assets should not be empty for healthcare"
    assert frame.apis, "apis should not be empty for healthcare"
    assert frame.databases, "databases should not be empty for healthcare"


def test_industrial_iot_fallback_keeps_existing_rich_defaults_and_fills_gaps():
    frame = _classify("Design a predictive maintenance system for factory pumps and compressors with vibration sensors.")
    assert frame.industry == "industrial_iot"
    # Already populated in _INDUSTRY_DEFAULTS — must not be overwritten.
    assert "MQTT" in frame.communication_protocols
    # Was previously empty in the offline path — now filled from the profile.
    assert frame.physical_assets
    assert frame.logical_assets
    assert frame.apis


def test_banking_fallback_populates_apis_and_logical_assets():
    frame = _classify("Build a banking ledger system with account transfers and fraud detection.")
    assert frame.industry == "banking_fintech"
    assert frame.apis
    assert frame.logical_assets
    assert frame.databases


def test_relationships_built_from_actors_entities_workflows():
    frame = _classify("We need an education attendance system for our school with students and faculty.")
    assert frame.industry == "education"
    assert frame.domain_entities, "expected education defaults to include domain_entities"
    assert frame.relationships, "relationships should be derived when actors/entities/workflows exist"


def test_generic_software_still_returns_populated_detection_fields():
    frame = _classify("Build a general purpose internal tool for tracking tasks.")
    assert frame.industry == "generic_software"
    assert frame.apis
    assert frame.databases
