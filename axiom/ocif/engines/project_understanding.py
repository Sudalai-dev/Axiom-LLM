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
    return ProjectUnderstandingFrame(**data)


# ---------------------------------------------------------------------------
# LLM-driven classifier
# ---------------------------------------------------------------------------

_CLASSIFICATION_JSON_INSTRUCTION = (
    "Respond ONLY with a JSON object (no prose outside the JSON) with these keys: "
    '{"industry": str (a short slug like "healthcare", "industrial_iot", "education", '
    '"banking_fintech", "automotive", "construction", "agriculture", "retail_ecommerce", '
    '"logistics_supply_chain", "ai_ml_platform", "event_driven_platform", or "generic_software" '
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
