"""
Project Understanding — deep project/industry classification that runs
after the Context Engine (intent + IT/IoT keyword extraction) and before
Planning, so downstream engines consume a genuine understanding of what
the project actually is instead of a shallow keyword match.

Not a formal CognitiveEngine / EngineName member: the "8 engines" /
"octagon" shape is a literal geometric invariant elsewhere in this codebase
(ocif/octagon.py, ocif/layout.py, core/engine_registry.py's
register_cognitive_engines), so this is deliberately a plain classifier
invoked directly from OctagonalKernel.process(), the same way the
Reasoning Engine calls into SolutionSynthesizer without that being a
separate formal engine either.

Two-tier, mirroring the platform-wide "never degrade to a stub" guarantee:
  1. LLM-driven classification (primary) — one call through the shared
     InferenceAdapter, asking for the full ProjectUnderstandingFrame as
     strict JSON.
  2. Rule-based fallback (offline / no live provider) — an expanded
     ~12-industry keyword lexicon, generalizing the same kind of matching
     ContextEngine already does for tech keywords, just far broader.

Results are cached per conversation_id (engine instances are constructed
once at process startup, so this cache lives for the process lifetime) so
a multi-turn conversation about the same project doesn't pay for a second
LLM classification call on every turn.
"""

import json
import logging
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from ocif.engines.domain_profiles import get_domain_profile
from ocif.frames import CognitiveContext, ProjectUnderstandingFrame
from ocif.inference_adapter import InferenceAdapter

logger = logging.getLogger("AxiomOCIF.ProjectUnderstanding")

_MAX_CACHE_SIZE = 500

# ---------------------------------------------------------------------------
# Rule-based fallback — expanded business/industry lexicon (distinct from
# ContextEngine.TECH_LEXICON, which only recognizes IT/IoT technology words
# and has no concept of what business the request is actually for).
# ---------------------------------------------------------------------------

_INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "industrial_iot": [
        "pump", "compressor", "motor", "valve", "plant", "factory", "manufacturing",
        "predictive maintenance", "conveyor", "turbine", "generator", "boiler",
        "industrial", "machinery", "equipment failure", "asset health", "vibration",
        "remaining useful life", "rul", "scada", "plc", "shop floor",
    ],
    "healthcare": [
        "hospital", "patient", "doctor", "nurse", "clinic", "clinical", "emr", "ehr",
        "appointment", "diagnosis", "medical", "healthcare", "treatment",
        "prescription", "pharmacy", "ward", "admission", "discharge", "physician",
    ],
    "education": [
        "school", "student", "faculty", "teacher", "attendance", "classroom",
        "university", "college", "curriculum", "exam", "grading", "enrollment",
        "campus", "lecture", "academic", "roll number", "semester",
    ],
    "banking_fintech": [
        "bank", "banking", "account balance", "transaction", "payment", "ledger",
        "loan", "credit card", "debit", "fintech", "money transfer", "kyc", "aml",
        "fraud detection", "wallet", "financial institution", "interest rate",
    ],
    "automotive": [
        "vehicle", "car fleet", "telematics", "engine diagnostics", "obd",
        "can bus", "automotive", "dealership", "odometer", "fuel efficiency",
        "driver behavior",
    ],
    "construction": [
        "construction", "job site", "building project", "contractor", "blueprint",
        "bim", "scaffolding", "civil engineering", "safety inspection",
        "site supervisor", "permit",
    ],
    "agriculture": [
        "farm", "crop", "soil moisture", "irrigation", "livestock", "agriculture",
        "agricultural", "harvest", "greenhouse", "farming", "crop yield",
    ],
    "retail_ecommerce": [
        "retail", "ecommerce", "e-commerce", "storefront", "shopping cart",
        "checkout", "product catalog", "warehouse inventory", "customer order",
        "point of sale", "pos system",
    ],
    "logistics_supply_chain": [
        "logistics", "shipment", "supply chain", "freight", "fleet routing",
        "package tracking", "courier", "dispatch", "delivery route",
    ],
    "hvac": [
        "hvac", "air handling unit", "chiller", "thermostat", "duct", "ventilation",
        "cooling tower", "air conditioning", "heat pump", "damper", "refrigerant",
    ],
    "insurance": [
        "insurance", "policyholder", "insurance claim", "underwriting", "premium",
        "actuarial", "insurer", "deductible", "policy renewal", "claims adjuster",
    ],
    "energy": [
        "power grid", "substation", "smart meter", "utility company", "renewable energy",
        "solar farm", "wind farm", "energy consumption", "grid outage", "power transformer",
    ],
    "government": [
        "citizen services", "government agency", "public sector", "permit application",
        "public records", "municipal", "compliance filing", "civic portal", "government portal",
    ],
    "manufacturing": [
        "production line", "work order", "quality control", "erp system", "mes system",
        "assembly line", "bill of materials", "shop floor schedule", "manufacturing plant",
    ],
    "smart_building": [
        "building automation", "occupancy sensor", "access control system", "bms",
        "building management system", "smart building", "energy management system", "facility management",
    ],
    "esg": [
        "esg", "sustainability report", "carbon footprint", "emissions tracking",
        "environmental report", "governance report", "social responsibility", "net zero", "esg compliance",
    ],
}

_AI_ENTITY_HINTS = {"LLM", "RAG", "Embeddings", "Machine Learning", "Vector Database", "Anomaly Detection"}
_EVENT_ENTITY_HINTS = {"Kafka", "RabbitMQ", "Microservices"}
_IOT_ENTITY_HINTS = {"MQTT", "OPC-UA", "Modbus", "IoT", "AIoT", "Sensors", "Edge Computing", "SCADA", "Telemetry"}

# Compact per-industry defaults for the fallback classifier — deliberately
# lighter-weight than the LLM path; SolutionSynthesizer's architecture
# detail lives in ocif/engines/industry_patterns.py, not duplicated here.
_INDUSTRY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "industrial_iot": dict(
        business_domain="Industrial IoT / Manufacturing",
        project_category="Predictive Maintenance & Asset Monitoring",
        application_category="Industrial AIoT Platform",
        system_type="Edge-to-cloud telemetry and alerting system",
        architecture_style="Event-driven, edge-to-cloud",
        deployment_model="Hybrid (edge gateway + cloud)",
        domain_expert_persona="Industrial IoT Solutions Architect",
        technical_constraints=["Intermittent field connectivity", "Constrained edge hardware", "Real-time alerting latency"],
        business_constraints=["Minimize unplanned downtime", "Extend equipment service life"],
        technical_actors=["Field Device / Edge Gateway", "Stream Processor", "Alerting Service"],
        domain_entities=["Device", "Telemetry Reading", "Alert", "Maintenance Ticket"],
        workflows=["Telemetry ingestion", "Anomaly/threshold evaluation", "Maintenance ticket escalation"],
        external_systems=["SCADA/PLC systems", "CMMS (maintenance management)"],
        databases=["Time-series store", "Relational metadata store"],
        communication_protocols=["MQTT", "OPC-UA", "Modbus"],
        sensors=["Vibration", "Temperature", "Pressure", "Flow"],
        devices=["Edge gateway", "Field sensor node"],
        ai_components=["Anomaly detection model", "Remaining-useful-life estimator"],
        edge_components=["Edge gateway buffering/store-and-forward"],
        recommended_documents=["Sensor Architecture", "Telemetry Flow", "Maintenance Report", "Remaining Useful Life Report", "Edge Architecture"],
        recommended_diagrams=["Device connectivity diagram", "Telemetry sequence diagram", "Edge deployment diagram"],
    ),
    "healthcare": dict(
        business_domain="Healthcare / Clinical Operations",
        project_category="Patient & Clinical Workflow Management",
        application_category="Healthcare Information System",
        system_type="Clinical records and workflow system",
        architecture_style="Layered service architecture with FHIR interoperability",
        deployment_model="Cloud (compliance-isolated) or on-prem hospital network",
        domain_expert_persona="Healthcare Solutions Architect",
        technical_constraints=["PHI data protection", "HL7/FHIR interoperability", "High availability for clinical operations"],
        business_constraints=["Regulatory compliance (HIPAA-style)", "Clinical staff workflow efficiency"],
        technical_actors=["Patient Records Service", "Integration Engine", "Clinical Workflow Engine"],
        domain_entities=["Patient", "Doctor", "Appointment", "Encounter", "Order", "Result"],
        workflows=["Patient registration", "Appointment scheduling", "Clinical encounter", "Order & result management"],
        external_systems=["Lab information system", "Imaging system", "Pharmacy system"],
        databases=["Encrypted relational store (PHI)"],
        communication_protocols=["HL7", "FHIR REST"],
        ai_components=[],
        recommended_documents=["Patient Flow", "Doctor Workflow", "EMR Architecture", "Appointment Flow", "Hospital Architecture"],
        recommended_diagrams=["Patient journey diagram", "Encounter/order sequence diagram"],
    ),
    "education": dict(
        business_domain="Education / Academic Administration",
        project_category="Student & Faculty Workflow Management",
        application_category="Academic Management System",
        system_type="Roster, attendance, and academic records system",
        architecture_style="Layered service architecture with institutional SSO",
        deployment_model="Cloud, multi-tenant per institution",
        domain_expert_persona="Education Platform Architect",
        technical_constraints=["Institutional SSO integration", "Student data privacy (FERPA-style)"],
        business_constraints=["Accurate attendance/grading records", "Guardian notification requirements"],
        technical_actors=["Identity & Roster Service", "Attendance Service", "Notification Service"],
        domain_entities=["Student", "Faculty", "Class Session", "Attendance Record", "Course", "Enrollment"],
        workflows=["Roster management", "Attendance capture", "Grading", "Guardian notification"],
        external_systems=["Institutional identity provider (SSO)"],
        databases=["Relational academic records store"],
        communication_protocols=["OAuth2/SSO"],
        ai_components=[],
        recommended_documents=["Authentication Flow", "Attendance Flow", "Faculty Workflow", "Student Workflow"],
        recommended_diagrams=["Attendance sequence diagram", "Roster/enrollment ER diagram"],
    ),
    "banking_fintech": dict(
        business_domain="Banking / Financial Services",
        project_category="Ledger & Payments Management",
        application_category="Financial Services Platform",
        system_type="Ledger-centric transaction processing system",
        architecture_style="Event-driven, ledger-centric",
        deployment_model="Cloud, regulatory-isolated environment",
        domain_expert_persona="Financial Solutions Architect",
        technical_constraints=["Idempotent money movement", "Double-entry ledger integrity", "Fraud/AML real-time scoring"],
        business_constraints=["Regulatory compliance (KYC/AML)", "Zero tolerance for balance inconsistency"],
        technical_actors=["Ledger Service", "Fraud & Compliance Engine", "Payments/Transfer Service"],
        domain_entities=["Account", "Ledger Entry", "Transfer", "KYC Check"],
        workflows=["Account opening", "Transfer initiation", "Fraud scoring", "Ledger posting"],
        external_systems=["Payment network", "KYC/AML provider"],
        databases=["Append-only ledger store"],
        communication_protocols=["REST", "Webhook callbacks"],
        ai_components=["Fraud scoring model"],
        recommended_documents=["Ledger Architecture", "Transfer Flow", "Compliance Report", "Fraud Monitoring Report"],
        recommended_diagrams=["Ledger ER diagram", "Transfer sequence diagram"],
    ),
    "automotive": dict(
        business_domain="Automotive / Fleet Telematics",
        project_category="Connected Vehicle Monitoring",
        application_category="Fleet Telematics Platform",
        system_type="Vehicle telemetry and fleet management system",
        architecture_style="Edge-to-cloud telemetry",
        deployment_model="Hybrid (vehicle gateway + cloud)",
        domain_expert_persona="Automotive Systems Architect",
        technical_constraints=["Intermittent cellular connectivity", "CAN-bus/OBD-II signal normalization"],
        business_constraints=["Fleet uptime and driver safety"],
        technical_actors=["Vehicle Gateway", "Telematics Ingestion Service", "Geofencing Engine"],
        domain_entities=["Vehicle", "Trip", "Driver", "Telemetry Event", "Maintenance Record"],
        workflows=["Telemetry uplink", "Geofence/rule evaluation", "Trip history reporting"],
        external_systems=["Dealership/maintenance system"],
        databases=["Time-series telemetry store"],
        communication_protocols=["MQTT", "CAN bus", "OBD-II"],
        recommended_documents=["Vehicle Telemetry Architecture", "Fleet Dashboard Flow"],
        recommended_diagrams=["Vehicle telemetry sequence diagram"],
    ),
    "construction": dict(
        business_domain="Construction / Project & Site Management",
        project_category="Site & Safety Management",
        application_category="Construction Project Management System",
        system_type="Project, schedule, and site-safety tracking system",
        architecture_style="Layered service architecture",
        deployment_model="Cloud",
        domain_expert_persona="Construction Systems Architect",
        technical_constraints=["Document/BIM versioning", "Offline-capable site data capture"],
        business_constraints=["Regulatory safety compliance", "Budget/schedule variance control"],
        technical_actors=["Project Service", "Site & Safety Service", "Document/BIM Service"],
        domain_entities=["Project", "Phase", "Task", "Site Inspection", "Equipment Assignment"],
        workflows=["Project/phase setup", "Site inspection logging", "Safety incident escalation"],
        external_systems=["BIM authoring tools"],
        databases=["Relational project store", "Object storage for drawings/BIM"],
        recommended_documents=["Site Safety Report", "Project Schedule Architecture"],
        recommended_diagrams=["Project/task ER diagram", "Site inspection workflow diagram"],
    ),
    "agriculture": dict(
        business_domain="Agriculture / Farm Monitoring",
        project_category="Crop & Soil Monitoring",
        application_category="Agricultural AIoT Platform",
        system_type="Field sensor monitoring and irrigation control system",
        architecture_style="Edge-to-cloud telemetry",
        deployment_model="Hybrid (field gateway + cloud)",
        domain_expert_persona="Agricultural Systems Architect",
        technical_constraints=["Sparse rural connectivity", "Battery-powered field sensors"],
        business_constraints=["Water usage efficiency", "Crop yield optimization"],
        technical_actors=["Field Gateway", "Agronomic Analytics Service", "Irrigation Control Service"],
        domain_entities=["Field", "Sensor", "Reading", "Irrigation Event"],
        workflows=["Sensor telemetry ingestion", "Agronomic evaluation", "Irrigation recommendation/actuation"],
        databases=["Time-series sensor store"],
        communication_protocols=["MQTT", "LoRaWAN"],
        sensors=["Soil moisture", "Weather", "Crop stage"],
        edge_components=["Field gateway"],
        recommended_documents=["Field Sensor Architecture", "Irrigation Flow Report"],
        recommended_diagrams=["Field telemetry sequence diagram"],
    ),
    "retail_ecommerce": dict(
        business_domain="Retail / E-commerce",
        project_category="Order & Inventory Management",
        application_category="E-commerce Platform",
        system_type="Order, inventory, and fulfillment system",
        architecture_style="Layered service architecture",
        deployment_model="Cloud",
        domain_expert_persona="Retail Commerce Solutions Architect",
        technical_constraints=["Inventory oversell prevention", "Checkout latency under load"],
        business_constraints=["Peak-season scalability", "Customer order accuracy"],
        technical_actors=["Catalog Service", "Inventory Service", "Order & Payment Service"],
        domain_entities=["Product", "Order", "Inventory Item", "Shipment"],
        workflows=["Checkout", "Stock reservation", "Payment capture", "Fulfillment"],
        external_systems=["Payment gateway", "Shipping carrier"],
        databases=["Relational order/inventory store", "Search index"],
        recommended_documents=["Order Flow Architecture", "Inventory Management Report"],
        recommended_diagrams=["Checkout sequence diagram", "Order/inventory ER diagram"],
    ),
    "logistics_supply_chain": dict(
        business_domain="Logistics / Supply Chain",
        project_category="Shipment Tracking & Fleet Routing",
        application_category="Logistics Management Platform",
        system_type="Shipment tracking and fleet routing system",
        architecture_style="Event-driven ingestion with routing services",
        deployment_model="Cloud",
        domain_expert_persona="Logistics Systems Architect",
        technical_constraints=["High-throughput GPS/scan-event ingestion"],
        business_constraints=["On-time delivery targets", "Fleet utilization efficiency"],
        technical_actors=["Shipment Service", "Fleet & Routing Service", "Tracking Ingestion Service"],
        domain_entities=["Shipment", "Vehicle", "Tracking Event", "Route"],
        workflows=["Shipment booking", "Fleet assignment", "In-transit tracking", "Delivery confirmation"],
        databases=["Time-series tracking store", "Relational shipment store"],
        recommended_documents=["Shipment Tracking Architecture", "Fleet Routing Report"],
        recommended_diagrams=["Shipment tracking sequence diagram"],
    ),
    "hvac": dict(
        business_domain="HVAC / Building Climate Control",
        project_category="Climate Control & Energy Optimization",
        application_category="HVAC AIoT Platform",
        system_type="Edge-to-cloud HVAC monitoring and control system",
        architecture_style="Event-driven, edge-to-cloud",
        deployment_model="Hybrid (building controller + cloud)",
        domain_expert_persona="HVAC Systems Architect",
        technical_constraints=["Real-time setpoint control latency", "Legacy BACnet/Modbus device integration"],
        business_constraints=["Energy cost reduction", "Occupant comfort compliance"],
        technical_actors=["Building Controller", "Climate Analytics Service", "Alerting Service"],
        domain_entities=["Air Handling Unit", "Zone", "Setpoint", "Fault Alert"],
        workflows=["Sensor telemetry ingestion", "Setpoint evaluation", "Fault detection and escalation"],
        external_systems=["Building Management System (BMS)"],
        databases=["Time-series store", "Relational configuration store"],
        communication_protocols=["BACnet", "Modbus", "MQTT"],
        sensors=["Temperature", "Humidity", "CO2", "Airflow"],
        devices=["Air handling unit controller", "Zone thermostat"],
        recommended_documents=["HVAC System Architecture", "Energy Optimization Report"],
        recommended_diagrams=["Zone control sequence diagram", "HVAC topology diagram"],
    ),
    "insurance": dict(
        business_domain="Insurance / Policy & Claims Management",
        project_category="Policy Administration & Claims Processing",
        application_category="Insurance Platform",
        system_type="Policy, underwriting, and claims management system",
        architecture_style="Layered service architecture with actuarial rules engine",
        deployment_model="Cloud, regulatory-isolated environment",
        domain_expert_persona="Insurance Solutions Architect",
        technical_constraints=["Actuarial rules versioning", "Auditable claims decisioning"],
        business_constraints=["Regulatory compliance", "Fraud prevention"],
        technical_actors=["Policy Service", "Claims Adjudication Service", "Underwriting Rules Engine"],
        domain_entities=["Policy", "Claim", "Policyholder", "Premium"],
        workflows=["Policy issuance", "Premium calculation", "Claim submission", "Claim adjudication"],
        external_systems=["Payment processor", "Third-party actuarial data provider"],
        databases=["Relational policy/claims store"],
        recommended_documents=["Claims Workflow Architecture", "Underwriting Rules Report"],
        recommended_diagrams=["Claims adjudication sequence diagram", "Policy/claim ER diagram"],
    ),
    "energy": dict(
        business_domain="Energy / Utilities & Grid Operations",
        project_category="Grid Monitoring & Energy Management",
        application_category="Energy AIoT Platform",
        system_type="Edge-to-cloud grid telemetry and demand management system",
        architecture_style="Event-driven, edge-to-cloud",
        deployment_model="Hybrid (substation gateway + cloud)",
        domain_expert_persona="Energy Systems Architect",
        technical_constraints=["Grid-critical real-time latency", "NERC-CIP segregation of OT/IT networks"],
        business_constraints=["Regulatory compliance (grid reliability standards)", "Outage minimization"],
        technical_actors=["Substation Gateway", "Grid Analytics Service", "Demand Response Engine"],
        domain_entities=["Smart Meter", "Substation", "Outage Event", "Load Reading"],
        workflows=["Meter telemetry ingestion", "Load forecasting", "Outage detection and escalation"],
        external_systems=["SCADA/grid control systems"],
        databases=["Time-series store", "Relational grid asset store"],
        communication_protocols=["DNP3", "MQTT", "OPC-UA"],
        sensors=["Voltage", "Current", "Power factor"],
        devices=["Smart meter", "Substation gateway"],
        recommended_documents=["Grid Telemetry Architecture", "Outage Response Report"],
        recommended_diagrams=["Grid telemetry sequence diagram", "Substation topology diagram"],
    ),
    "government": dict(
        business_domain="Government / Public Sector Services",
        project_category="Citizen Services & Records Management",
        application_category="Government Services Platform",
        system_type="Citizen-facing service and records management system",
        architecture_style="Layered service architecture with strict accessibility/compliance controls",
        deployment_model="Government cloud (FedRAMP-style) or on-prem municipal network",
        domain_expert_persona="Government Solutions Architect",
        technical_constraints=["Accessibility compliance (Section 508-style)", "Long-term records retention"],
        business_constraints=["Regulatory compliance", "Public transparency requirements"],
        technical_actors=["Citizen Portal Service", "Records Management Service", "Permit/Application Engine"],
        domain_entities=["Citizen", "Application", "Permit", "Public Record"],
        workflows=["Application submission", "Permit review", "Public record request"],
        external_systems=["Government identity verification service"],
        databases=["Relational records store"],
        recommended_documents=["Citizen Services Architecture", "Records Retention Report"],
        recommended_diagrams=["Application review sequence diagram", "Records ER diagram"],
    ),
    "manufacturing": dict(
        business_domain="Manufacturing / Production Operations",
        project_category="Production Planning & Quality Management",
        application_category="Manufacturing Execution Platform",
        system_type="Shop-floor production and quality management system",
        architecture_style="Layered service architecture with MES/ERP integration",
        deployment_model="Hybrid (shop-floor systems + cloud)",
        domain_expert_persona="Manufacturing Systems Architect",
        technical_constraints=["Real-time shop-floor data capture", "ERP/MES integration"],
        business_constraints=["Production throughput targets", "Quality/defect-rate control"],
        technical_actors=["MES Integration Service", "Quality Control Service", "Production Scheduling Service"],
        domain_entities=["Work Order", "Production Line", "Quality Inspection", "Bill of Materials"],
        workflows=["Work order scheduling", "Production tracking", "Quality inspection", "Defect escalation"],
        external_systems=["ERP system", "MES system"],
        databases=["Relational production store"],
        recommended_documents=["Production Workflow Architecture", "Quality Control Report"],
        recommended_diagrams=["Production line sequence diagram", "Work order ER diagram"],
    ),
    "smart_building": dict(
        business_domain="Smart Building / Facility Automation",
        project_category="Building Automation & Occupancy Management",
        application_category="Smart Building AIoT Platform",
        system_type="Edge-to-cloud building automation and energy management system",
        architecture_style="Event-driven, edge-to-cloud",
        deployment_model="Hybrid (building controller + cloud)",
        domain_expert_persona="Smart Building Systems Architect",
        technical_constraints=["Legacy BACnet/Modbus device integration", "Real-time access control latency"],
        business_constraints=["Energy cost reduction", "Occupant safety and comfort"],
        technical_actors=["Building Automation Controller", "Occupancy Analytics Service", "Access Control Service"],
        domain_entities=["Zone", "Occupancy Sensor", "Access Event", "Energy Reading"],
        workflows=["Occupancy telemetry ingestion", "Energy optimization", "Access control evaluation"],
        external_systems=["Building Management System (BMS)"],
        databases=["Time-series store", "Relational configuration store"],
        communication_protocols=["BACnet", "MQTT", "Zigbee"],
        sensors=["Occupancy", "Temperature", "Light level"],
        devices=["Building controller", "Access control reader"],
        recommended_documents=["Building Automation Architecture", "Energy Management Report"],
        recommended_diagrams=["Occupancy telemetry sequence diagram", "Building automation topology diagram"],
    ),
    "esg": dict(
        business_domain="ESG / Sustainability & Compliance Reporting",
        project_category="Sustainability Metrics & Compliance Reporting",
        application_category="ESG Reporting Platform",
        system_type="Sustainability data aggregation and compliance reporting system",
        architecture_style="Layered service architecture with data aggregation pipeline",
        deployment_model="Cloud",
        domain_expert_persona="ESG Solutions Architect",
        technical_constraints=["Multi-source data aggregation", "Auditable reporting trail"],
        business_constraints=["Regulatory disclosure requirements", "Data accuracy for public reporting"],
        technical_actors=["Data Aggregation Service", "Reporting Engine", "Compliance Audit Service"],
        domain_entities=["Emission Record", "Sustainability Metric", "Compliance Report", "Data Source"],
        workflows=["Data source ingestion", "Metric aggregation", "Report generation", "Compliance audit"],
        external_systems=["Third-party emissions data provider"],
        databases=["Relational metrics store"],
        recommended_documents=["ESG Data Architecture", "Sustainability Compliance Report"],
        recommended_diagrams=["Data aggregation sequence diagram", "ESG metrics ER diagram"],
    ),
    "ai_ml_platform": dict(
        business_domain="AI / Machine Learning Platform",
        project_category="AI Inference & Retrieval System",
        application_category="AI/RAG Platform",
        system_type="Retrieval-augmented generation pipeline",
        architecture_style="AI inference & retrieval pipeline",
        deployment_model="Cloud",
        domain_expert_persona="AI Solutions Architect",
        technical_constraints=["Grounding/hallucination control", "Provider fallback"],
        technical_actors=["Inference Orchestrator", "Model Gateway"],
        domain_entities=["Document", "Chunk", "Embedding", "Query"],
        workflows=["Document ingestion", "Retrieval", "Grounded generation"],
        databases=["Vector store"],
        ai_components=["Embedding model", "LLM provider"],
        recommended_documents=["AI Pipeline Architecture", "Evaluation Report"],
    ),
    "event_driven_platform": dict(
        business_domain="General Software / Event-Driven Systems",
        project_category="Event-Driven Microservices",
        application_category="General Software Platform",
        system_type="Event-driven microservices system",
        architecture_style="Event-driven microservices",
        deployment_model="Cloud",
        domain_expert_persona="Solutions Architect",
        technical_actors=["Domain Services", "Event Backbone"],
        domain_entities=["Domain Event", "Aggregate"],
        workflows=["Event publication", "Event consumption"],
        recommended_documents=["Event Architecture"],
    ),
    "generic_software": dict(
        business_domain="General Software",
        project_category="General Business Application",
        application_category="General Software Platform",
        system_type="Layered web/API service",
        architecture_style="Layered service architecture",
        deployment_model="Cloud",
        domain_expert_persona="Solutions Architect",
        technical_actors=["Application Service"],
        domain_entities=["Resource", "Event"],
        workflows=["Primary request flow"],
        recommended_documents=["Architecture Overview"],
    ),
}


def _score_industry(lowered_text: str) -> Optional[str]:
    """Highest keyword-hit-count industry, or None if nothing matched."""
    best_key, best_score = None, 0
    for industry, keywords in _INDUSTRY_KEYWORDS.items():
        score = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", lowered_text))
        if score > best_score:
            best_key, best_score = industry, score
    return best_key


_DETECTION_FIELDS = (
    "physical_assets", "logical_assets", "sensors", "devices",
    "communication_protocols", "apis", "databases", "ai_components",
    "cloud_components", "edge_components",
)


def _build_relationships(entities: List[str], actors: List[str], workflows: List[str]) -> List[str]:
    """
    Deterministic relationship templating from already-known entities/actors/
    workflows — no fabrication beyond what the frame itself already asserts.
    Only used by the offline fallback; the LLM path supplies relationships
    directly as part of its structured response.
    """
    relationships: List[str] = []
    if actors and entities:
        relationships.append(f"{actors[0]} manages {entities[0]}")
    for left, right in zip(entities, entities[1:]):
        relationships.append(f"{left} relates to {right}")
    if workflows and entities:
        relationships.append(f"{workflows[0]} operates on {entities[0]}")
    return relationships


def classify_rule_based(context: CognitiveContext) -> ProjectUnderstandingFrame:
    """Offline fallback classifier — never raises, never returns an empty stub."""
    text = context.perception.normalized_text if context.perception else (context.task or "")
    lowered = text.lower()
    entities = set(context.context.entities if context.context else context.entities)

    industry = _score_industry(lowered)
    if industry is None:
        if entities & _IOT_ENTITY_HINTS:
            industry = "industrial_iot"
        elif entities & _AI_ENTITY_HINTS:
            industry = "ai_ml_platform"
        elif entities & _EVENT_ENTITY_HINTS:
            industry = "event_driven_platform"
        else:
            industry = "generic_software"

    defaults = _INDUSTRY_DEFAULTS.get(industry, _INDUSTRY_DEFAULTS["generic_software"])
    subject = context.context.subject if context.context else text[:200]
    base_actors = list(context.context.actors) if context.context else []

    data: Dict[str, Any] = {
        "industry": industry,
        "business_problem": f"Stakeholders need: {subject}",
        "engineering_problem": (
            f"Design and implement a {defaults.get('system_type', 'system')} that satisfies: {subject}"
        ),
        "actors": base_actors or ["End User", "System Administrator"],
        "confidence": 0.55,
        "classification_method": "rule_based_fallback",
    }
    data.update({k: v for k, v in defaults.items() if k not in data})

    # Fill remaining detection fields (assets/sensors/devices/protocols/APIs/
    # databases/...) from the shared DomainProfile registry so the offline
    # path is never thinner than the LLM path on these fields — see
    # ocif/engines/domain_profiles.py.
    profile = get_domain_profile(industry)
    for detection_field in _DETECTION_FIELDS:
        if not data.get(detection_field):
            profile_value = getattr(profile, detection_field)
            if profile_value:
                data[detection_field] = list(profile_value)

    data["relationships"] = _build_relationships(
        entities=data.get("domain_entities", []),
        actors=data["actors"],
        workflows=data.get("workflows", []),
    )

    return ProjectUnderstandingFrame(**data)


# ---------------------------------------------------------------------------
# LLM-driven classifier
# ---------------------------------------------------------------------------

_CLASSIFICATION_JSON_INSTRUCTION = (
    "Respond ONLY with a JSON object (no prose outside the JSON) with these keys: "
    '{"industry": str (a short slug like "healthcare", "industrial_iot", "education", '
    '"banking_fintech", "automotive", "construction", "agriculture", "retail_ecommerce", '
    '"logistics_supply_chain", "ai_ml_platform", "event_driven_platform", "hvac", "insurance", '
    '"energy", "government", "manufacturing", "smart_building", "esg", or "generic_software" '
    'if truly none fit — invent a new short slug only if the project genuinely belongs to none '
    'of these), "business_domain": str, "business_problem": str, "engineering_problem": str, '
    '"project_category": str, "application_category": str, "system_type": str, '
    '"architecture_style": str, "deployment_model": str, '
    '"technical_constraints": [str], "business_constraints": [str], "actors": [str], '
    '"technical_actors": [str], "physical_assets": [str], "logical_assets": [str], '
    '"domain_entities": [str], "relationships": [str], "workflows": [str], '
    '"data_flow": str, "control_flow": str, "external_systems": [str], "apis": [str], '
    '"databases": [str], "communication_protocols": [str], "sensors": [str], "devices": [str], '
    '"ai_components": [str], "cloud_components": [str], "edge_components": [str], '
    '"recommended_documents": [str], "recommended_diagrams": [str], "required_images": [str], '
    '"required_reports": [str], "domain_expert_persona": str '
    '(e.g. "Healthcare Solutions Architect", "Industrial IoT Solutions Architect"), '
    '"confidence": number between 0 and 1}.'
)


class ProjectUnderstandingEngine:
    """
    Classifies the incoming request into a ProjectUnderstandingFrame before
    Planning runs. Plain class (not a CognitiveEngine) — see module
    docstring for why. `classify()` is always safe to call and always
    returns a populated frame.
    """

    def __init__(self, inference: Optional[InferenceAdapter] = None) -> None:
        self.inference = inference or InferenceAdapter()
        self._cache: "OrderedDict[str, ProjectUnderstandingFrame]" = OrderedDict()

    async def classify(self, context: CognitiveContext) -> ProjectUnderstandingFrame:
        cached = self._cache.get(context.conversation_id)
        if cached is not None:
            self._cache.move_to_end(context.conversation_id)
            return cached

        frame = await self._classify_via_llm(context)
        if frame is None:
            frame = classify_rule_based(context)

        self._cache[context.conversation_id] = frame
        if len(self._cache) > _MAX_CACHE_SIZE:
            self._cache.popitem(last=False)
        return frame

    async def _classify_via_llm(self, context: CognitiveContext) -> Optional[ProjectUnderstandingFrame]:
        prompt = self._build_prompt(context)
        intent = context.intent or (context.context.intent.value if context.context and hasattr(context.context.intent, "value") else "general_engineering")
        payload = await self.inference.complete(prompt=prompt, intent=intent)
        if not payload:
            return None

        parsed = self._extract_json(payload["content"])
        if not parsed:
            return None

        try:
            valid_fields = ProjectUnderstandingFrame.model_fields
            data = {k: v for k, v in parsed.items() if k in valid_fields}
            data["classification_method"] = "llm"
            return ProjectUnderstandingFrame(**data)
        except Exception as exc:
            logger.warning(f"LLM project-understanding parse failed, using rule-based fallback: {exc}")
            return None

    def _build_prompt(self, context: CognitiveContext) -> str:
        frame = context.context
        text = context.perception.normalized_text if context.perception else context.task
        parts = [
            "You are AXIOM's Project Understanding classifier. Before any solution is designed, "
            "you deeply analyze what the project actually is — its industry, business domain, "
            "actors, entities, workflows, and required technical components — so the eventual "
            "solution reads like it was written by an experienced architect in THAT specific "
            "industry, not a generic software architect.",
            f"REQUEST: {text}",
        ]
        if frame:
            parts.append(f"PRELIMINARY INTENT: {frame.intent} | KEYWORDS DETECTED: {', '.join(frame.entities) or 'none'}")
            if frame.actors:
                parts.append(f"PRELIMINARY ACTORS: {', '.join(frame.actors)}")
        parts.append(_CLASSIFICATION_JSON_INSTRUCTION)
        return "\n\n".join(parts)

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        candidates = re.findall(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL) or [content]
        for candidate in candidates:
            try:
                data = json.loads(candidate.strip())
                if isinstance(data, dict) and "industry" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                continue
        return None
