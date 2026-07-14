"""
Domain Profile registry — the "detection" half of Project Intelligence.

ProjectUnderstandingFrame carries physical_assets, logical_assets, sensors,
devices, communication_protocols, apis, and databases (ocif/frames.py), but
the offline rule-based fallback classifier (project_understanding.py's
classify_rule_based) only populated a couple of these fields for a couple of
industries — everything else shipped empty whenever no LLM provider was
live. This module is the single source of truth for those fields per
industry, so the fallback path is never thinner than the LLM path on the
fields the platform explicitly promises to detect.

Keyed by the same industry slugs as _INDUSTRY_KEYWORDS/_INDUSTRY_DEFAULTS
(project_understanding.py) and PATTERNS_BY_KEY (industry_patterns.py).
Adding a new industry means adding one DomainProfile here — mirrors the
extension philosophy industry_patterns.py already documents for itself, and
this registry is the natural seed for future domain-profile expansion.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DomainProfile:
    key: str
    physical_assets: List[str] = field(default_factory=list)
    logical_assets: List[str] = field(default_factory=list)
    sensors: List[str] = field(default_factory=list)
    devices: List[str] = field(default_factory=list)
    communication_protocols: List[str] = field(default_factory=list)
    apis: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    ai_components: List[str] = field(default_factory=list)
    cloud_components: List[str] = field(default_factory=list)
    edge_components: List[str] = field(default_factory=list)


DOMAIN_PROFILES: Dict[str, DomainProfile] = {
    "industrial_iot": DomainProfile(
        key="industrial_iot",
        physical_assets=["Pump", "Motor", "Compressor", "Valve", "Conveyor", "Turbine", "Boiler"],
        logical_assets=["Device Twin", "Maintenance Ticket", "Asset Health Score"],
        sensors=["Vibration", "Temperature", "Pressure", "Flow", "Current"],
        devices=["Edge gateway", "Field sensor node", "PLC"],
        communication_protocols=["MQTT", "OPC-UA", "Modbus"],
        apis=["Device Registry API", "Telemetry Query API", "Alert API", "Remaining-Useful-Life API"],
        databases=["Time-series store (TimescaleDB)", "Relational metadata store"],
        ai_components=["Anomaly detection model", "Remaining-useful-life estimator"],
        edge_components=["Edge gateway buffering/store-and-forward"],
    ),
    "healthcare": DomainProfile(
        key="healthcare",
        physical_assets=["Bedside monitor", "Infusion pump", "Imaging scanner", "Ventilator"],
        logical_assets=["Patient record", "Care plan", "Clinical order", "Consent record"],
        sensors=["Vital signs monitor", "Pulse oximeter"],
        devices=["Clinical workstation", "Mobile ward device"],
        communication_protocols=["HL7", "FHIR REST"],
        apis=["Patient API", "Appointment API", "Encounter/Order API", "Results API"],
        databases=["Encrypted relational store (PHI)"],
    ),
    "education": DomainProfile(
        key="education",
        physical_assets=["Classroom attendance scanner", "Campus ID badge reader"],
        logical_assets=["Student record", "Enrollment", "Grade book", "Attendance record"],
        devices=["Classroom kiosk", "Faculty portal device"],
        communication_protocols=["OAuth2/SSO"],
        apis=["Student API", "Attendance API", "Course/Assignment API", "Grades API"],
        databases=["Relational academic records store"],
    ),
    "banking_fintech": DomainProfile(
        key="banking_fintech",
        logical_assets=["Account", "Ledger Entry", "KYC Check", "Fraud Case"],
        communication_protocols=["REST", "Webhook callbacks"],
        apis=["Account API", "Transfer API", "Ledger Query API", "Compliance/Fraud API"],
        databases=["Append-only ledger store"],
        ai_components=["Fraud scoring model"],
    ),
    "automotive": DomainProfile(
        key="automotive",
        physical_assets=["Vehicle", "OBD-II unit", "Telematics control unit"],
        logical_assets=["Trip record", "Maintenance record", "Driver profile"],
        sensors=["GPS", "Engine diagnostics", "Fuel level"],
        devices=["Vehicle gateway"],
        communication_protocols=["MQTT", "CAN bus", "OBD-II"],
        apis=["Vehicle API", "Trip History API", "Geofence API", "Alert API"],
        databases=["Time-series telemetry store"],
    ),
    "construction": DomainProfile(
        key="construction",
        physical_assets=["Heavy equipment", "Site safety sensor", "Scaffolding"],
        logical_assets=["Project", "Phase", "Task", "Site Inspection", "BIM Model"],
        devices=["Site tablet", "Safety wearable"],
        apis=["Project API", "Site Inspection API", "Equipment Assignment API", "Document/BIM API"],
        databases=["Relational project store", "Object storage for drawings/BIM"],
    ),
    "agriculture": DomainProfile(
        key="agriculture",
        physical_assets=["Irrigation valve", "Field gateway", "Weather station"],
        logical_assets=["Field", "Irrigation Event", "Crop Cycle"],
        sensors=["Soil moisture", "Weather", "Crop stage"],
        devices=["Field gateway"],
        communication_protocols=["MQTT", "LoRaWAN"],
        apis=["Field Readings API", "Irrigation Recommendation API", "Alert API"],
        databases=["Time-series sensor store"],
        edge_components=["Field gateway"],
    ),
    "retail_ecommerce": DomainProfile(
        key="retail_ecommerce",
        physical_assets=["Point-of-sale terminal", "Warehouse scanner"],
        logical_assets=["Product", "Order", "Inventory Item", "Shipment"],
        communication_protocols=["REST"],
        apis=["Catalog API", "Inventory API", "Order/Payment API"],
        databases=["Relational order/inventory store", "Search index"],
    ),
    "logistics_supply_chain": DomainProfile(
        key="logistics_supply_chain",
        physical_assets=["Delivery vehicle", "Warehouse scanner", "GPS tracker"],
        logical_assets=["Shipment", "Route", "Tracking Event"],
        sensors=["GPS"],
        devices=["Fleet gateway", "Handheld scanner"],
        apis=["Shipment API", "Fleet Assignment API", "Tracking API"],
        databases=["Time-series tracking store", "Relational shipment store"],
    ),
    "hvac": DomainProfile(
        key="hvac",
        physical_assets=["Air handling unit", "Chiller", "Cooling tower", "Damper"],
        logical_assets=["Zone Configuration", "Setpoint Profile", "Fault Alert"],
        sensors=["Temperature", "Humidity", "CO2", "Airflow"],
        devices=["Air handling unit controller", "Zone thermostat"],
        communication_protocols=["BACnet", "Modbus", "MQTT"],
        apis=["Zone Control API", "Setpoint API", "Fault Alert API"],
        databases=["Time-series store", "Relational configuration store"],
        edge_components=["Building controller"],
    ),
    "insurance": DomainProfile(
        key="insurance",
        logical_assets=["Policy", "Claim", "Policyholder Profile", "Premium Ledger"],
        apis=["Policy API", "Claims API", "Underwriting Rules API"],
        databases=["Relational policy/claims store"],
        ai_components=["Fraud detection model", "Claims triage model"],
    ),
    "energy": DomainProfile(
        key="energy",
        physical_assets=["Smart meter", "Substation transformer", "Circuit breaker"],
        logical_assets=["Load Reading", "Outage Event", "Grid Asset Record"],
        sensors=["Voltage", "Current", "Power factor"],
        devices=["Smart meter", "Substation gateway"],
        communication_protocols=["DNP3", "MQTT", "OPC-UA"],
        apis=["Meter Telemetry API", "Outage API", "Grid Asset API"],
        databases=["Time-series store", "Relational grid asset store"],
        ai_components=["Load forecasting model"],
    ),
    "government": DomainProfile(
        key="government",
        physical_assets=["Municipal kiosk"],
        logical_assets=["Citizen Application", "Permit Record", "Public Record"],
        apis=["Citizen Services API", "Permit API", "Public Records API"],
        databases=["Relational records store"],
        cloud_components=["Government cloud (FedRAMP-style)"],
    ),
    "manufacturing": DomainProfile(
        key="manufacturing",
        physical_assets=["Production line equipment", "CNC machine", "Assembly robot"],
        logical_assets=["Work Order", "Bill of Materials", "Quality Inspection Record"],
        sensors=["Cycle time", "Defect detection", "Machine utilization"],
        devices=["Shop-floor terminal", "PLC"],
        communication_protocols=["OPC-UA", "Modbus"],
        apis=["Work Order API", "Quality Control API", "Production Scheduling API"],
        databases=["Relational production store"],
        cloud_components=["ERP/MES integration gateway"],
    ),
    "smart_building": DomainProfile(
        key="smart_building",
        physical_assets=["Access control reader", "Occupancy sensor", "Building controller"],
        logical_assets=["Zone", "Access Event", "Energy Reading"],
        sensors=["Occupancy", "Temperature", "Light level"],
        devices=["Building controller", "Access control reader"],
        communication_protocols=["BACnet", "MQTT", "Zigbee"],
        apis=["Building Automation API", "Access Control API", "Energy Management API"],
        databases=["Time-series store", "Relational configuration store"],
        edge_components=["Building automation controller"],
    ),
    "esg": DomainProfile(
        key="esg",
        logical_assets=["Emission Record", "Sustainability Metric", "Compliance Report"],
        apis=["Data Aggregation API", "Reporting API", "Compliance Audit API"],
        databases=["Relational metrics store"],
        cloud_components=["Third-party emissions data connector"],
    ),
    "ai_ml_platform": DomainProfile(
        key="ai_ml_platform",
        logical_assets=["Document", "Chunk", "Embedding", "Query"],
        apis=["Ingestion API", "Query API", "Feedback API"],
        databases=["Vector store"],
        ai_components=["Embedding model", "LLM provider"],
        cloud_components=["Model gateway"],
    ),
    "event_driven_platform": DomainProfile(
        key="event_driven_platform",
        logical_assets=["Domain Event", "Aggregate", "Read Model"],
        communication_protocols=["Kafka", "AMQP"],
        apis=["Domain Service API"],
        databases=["Relational store (per service)"],
        cloud_components=["Event backbone"],
    ),
    "generic_software": DomainProfile(
        key="generic_software",
        logical_assets=["Resource", "Event"],
        apis=["Resource API"],
        databases=["Relational store"],
        cloud_components=["Application service"],
    ),
}


def get_domain_profile(industry: str) -> DomainProfile:
    """Returns the profile for an industry slug, falling back to generic_software."""
    key = (industry or "").strip().lower().replace(" ", "_").replace("-", "_")
    return DOMAIN_PROFILES.get(key, DOMAIN_PROFILES["generic_software"])
