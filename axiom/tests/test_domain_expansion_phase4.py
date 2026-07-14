"""
Phase 4 (Domain Knowledge Engine) — tests for the 7 newly added verticals:
HVAC, Insurance, Energy, Government, Manufacturing, Smart Building, ESG.
Also confirms "Water Pump" / "Hospital" style requests keep resolving to
their existing industrial_iot / healthcare profiles rather than being
mistakenly captured by a new, narrower keyword set.
"""

from ocif.engines.domain_profiles import DOMAIN_PROFILES
from ocif.engines.engineering_intelligence import IndustryClassifier
from ocif.engines.industry_patterns import PATTERNS_BY_KEY, select_pattern
from ocif.engines.project_understanding import _INDUSTRY_DEFAULTS, _INDUSTRY_KEYWORDS, classify_rule_based
from ocif.frames import CognitiveContext, ContextFrame, PerceptionFrame, ProjectUnderstandingFrame

NEW_INDUSTRIES = ["hvac", "insurance", "energy", "government", "manufacturing", "smart_building", "esg"]


def _classify(text: str):
    ctx = CognitiveContext(task=text)
    ctx.perception = PerceptionFrame(raw_text=text, normalized_text=text)
    ctx.context = ContextFrame(subject=text, entities=[], actors=[])
    return classify_rule_based(ctx)


def test_new_industries_registered_everywhere():
    for industry in NEW_INDUSTRIES:
        assert industry in _INDUSTRY_KEYWORDS, industry
        assert industry in _INDUSTRY_DEFAULTS, industry
        assert industry in DOMAIN_PROFILES, industry
        assert industry in PATTERNS_BY_KEY, industry
        name, standards = IndustryClassifier().classify(industry)
        assert name and standards, industry


def test_hvac_request_classifies_as_hvac_not_industrial_iot():
    frame = _classify("We need an HVAC system to manage air conditioning, chiller units, and building thermostat control.")
    assert frame.industry == "hvac"
    assert frame.communication_protocols
    assert frame.apis


def test_insurance_request_classifies_correctly():
    frame = _classify("Build a system for policyholders to submit insurance claims and for underwriting to calculate premiums.")
    assert frame.industry == "insurance"
    assert frame.logical_assets
    assert frame.apis


def test_energy_request_classifies_correctly():
    frame = _classify("Design a smart meter and substation monitoring platform for our utility company's power grid.")
    assert frame.industry == "energy"
    assert frame.sensors
    assert frame.communication_protocols


def test_government_request_classifies_correctly():
    frame = _classify("Build a citizen services portal for permit applications and public records requests for our municipal government agency.")
    assert frame.industry == "government"
    assert frame.apis


def test_manufacturing_request_classifies_correctly():
    frame = _classify("We need an MES system to track work orders and quality control on our production line and assembly line.")
    assert frame.industry == "manufacturing"
    assert frame.apis


def test_smart_building_request_classifies_correctly():
    frame = _classify("Build a smart building automation system with occupancy sensors, access control, and a building management system.")
    assert frame.industry == "smart_building"
    assert frame.sensors


def test_esg_request_classifies_correctly():
    frame = _classify("We need an ESG platform to track our carbon footprint and generate sustainability reports for governance reporting.")
    assert frame.industry == "esg"
    assert frame.apis


def test_water_pump_still_resolves_to_industrial_iot():
    frame = _classify("Design a predictive maintenance platform for factory water pumps and compressors with vibration sensors.")
    assert frame.industry == "industrial_iot"


def test_hospital_style_request_still_resolves_to_healthcare():
    frame = _classify("We run a hospital and need to manage patient appointments and doctor schedules.")
    assert frame.industry == "healthcare"


def test_select_pattern_resolves_new_industries():
    for industry in NEW_INDUSTRIES:
        understanding = ProjectUnderstandingFrame(industry=industry)
        pattern = select_pattern(understanding)
        assert pattern.key == industry
        assert pattern.er_diagram.strip().lower().startswith("erdiagram")
        assert pattern.workflow_diagram.strip().lower().startswith("sequencediagram")
