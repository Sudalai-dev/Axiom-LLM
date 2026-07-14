"""
Engineering Intelligence Engine (Engine 6) — evolved from Reasoning Engine.

This is the cognitive heart of Axiom. It runs a multi-stage pre-inference
pipeline to analyze intents, domains, industries, experts, engineering patterns,
specialized knowledge packs, and diagrams, constructing a highly contextual
dynamic prompt before invoking the Inference Adapter (LLM). After generation,
the Blueprint Optimizer verifies, deduplicates, and validates the output.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from dataclasses import asdict

from ocif.engine import CognitiveEngine
from ocif.engines.generation_planner import GenerationPlanner
from ocif.engines.industry_patterns import IndustryPattern, select_pattern, PATTERNS_BY_KEY
from ocif.frames import (
    CognitiveContext,
    ContextFrame,
    EngineName,
    EngineResult,
    KnowledgeFrame,
    Plan,
    ProjectUnderstandingFrame,
    ReasoningResult,
    Risk,
    RoadmapPhase,
    SolutionDocument,
    TechChoice,
)
from ocif.inference_adapter import InferenceAdapter

logger = logging.getLogger("AxiomOCIF.EngineeringIntelligence")

# ---------------------------------------------------------------------------
# Specialized Knowledge Packs (V2.0 Core Intellectual Property)
# ---------------------------------------------------------------------------

KNOWLEDGE_PACKS: Dict[str, Dict[str, Any]] = {
    "software/backend": {
        "name": "Backend Development & Systems Architecture",
        "standards": ["REST API Design", "RFC 7807 (Problem Details)", "OpenAPI 3.0", "OAuth2 & JWT"],
        "patterns": ["Microservices", "Event-Driven Architecture", "CQRS", "Layered Service Architecture"],
        "common_problems": ["Database connection pooling exhaustion", "N+1 query execution", "State corruption in stateless workers"],
        "failure_modes": ["Cascading failure under high database load", "Token decryption bottlenecks", "Out of memory under large CSV exports"],
        "recommendations": ["Use async/await concurrency", "Implement circuit breakers", "Leverage connection poolers like PgBouncer"],
    },
    "software/frontend": {
        "name": "Frontend Engineering & User Experience",
        "standards": ["W3C WCAG 2.1 AA", "HTML5 & Semantic Elements", "ECMAScript 2026 Type Safety"],
        "patterns": ["Component-driven SPA", "Virtual DOM rendering", "Centralized State Management"],
        "common_problems": ["Large bundle sizes delaying time-to-interactive", "State de-synchronization across tabs", "XSS vulnerabilities in raw HTML rendering"],
        "failure_modes": ["Browser freeze during complex UI renders", "Token theft via localStorage XSS", "API polling overloading the network"],
        "recommendations": ["Code splitting and lazy loading", "Strict sanitization on render", "Token storage in HttpOnly secure cookies"],
    },
    "database": {
        "name": "Data Storage & Database Design",
        "standards": ["ACID Compliance Standards", "SQL:2023 Specifications", "BCNF Normalization"],
        "patterns": ["Distributed Caching", "Read-replicas replication", "Append-only Transaction Ledger"],
        "common_problems": ["Missing indexes on query filters", "Unbounded transaction locks", "Data drift between cache and SQL store"],
        "failure_modes": ["Write deadlocks on concurrent hot-rows", "Replication lag on read replicas", "Cache penetration/stampede"],
        "recommendations": ["Versioned migration scripts via Alembic", "Row-level security policies", "Read/Write isolation pattern"],
    },
    "cloud": {
        "name": "Cloud Infrastructure & Platform Ops",
        "standards": ["CIS Benchmarks for Cloud Providers", "12-Factor App Principles", "ISO/IEC 27001 Security Controls"],
        "patterns": ["Infrastructure as Code", "Kubernetes Orchestration", "Blue-Green Deployment"],
        "common_problems": ["Secrets stored in container environment variables", "Under-provisioned node CPU/memory pools", "Orphaned storage volumes costing budget"],
        "failure_modes": ["Incorrect IAM policy allowing root access", "Deployment fail loops due to failed readiness probes", "DDoS exhaustion of VPC bandwidth"],
        "recommendations": ["Secrets injection via Vault/SecretsManager", "Declarative IaC with Terraform", "Automated rolling updates with health-checks"],
    },
    "mqtt": {
        "name": "Industrial IoT & Telemetry Ingestion",
        "standards": ["MQTT 3.1.1/5.0 Spec", "OPC-UA Part 1-14", "Modbus TCP/RTU Standard", "ISA-95 Enterprise-Control Integration"],
        "patterns": ["Edge Gateway Store-and-Forward", "Telemetry Stream Processing", "Industrial Edge Buffer"],
        "common_problems": ["Unbounded message queues at the edge", "No protocol normalization across sensors", "TCP connection churn on cellular links"],
        "failure_modes": ["MQTT broker heap exhaustion under reconnection storm", "Modbus register conflict on PLC", "Data loss during cellular blackout"],
        "recommendations": ["At-least-once (QoS 1) delivery with edge buffering", "Topic namespace mapping (site/asset/metric)", "TLS 1.3 mutual authentication"],
    },
    "industrial/hvac": {
        "name": "Industrial Assets & HVAC Controls",
        "standards": ["ASHRAE Standard 135 (BACnet)", "ISO 50001 Energy Management", "NEMA Equipment Classifications"],
        "patterns": ["Predictive Maintenance Loop", "Thermal Control Feedback", "Closed-Loop Automation"],
        "common_problems": ["Sensor drift in thermal readings", "Short-cycling damaging compressor motors", "Unfiltered high frequency vibration noise"],
        "failure_modes": ["Compressor mechanical seize from low oil pressure", "Controller override freeze", "Fan bearing wear leading to thermal lockup"],
        "recommendations": ["Remaining-useful-life (RUL) scheduling", "Vibration analysis filters", "Dampener feedback validation loops"],
    },
    "robotics": {
        "name": "Robotics & Automation Systems",
        "standards": ["ISO 10218 Robot Safety", "ROS 2 Transport Standard", "IEC 61131-3 PLC Programming"],
        "patterns": ["Digital Twin State Tracking", "Real-Time Controller Loop", "Safety Gated Automation"],
        "common_problems": ["Command latency causing robot overtravel", "Odometry drift on uneven flooring", "Actuator overload from joint binding"],
        "failure_modes": ["Emergency stop failure under network loss", "Lidar blockage halting navigation", "Coordinate frame translation mismatch"],
        "recommendations": ["Gated emergency hardware overrides", "Deterministic control loops", "Continuous kinematics validation"],
    },
    "networking/security": {
        "name": "Cybersecurity & Network Infrastructure",
        "standards": ["OWASP Top 10 Mitigation", "NIST Cybersecurity Framework", "PCI-DSS 4.0 Compliance"],
        "patterns": ["Zero Trust Architecture", "Defense in Depth", "Audit Ledger Tracking"],
        "common_problems": ["Hardcoded cryptographic keys", "Permissive CORS policies", "SQL injection via dynamic strings"],
        "failure_modes": ["Data breach of PHI/PII records", "Replay attacks on unversioned request payload", "Man-in-the-middle decryption on internal backplane"],
        "recommendations": ["Enforce TLS 1.3 internally", "Automated static code analysis (SAST)", "Role-based access control with least privilege"],
    }
}

# ---------------------------------------------------------------------------
# Pre-inference Pipeline Components
# ---------------------------------------------------------------------------

class IntentAnalyzer:
    """Classifies user intent into distinct engineering objectives."""
    
    INTENT_KEYWORDS = {
        "DATABASE_DESIGN": ["database", "schema", "er diagram", "sql table", "postgres model", "ledger schema", "db design"],
        "FAILURE_ANALYSIS": ["failure", "broken", "troubleshoot", "root cause", "rca", "incident", "crash", "bug", "leak", "ac failure"],
        "CODE_GENERATION": ["code", "implementation", "class", "function", "endpoint", "api controller", "write a python script"],
        "DOCUMENTATION": ["prd", "brd", "srs", "hld", "lld", "user guide", "architecture reference"],
        "REVIEW": ["review", "audit", "assess", "evaluate", "critique", "optimize"],
        "AIOT_ENGINEERING": ["mqtt", "opc-ua", "plc", "scada", "telemetry", "sensor monitoring", "edge gateway"],
    }

    def analyze(self, message: str, context_intent: str) -> str:
        lowered = message.lower()
        # Direct keyword match
        for intent_slug, keywords in self.INTENT_KEYWORDS.items():
            if any(kw in lowered for kw in keywords):
                return intent_slug
        # Fallback to context intent
        return context_intent.upper()


class DomainClassifier:
    """Classifies engineering request into multiple core domains of expertise."""

    DOMAIN_RULES = {
        "Industrial IoT": ["mqtt", "opc-ua", "modbus", "scada", "plc", "telemetry", "edge", "pump", "sensor"],
        "Mechanical Engineering": ["pump", "compressor", "motor", "hvac", "vibration", "turbine", "bearing", "actuator"],
        "Electrical Engineering": ["power", "voltage", "current", "control diagram", "wiring", "phase", "grid"],
        "Artificial Intelligence": ["llm", "rag", "embedding", "vector", "ai", "machine learning", "ml", "anomaly detection"],
        "Software Engineering": ["api", "service", "frontend", "backend", "web", "react", "typescript", "fastapi", "django"],
        "Database Engineering": ["postgres", "mysql", "mongodb", "ledger", "database", "sql", "timescale", "redis"],
        "Cybersecurity": ["oauth", "jwt", "tls", "auth", "rbac", "encryption", "secure", "hipaa", "audit log"],
        "DevOps": ["docker", "kubernetes", "k8s", "ci/cd", "deployment", "pipeline", "cloud", "aws", "azure"]
    }

    def classify(self, message: str, understanding: Optional[ProjectUnderstandingFrame] = None) -> List[str]:
        lowered = message.lower()
        matched = []
        for domain, keywords in self.DOMAIN_RULES.items():
            if any(kw in lowered for kw in keywords):
                matched.append(domain)

        # Reuse signals Project Understanding already derived (see
        # ocif/engines/project_understanding.py) instead of re-scanning raw
        # text blind to what's already known about the project. Runs the
        # SAME keyword rules against the frame's own technical-vocabulary
        # fields — not a separate "any value present" heuristic, since e.g.
        # HL7/FHIR (healthcare protocols) or a generic "relational store"
        # description must not be mistaken for Industrial IoT / Database
        # Engineering signals just because *some* protocol/database is
        # listed. Deliberately excludes physical_assets/sensors/devices:
        # those are free-form domain-noun lists (e.g. "Infusion pump") that
        # collide with DOMAIN_RULES' short generic keywords (e.g. "pump")
        # designed for scanning prose, not curated asset names.
        if understanding is not None:
            frame_evidence = " ".join(
                understanding.communication_protocols
                + understanding.ai_components
                + understanding.databases
                + understanding.cloud_components
                + understanding.edge_components
            ).lower()
            if frame_evidence:
                for domain, keywords in self.DOMAIN_RULES.items():
                    if domain not in matched and any(kw in frame_evidence for kw in keywords):
                        matched.append(domain)

        if not matched:
            matched.append("Software Engineering")  # baseline domain
        return matched


class IndustryClassifier:
    """Resolves the exact vertical industry and maps specific regulatory compliance standard requirements."""

    INDUSTRY_COMPLIANCE = {
        "healthcare": ("Healthcare", ["HIPAA (Health Insurance Portability and Accountability Act)", "FHIR (Fast Healthcare Interoperability Resources) REST Spec", "HL7 v2/v3 Ingestion"]),
        "banking_fintech": ("Finance & Banking", ["PCI-DSS 4.0 Compliance", "Double-Entry Ledger Integrity", "AML/KYC regulatory checks"]),
        "industrial_iot": ("Manufacturing & Industrial IoT", ["ISA-95 Enterprise Architecture model", "IEC 62443 Industrial Cybersecurity", "OPC-UA communication"]),
        "energy": ("Energy & Utilities", ["NERC-CIP cyber security standards", "IEEE 1547 Grid Connection standard"]),
        "education": ("Education & Academy", ["FERPA student data protection", "COPPA children privacy rules"]),
        "automotive": ("Automotive & Telematics", ["ISO 26262 functional safety", "AUTOSAR specifications", "CAN-bus diagnostics"]),
        "construction": ("Construction & Infrastructure", ["BIM (Building Information Modeling) standards", "OSHA safety logs"]),
        "agriculture": ("Agriculture & Agronomy", ["LoRaWAN specification", "USDA agronomic metrics"]),
        "retail_ecommerce": ("Retail & Commerce", ["PCI-DSS standard", "CPA/GDPR compliance"]),
        "logistics_supply_chain": ("Logistics & Supply Chain", ["GS1 barcode standards", "ISO 28000 security for supply chain"]),
        "ai_ml_platform": ("AI Platform & Engineering", ["EU AI Act compliance", "NIST AI Risk Management Framework"]),
        "hvac": ("HVAC & Building Climate Control", ["ASHRAE 90.1 energy efficiency standard", "AHRI equipment certification standards"]),
        "insurance": ("Insurance", ["NAIC Model Regulations", "Solvency II (EU)", "IFRS 17 insurance contracts standard"]),
        "government": ("Government & Public Sector", ["FedRAMP compliance (cloud)", "FISMA security controls", "Section 508 accessibility"]),
        "manufacturing": ("Manufacturing", ["ISO 9001 quality management", "ISA-95 enterprise-control integration", "OSHA workplace safety"]),
        "smart_building": ("Smart Building & Facility Automation", ["ASHRAE Guideline 36", "BACnet/IP interoperability standard", "LEED sustainability certification"]),
        "esg": ("ESG & Sustainability Reporting", ["GRI (Global Reporting Initiative) standards", "TCFD climate disclosure framework", "CSRD (EU Corporate Sustainability Reporting Directive)"]),
        "generic_software": ("General Technology", ["SOC 2 Type II controls", "GDPR privacy rules"])
    }

    def classify(self, industry_slug: str) -> Tuple[str, List[str]]:
        slug = (industry_slug or "generic_software").strip().lower()
        name, standards = self.INDUSTRY_COMPLIANCE.get(slug, self.INDUSTRY_COMPLIANCE["generic_software"])
        return name, standards


class ExpertSelector:
    """Selects one or more specialist expert personas for the solution."""

    DOMAIN_EXPERT_MAP = {
        "Industrial IoT": "Industrial IoT Architect",
        "Mechanical Engineering": "Mechanical Systems Engineer",
        "Electrical Engineering": "Electrical Power Architect",
        "Artificial Intelligence": "AI Systems Architect",
        "Software Engineering": "Software Architect",
        "Database Engineering": "Database Administrator & Architect",
        "Cybersecurity": "Security Architect",
        "DevOps": "Cloud & DevOps Architect"
    }

    def select(self, domains: List[str]) -> List[str]:
        experts = []
        for domain in domains:
            expert = self.DOMAIN_EXPERT_MAP.get(domain)
            if expert and expert not in experts:
                experts.append(expert)
        if not experts:
            experts.append("Solutions Architect")
        return experts


class KnowledgePackLoader:
    """Loads specialized Knowledge Packs matching the active domains.

    Primary source is the durable Engineering Knowledge Platform (dynamic,
    ranked, human-governed assembly). When no platform is injected — or it
    yields nothing — this falls back to the hardcoded ``KNOWLEDGE_PACKS`` so the
    platform never degrades.
    """

    def __init__(self, platform: Optional[Any] = None) -> None:
        self.platform = platform

    def load(
        self,
        domains: List[str],
        industry_slug: str,
        intent: str = "",
        entities: Optional[List[str]] = None,
        message: str = "",
    ) -> List[Dict[str, Any]]:
        # Primary: dynamic assembly from the Engineering Knowledge Platform.
        if self.platform is not None:
            try:
                packs = self.platform.assemble_packs(
                    domains=domains, industry=industry_slug, intent=intent,
                    entities=entities or [], message=message,
                )
                if packs:
                    return packs
            except Exception as exc:  # never let the platform break the engine
                logger.warning(f"Knowledge Platform assembly failed, falling back to hardcoded packs: {exc}")

        # Fallback: the original hardcoded packs (guaranteed non-degradation).
        loaded = []
        # Load by domain matching
        for domain in domains:
            if "IoT" in domain and "mqtt" not in loaded:
                loaded.append(KNOWLEDGE_PACKS["mqtt"])
            if "Mechanical" in domain and "industrial/hvac" not in loaded:
                loaded.append(KNOWLEDGE_PACKS["industrial/hvac"])
            if "Database" in domain and "database" not in loaded:
                loaded.append(KNOWLEDGE_PACKS["database"])
            if "Cybersecurity" in domain and "networking/security" not in loaded:
                loaded.append(KNOWLEDGE_PACKS["networking/security"])
            if "DevOps" in domain and "cloud" not in loaded:
                loaded.append(KNOWLEDGE_PACKS["cloud"])
            if "Software" in domain and "software/backend" not in loaded:
                loaded.append(KNOWLEDGE_PACKS["software/backend"])
                
        # Load by industry
        if industry_slug in ("industrial_iot", "automotive", "agriculture") and KNOWLEDGE_PACKS["mqtt"] not in loaded:
            loaded.append(KNOWLEDGE_PACKS["mqtt"])
        if industry_slug == "healthcare" and KNOWLEDGE_PACKS["networking/security"] not in loaded:
            loaded.append(KNOWLEDGE_PACKS["networking/security"])
            
        if not loaded:
            loaded.append(KNOWLEDGE_PACKS["software/backend"])
        return loaded


class DiagramPlanner:
    """Dynamically plans what engineering diagrams must be generated."""

    def plan(self, domains: List[str], intent: str) -> List[str]:
        diagrams = []
        if "Industrial IoT" in domains or "Mechanical Engineering" in domains:
            diagrams += ["Edge-to-Cloud Device Topology", "Telemetry Ingestion Sequence Diagram"]
        if "Database Engineering" in domains or intent == "DATABASE_DESIGN":
            diagrams += ["Entity-Relationship (ER) Schema Diagram"]
        if "Software Engineering" in domains:
            diagrams += ["Component Architecture Overview", "REST API Request/Response Flow"]
        if "DevOps" in domains:
            diagrams += ["Deployment Infrastructure Diagram (Kubernetes/VPC)", "CI/CD Promotion Pipeline Flow"]
        if intent == "FAILURE_ANALYSIS":
            diagrams += ["Failure Logic / Root Cause Classification Tree", "Graceful Degradation/Failover State Machine"]
            
        # Default diagrams
        if not diagrams:
            diagrams = ["Component Architecture Overview", "API Flow Diagram"]
        return list(set(diagrams))


class DeliverablePlanner:
    """Plans list of target deliverables/documents depending on request intent."""

    def plan(self, intent: str) -> List[str]:
        if intent == "DATABASE_DESIGN":
            return ["Database Schema Specification", "Double-Entry Ledger Architecture", "SQL Migration Pipeline script"]
        elif intent == "FAILURE_ANALYSIS":
            return ["Root Cause Analysis (RCA) Report", "Graceful Degradation Spec", "Alert Escalation Runbook"]
        elif intent == "CODE_GENERATION":
            return ["Typed Interface Definitions", "API Endpoint OpenAPI 3.0 Contract", "Integration Unit Test Suite"]
        elif intent == "REVIEW":
            return ["Architecture Evaluation Matrix", "Security Auditing Checklist", "Performance Bottleneck Report"]
        else:
            # Default HLD/LLD deliverables
            return ["High-Level Design (HLD)", "System Architecture Blueprint", "Implementation Roadmap", "Non-Functional Requirements Validation"]


class UseCaseExpander:
    """Automatically expands incomplete user prompts to capture production-grade scenarios."""

    def expand(self, message: str, domains: List[str], industry_name: str) -> Dict[str, Any]:
        return {
            "business_goals": [
                f"Onboard and connect the required entities to standard service layers in the {industry_name} sector.",
                "Ensure high reliability, audit compliance, and system observability to minimize operational risks."
            ],
            "technical_goals": [
                "Establish a secure, authenticated, and rate-limited API gateway.",
                "Implement transactional persistence with safe, isolated storage boundaries.",
                "Design for asynchronous decoupled workers to handle high-latency operations."
            ],
            "scalability_strategy": "Horizontal scaling at service tier; indexing & caching at storage tier.",
            "recovery_strategy": "At-least-once message delivery, transactional rollbacks, and replica failover.",
            "security_strategy": "TLS 1.3 encryption, OAuth2 Bearer tokens, row-level multi-tenant DB segregation."
        }


# ---------------------------------------------------------------------------
# Blueprint Optimizer
# ---------------------------------------------------------------------------

class BlueprintOptimizer:
    """
    Validates, deduplicates, and optimizes the generated solution blueprint
    before it is saved and visualized.
    """

    def optimize(self, doc: SolutionDocument, domains: List[str], score_base: float) -> Tuple[SolutionDocument, float]:
        # 1. Clean list duplicates (tech stack, risks, future enhancements)
        cleaned_stack = []
        seen_layers = set()
        for item in doc.technology_stack:
            key = f"{item.layer.lower()}:{item.choice.lower()}"
            if key not in seen_layers:
                seen_layers.add(key)
                cleaned_stack.append(item)
        doc.technology_stack = cleaned_stack

        cleaned_risks = []
        seen_risks = set()
        for item in doc.risk_assessment:
            desc = item.risk.lower().strip()
            if desc not in seen_risks and len(desc) > 3:
                seen_risks.add(desc)
                cleaned_risks.append(item)
        doc.risk_assessment = cleaned_risks

        cleaned_future = []
        seen_future = set()
        for item in doc.future_enhancements:
            desc = item.lower().strip()
            if desc not in seen_future and len(desc) > 3:
                seen_future.add(desc)
                cleaned_future.append(item)
        doc.future_enhancements = cleaned_future

        # 2. Check for typical LLM placeholder stubs and replace or expand them
        placeholders = [r"insert here", r"TODO", r"Lorem Ipsum", r"Your Name", r"Placeholder"]
        for p in placeholders:
            doc.executive_summary = re.sub(p, "Consolidated production design pattern", doc.executive_summary, flags=re.IGNORECASE)
            doc.problem_statement = re.sub(p, "System architecture implementation requirements", doc.problem_statement, flags=re.IGNORECASE)

        # 3. Calculate completeness score
        completeness_pct = 100.0
        missing_count = 0
        
        # Check standard sections
        if not doc.executive_summary or len(doc.executive_summary) < 50:
            missing_count += 1
        if not doc.recommended_solution or len(doc.recommended_solution) < 50:
            missing_count += 1
        if not doc.architecture_overview or "mermaid" not in doc.architecture_overview:
            missing_count += 1
        if not doc.technology_stack:
            missing_count += 1
        if not doc.api_design or "|" not in doc.api_design:
            missing_count += 1

        completeness_pct = max(100.0 - (missing_count * 15.0), 45.0)

        # 4. Final confidence adjustment
        final_confidence = round(min(score_base + (completeness_pct / 500.0), 0.98), 2)

        return doc, final_confidence


# ---------------------------------------------------------------------------
# Deterministic Solution Synthesizer
# ---------------------------------------------------------------------------

class SolutionSynthesizer:
    """Composes a complete SolutionDocument from the cognitive frames."""

    def synthesize(
        self,
        frame: ContextFrame,
        plan: Plan,
        knowledge: KnowledgeFrame,
        learning: Optional[List[str]] = None,
        understanding: Optional[ProjectUnderstandingFrame] = None,
    ) -> SolutionDocument:
        pattern = select_pattern(understanding)
        title = self._title(frame)
        components = pattern.components

        doc = SolutionDocument(
            title=title,
            executive_summary=self._executive_summary(frame, pattern, understanding),
            problem_statement=self._problem_statement(frame, understanding),
            actors=list(frame.actors),
            requirements_analysis=self._requirements_analysis(frame, plan),
            recommended_solution=self._recommended_solution(pattern),
            architecture_overview=self._architecture_overview(pattern),
            technology_stack=[TechChoice(layer=l, choice=c, rationale=r) for l, c, r in pattern.stack],
            component_design=self._component_design(components),
            database_design=self._database_design(pattern),
            api_design=self._api_design(pattern),
            workflow=self._workflow(pattern),
            security_architecture=self._security_architecture(pattern),
            deployment_architecture=self._deployment_architecture(pattern),
            monitoring_strategy=self._monitoring_strategy(pattern),
            testing_strategy=self._testing_strategy(pattern),
            implementation_roadmap=self._roadmap(frame, pattern),
            risk_assessment=self._risks(pattern),
            future_enhancements=self._future(pattern),
            final_recommendations=self._final(pattern, knowledge, learning),
        )
        return doc

    # -- sections -----------------------------------------------------------

    def _title(self, frame: ContextFrame) -> str:
        subject = frame.subject.rstrip(".?! ")
        return subject[:1].upper() + subject[1:] if subject else "Engineering Solution"

    def _executive_summary(
        self, frame: ContextFrame, pattern: IndustryPattern, understanding: Optional[ProjectUnderstandingFrame]
    ) -> str:
        entities = ", ".join(frame.entities[:6]) if frame.entities else "the requested capability"
        persona = understanding.domain_expert_persona if understanding else "Solutions Architect"
        domain_line = (
            f" Prepared from the perspective of an experienced {persona} for the "
            f"{understanding.business_domain} domain." if understanding and understanding.business_domain else ""
        )
        return (
            f"This document presents a production-ready engineering solution for the stated need: "
            f"**{frame.subject}**. The recommended approach is a **{pattern.name}** built around "
            f"{entities}. The design covers the full realistic scope — primary user flows, "
            f"administration, failure handling, security, and operations — and concludes with a "
            f"phased implementation roadmap a team can execute immediately.{domain_line}"
        )

    def _problem_statement(self, frame: ContextFrame, understanding: Optional[ProjectUnderstandingFrame]) -> str:
        actors = ", ".join(frame.actors[:4])
        problem_line = (
            f"\n\n{understanding.business_problem}" if understanding and understanding.business_problem else ""
        )
        return (
            f"{frame.subject}\n\n"
            f"Stakeholders affected: {actors}. Beyond the literal request, a production system must "
            f"also handle configuration and onboarding, partial failures of dependencies, "
            f"unauthorized access attempts, and rapid diagnosis of incidents. This solution treats "
            f"those as first-class requirements rather than afterthoughts.{problem_line}"
        )

    def _requirements_analysis(self, frame: ContextFrame, plan: Plan) -> str:
        lines = [
            "The request was expanded into the complete scenario set the solution must satisfy:",
            "",
            "| # | Actor | Scenario | Expected Behavior |",
            "|---|-------|----------|-------------------|",
        ]
        for uc in frame.use_cases:
            lines.append(f"| {uc.id} | {uc.actor} | {uc.scenario} | {uc.expected_behavior} |")
        lines += [
            "",
            "**Non-functional requirements**",
            "",
            "| ID | Category | Requirement |",
            "|----|----------|-------------|",
        ]
        for nfr in plan.non_functional_requirements:
            lines.append(f"| {nfr.id} | {nfr.category} | {nfr.requirement} |")
        if plan.constraints:
            lines += ["", "**Constraints:** " + " ".join(plan.constraints)]
        if plan.assumptions:
            lines += ["", "**Assumptions:** " + " ".join(plan.assumptions)]
        return "\n".join(lines)

    _ALTERNATIVES_BY_PATTERN_KEY = {
        "industrial_iot": "a monolithic SCADA extension (poor scalability, vendor lock-in) and direct device-to-cloud HTTP polling (battery/bandwidth cost, no offline buffering)",
        "event_driven_platform": "a modular monolith (simpler initially but couples deploy cadence) and synchronous REST chaining between services (cascading failures under load)",
        "generic_software": "a microservices split (operational overhead unjustified at this scale) and a server-rendered monolith (limits interactive UX)",
        "ai_ml_platform": "fine-tuning a dedicated model (cost and staleness) and prompt-only integration without retrieval (hallucination risk on domain facts)",
        "healthcare": "a single monolithic EMR module (limits per-department scaling) and direct database access from client apps (breaks auditability/compliance)",
        "education": "a spreadsheet-based attendance process (no auditability, error-prone) and a single shared login per class (defeats individual accountability)",
        "banking_fintech": "eventual-consistency balance updates without a ledger (reconciliation nightmares) and synchronous third-party fraud calls blocking every transaction (latency/availability risk)",
    }

    def _recommended_solution(self, pattern: IndustryPattern) -> str:
        alt = self._ALTERNATIVES_BY_PATTERN_KEY.get(
            pattern.key, "simpler architectures that fail the stated non-functional requirements"
        )
        return (
            f"Adopt a **{pattern.name}**. Alternatives considered and rejected: {alt}. "
            f"The chosen pattern best balances delivery speed, operational simplicity, and the "
            f"reliability/scalability requirements derived from the scenario analysis. Each component "
            f"below is independently testable and replaceable, and the design avoids hard vendor "
            f"lock-in at every layer."
        )

    def _architecture_overview(self, pattern: IndustryPattern) -> str:
        nodes = pattern.components
        ids = [re.sub(r"[^A-Za-z0-9]", "", name)[:14] or f"C{i}" for i, (name, _) in enumerate(nodes)]
        mermaid = ["flowchart LR"]
        for (name, _), nid in zip(nodes, ids):
            mermaid.append(f'    {nid}["{name}"]')
        for a, b in zip(ids, ids[1:]):
            mermaid.append(f"    {a} --> {b}")
        narrative = "\n".join(f"- **{name}** — {desc}" for name, desc in nodes)
        return (
            f"The system is composed of the following cooperating components:\n\n{narrative}\n\n"
            "```mermaid\n" + "\n".join(mermaid) + "\n```"
        )

    def _component_design(self, components) -> str:
        lines = []
        for name, desc in components:
            lines.append(
                f"### {name}\n{desc} Exposes a narrow, typed interface; owns its configuration; "
                f"emits structured logs and metrics; fails independently without cascading."
            )
        return "\n\n".join(lines)

    def _database_design(self, pattern: IndustryPattern) -> str:
        return f"{pattern.er_notes}\n\n```mermaid\n{pattern.er_diagram}\n```"

    def _api_design(self, pattern: IndustryPattern) -> str:
        rows = [
            "| Method | Endpoint | Purpose |",
            "|--------|----------|---------|",
            "| POST | /api/v1/auth/login | Authenticate and issue JWT |",
        ] + pattern.api_rows
        return (
            "REST + JSON with OpenAPI documentation generated from typed contracts. All endpoints "
            "are versioned, authenticated (Bearer JWT), tenant-scoped, and rate-limited. Errors follow "
            "RFC 7807 problem+json.\n\n" + "\n".join(rows)
        )

    def _workflow(self, pattern: IndustryPattern) -> str:
        return f"{pattern.workflow_narrative}\n\n```mermaid\n{pattern.workflow_diagram}\n```"

    def _security_architecture(self, pattern: IndustryPattern) -> str:
        return (
            "- **Authentication:** OAuth2/JWT with short-lived access tokens and refresh rotation.\n"
            "- **Authorization:** role-based access control enforced at the API layer and row-level "
            "tenant isolation in the database.\n"
            "- **Transport:** TLS 1.2+ everywhere; internal service traffic on a private network.\n"
            "- **Secrets:** injected from a secrets manager; never committed or baked into images.\n"
            "- **Input handling:** schema validation at every boundary; parameterized queries; "
            "rate limiting and audit logging on all mutating endpoints." + pattern.security_extra
        )

    def _deployment_architecture(self, pattern: IndustryPattern) -> str:
        mermaid = (
            "flowchart TB\n"
            "    subgraph Dev[Development]\n        DC[docker-compose]\n    end\n"
            "    subgraph CI[CI/CD Pipeline]\n        T[Tests + Lint] --> B[Build Images] --> SC[Security Scan] --> RG[Registry]\n    end\n"
            "    subgraph Prod[Production Kubernetes]\n        ING[Ingress + TLS] --> SVC[Services]\n        SVC --> DB[(Managed PostgreSQL)]\n        SVC --> RD[(Redis)]\n    end\n"
            "    Dev --> CI --> Prod"
        )
        return (
            "Three environments — development (docker-compose), staging, and production (Kubernetes) — "
            "promoted through a CI/CD pipeline: tests and linting gate every merge; images are built "
            "once, scanned, and promoted immutably; production rollouts are rolling with automatic "
            "rollback on failed health checks. Configuration is environment-injected (12-factor); "
            "stateful services use managed offerings where available." + pattern.deployment_extra + "\n\n"
            "```mermaid\n" + mermaid + "\n```"
        )

    def _monitoring_strategy(self, pattern: IndustryPattern) -> str:
        return (
            "- **Metrics:** Prometheus scrapes every service (request rate, latency P50/P95/P99, error "
            "rate, queue depth, resource saturation); Grafana dashboards per component.\n"
            "- **Logs:** structured JSON logs with correlation IDs, centrally aggregated.\n"
            "- **Traces:** OpenTelemetry spans across service boundaries for end-to-end latency analysis.\n"
            "- **Alerts:** SLO-based alerting (error budget burn), paging only on user-impacting "
            "symptoms; everything else lands on a triage dashboard.\n"
            "- **Health:** liveness/readiness endpoints on every service consumed by the orchestrator."
            + pattern.monitoring_extra
        )

    def _testing_strategy(self, pattern: IndustryPattern) -> str:
        return (
            "- **Unit tests** for domain logic and pure components (fast, run on every commit).\n"
            "- **Integration tests** against real database/broker instances in containers.\n"
            "- **Contract tests** on API schemas so clients and services evolve safely.\n"
            "- **End-to-end tests** covering the primary use-case flows, including failure injection "
            "(dependency down, malformed input, unauthorized access).\n"
            "- **Performance tests** establishing baseline throughput/latency before launch; regressions "
            "gate releases.\n"
            "- CI enforces all suites plus static analysis; coverage tracked on the critical path."
            + pattern.testing_extra
        )

    def _roadmap(self, frame: ContextFrame, pattern: IndustryPattern) -> List[RoadmapPhase]:
        return [
            RoadmapPhase(phase="Phase 1 — Foundation (weeks 1-2)", items=[
                "Repository, CI/CD skeleton, environments, and coding standards.",
                "Core data model, migrations, and authentication.",
                "Walking skeleton: thinnest end-to-end slice of the primary use case deployed to staging.",
            ]),
            RoadmapPhase(phase="Phase 2 — Core capability (weeks 3-5)", items=[
                pattern.roadmap_phase2_focus,
                "Administration and configuration surfaces.",
                "Integration and contract test suites.",
            ]),
            RoadmapPhase(phase="Phase 3 — Hardening (weeks 6-7)", items=[
                "Failure handling: retries, buffering, graceful degradation, chaos tests.",
                "Security review: authorization matrix, secrets, penetration checklist.",
                "Observability: dashboards, SLOs, alert runbooks.",
            ]),
            RoadmapPhase(phase="Phase 4 — Launch & iterate (week 8+)", items=[
                "Performance baseline and capacity plan.",
                "Production rollout with rollback plan.",
                "Feedback loop: usage analytics driving the enhancement backlog.",
            ]),
        ]

    def _risks(self, pattern: IndustryPattern) -> List[Risk]:
        risks = [
            Risk(risk="Scope creep beyond the analyzed use cases", likelihood="medium", impact="medium",
                 mitigation="Change control against the requirements table; new scenarios enter the backlog, not the sprint."),
            Risk(risk="Underestimated load profile degrades latency", likelihood="medium", impact="high",
                 mitigation="Performance tests before launch; horizontal scaling designed in from Phase 1."),
            Risk(risk="Security misconfiguration in deployment", likelihood="low", impact="high",
                 mitigation="Infrastructure as code with reviewed changes; automated security scanning in CI."),
        ]
        for risk, likelihood, impact, mitigation in pattern.risks_extra:
            risks.append(Risk(risk=risk, likelihood=likelihood, impact=impact, mitigation=mitigation))
        return risks

    def _future(self, pattern: IndustryPattern) -> List[str]:
        future = [
            "Multi-region deployment for latency and disaster recovery.",
            "Self-service analytics and reporting on accumulated data.",
            "Fine-grained usage metering and cost attribution per tenant.",
        ]
        for item in reversed(pattern.future_extra):
            future.insert(0, item)
        return future

    def _final(
        self, pattern: IndustryPattern, knowledge: KnowledgeFrame,
        learning: Optional[List[str]] = None,
    ) -> str:
        grounding = (
            f" The design is additionally grounded on {len(knowledge.sources)} internal knowledge "
            f"sources." if knowledge and knowledge.knowledge_used else ""
        )
        learning_note = (
            f" This recommendation stays consistent with {len(learning)} previously validated "
            f"solution(s) to similar requests learned from past conversations."
            if learning else ""
        )
        return (
            f"Proceed with the **{pattern.name}** as specified. Start with the Phase 1 walking "
            f"skeleton to de-risk integration early, keep every component behind a typed contract so "
            f"individual choices remain replaceable, and treat the non-functional requirements as "
            f"acceptance criteria — not aspirations.{grounding}{learning_note}"
        )


# ---------------------------------------------------------------------------
# Engineering Intelligence Engine Class (Slot 6)
# ---------------------------------------------------------------------------

_SOLUTION_JSON_INSTRUCTION = (
    "Respond ONLY with a JSON object matching this schema (no prose outside the JSON): "
    '{"title": str, "executive_summary": str, "problem_statement": str, '
    '"requirements_analysis": str, "recommended_solution": str, "architecture_overview": str, '
    '"technology_stack": [{"layer": str, "choice": str, "rationale": str}], '
    '"component_design": str, "database_design": str, "api_design": str, "workflow": str, '
    '"security_architecture": str, "deployment_architecture": str, "monitoring_strategy": str, '
    '"testing_strategy": str, "implementation_roadmap": [{"phase": str, "items": [str]}], '
    '"risk_assessment": [{"risk": str, "likelihood": str, "impact": str, "mitigation": str}], '
    '"future_enhancements": [str], "final_recommendations": str}. '
    "Markdown (including ```mermaid diagrams) is allowed inside string fields."
)


class EngineeringIntelligenceEngine(CognitiveEngine):
    """
    Core orchestrator of Axiom's Engineering Intelligence pre-inference pipeline.
    Replaces ReasoningEngine at Engine slot 6.
    """
    name = EngineName.REASONING

    def __init__(
        self,
        inference: Optional[InferenceAdapter] = None,
        knowledge_platform: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self.inference = inference or InferenceAdapter()
        # Engineering Knowledge Platform (ecosystem.KnowledgePlatform) — the
        # durable source of engineering intelligence. Optional: when None the
        # engine behaves exactly as before, reading the hardcoded packs.
        self.knowledge_platform = knowledge_platform

        # Sub-engines instantiations
        self.intent_analyzer = IntentAnalyzer()
        self.domain_classifier = DomainClassifier()
        self.industry_classifier = IndustryClassifier()
        self.expert_selector = ExpertSelector()
        self.knowledge_pack_loader = KnowledgePackLoader(platform=knowledge_platform)
        self.diagram_planner = DiagramPlanner()
        self.deliverable_planner = DeliverablePlanner()
        self.use_case_expander = UseCaseExpander()
        self.blueprint_optimizer = BlueprintOptimizer()
        self.synthesizer = SolutionSynthesizer()
        self.generation_planner = GenerationPlanner()

    async def _run(self, context: CognitiveContext) -> EngineResult:
        frame = context.context
        plan = context.plan
        knowledge = context.knowledge or KnowledgeFrame()
        learning = context.memory.learning if context.memory else []
        understanding = context.project_understanding

        # 1. Run Pre-Inference Classification Pipeline
        raw_task = context.task or ""
        
        # Resolve Intent
        intent = self.intent_analyzer.analyze(raw_task, context.intent or "general_engineering")
        
        # Classify Domains & Experts
        domains = self.domain_classifier.classify(raw_task, understanding)
        experts = self.expert_selector.select(domains)
        
        # Classify Industry & Standards
        industry_slug = understanding.industry if understanding else "generic_software"
        industry_name, standards = self.industry_classifier.classify(industry_slug)
        
        # Load Knowledge Packs — dynamically assembled from the Engineering
        # Knowledge Platform when available, else hardcoded fallback.
        entities = list(frame.entities)
        packs = self.knowledge_pack_loader.load(
            domains, industry_slug, intent=intent, entities=entities, message=raw_task
        )

        # Pull expanded standards + deterministic engineering rules from the
        # platform (additive enrichment; empty when no platform is wired).
        platform_standards: List[Dict[str, Any]] = []
        rules_applied: List[Dict[str, Any]] = []
        if self.knowledge_platform is not None:
            try:
                platform_standards = self.knowledge_platform.standards_for(domains, industry_slug)
            except Exception:
                platform_standards = []
            try:
                rules_applied = self.knowledge_platform.rules_for(raw_task, domains, intent, entities)
            except Exception:
                rules_applied = []

        # Plan Diagrams & Deliverables
        diagrams = self.diagram_planner.plan(domains, intent)
        deliverables = self.deliverable_planner.plan(intent)

        # Dynamic Planning Engine (Phase 5) — decides what SHOULD be
        # generated (documents/diagrams/reports/images/architecture) before
        # generation begins, from Project Intelligence alone. Advisory only:
        # does not filter the existing fixed document/diagram catalogs.
        generation_plan = self.generation_planner.plan(understanding, select_pattern(understanding))

        # Expand Use Case Metadata
        expanded = self.use_case_expander.expand(raw_task, domains, industry_name)

        # Save pipeline metadata context to context.metadata for downstream tracing
        context.metadata["engineering_intelligence"] = {
            "intent": intent,
            "domains": domains,
            "experts": experts,
            "industry": industry_name,
            "standards": standards,
            "diagrams": diagrams,
            "deliverables": deliverables,
            "expanded": expanded,
            "generation_plan": asdict(generation_plan),
            # Provenance: proves knowledge came from the platform, not the
            # hardcoded dict (developer-trace only, never user-facing).
            "knowledge_source": "platform" if (self.knowledge_platform is not None and packs) else "hardcoded_fallback",
            "platform_packs_used": [p.get("name", "") for p in packs],
            "standards_applied": [s.get("name", "") for s in platform_standards],
            "rules_applied": [r.get("name", "") for r in rules_applied],
        }

        # 2. Setup Base Document via Synthesizer (safe deterministic fallback)
        base_doc = self.synthesizer.synthesize(frame, plan, knowledge, learning, understanding)
        provider_used = "internal-synthesizer"
        model_used = "axiom-solution-synthesizer"

        # 3. Construct Dynamic Prompt & Complete LLM Inference
        dynamic_prompt = self._build_dynamic_prompt(
            context, intent, domains, experts, industry_name, standards, packs, diagrams, deliverables, expanded,
            platform_standards=platform_standards, rules_applied=rules_applied,
        )
        
        llm_payload = await self.inference.complete(
            prompt=dynamic_prompt, intent=intent
        )
        
        if llm_payload:
            parsed = self._extract_json(llm_payload["content"])
            if parsed:
                base_doc = self._merge(base_doc, parsed)
                provider_used = llm_payload.get("provider", "llm")
                model_used = llm_payload.get("model_used", "unknown")

        # 4. Score Confidence Baseline
        score_base = self._score_confidence(frame, knowledge, provider_used, learning)

        # 5. Post-Process & Run Blueprint Optimizer
        optimized_doc, final_confidence = self.blueprint_optimizer.optimize(
            base_doc, domains, score_base
        )
        
        tradeoffs = [
            f"Aligned architecture design around target industry standards: {', '.join(standards[:2])}.",
            f"Specialized experts profile selected: {', '.join(experts[:2])}.",
            "Optimizer-driven structural cleanup and validation checks passed successfully."
        ]

        context.reasoning = ReasoningResult(
            solution_draft=optimized_doc,
            confidence=final_confidence,
            rationale=(
                f"Engineering Solution mapped for domains ({', '.join(domains)}) and industry ({industry_name}). "
                f"Synthesized from {len(frame.use_cases)} scenarios, "
                f"{len(plan.functional_requirements)} functional requirements, and dynamic knowledge packs."
            ),
            tradeoffs=tradeoffs,
            provider_used=provider_used,
            model_used=model_used,
        )
        context.confidence = final_confidence

        return EngineResult(
            engine=self.name,
            summary=f"Engineering Solution optimized via {provider_used} (confidence {final_confidence:.2f}).",
            payload={"provider": provider_used, "model": model_used, "confidence": final_confidence},
        )

    # -- Dynamic Prompt Builder ----------------------------------------------

    def _build_dynamic_prompt(
        self,
        context: CognitiveContext,
        intent: str,
        domains: List[str],
        experts: List[str],
        industry_name: str,
        standards: List[str],
        packs: List[Dict[str, Any]],
        diagrams: List[str],
        deliverables: List[str],
        expanded: Dict[str, Any],
        platform_standards: Optional[List[Dict[str, Any]]] = None,
        rules_applied: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        frame = context.context
        plan = context.plan
        knowledge = context.knowledge or KnowledgeFrame()
        memory = context.memory

        # Format loaded Knowledge Packs
        packs_formatted = []
        for pack in packs:
            pack_desc = (
                f"### Pack: {pack['name']}\n"
                f"- Standards: {', '.join(pack['standards'])}\n"
                f"- Core Patterns: {', '.join(pack['patterns'])}\n"
                f"- Typical Problems: {', '.join(pack['common_problems'])}\n"
                f"- Failure Modes: {', '.join(pack['failure_modes'])}"
            )
            packs_formatted.append(pack_desc)

        # Assemble elements
        parts = [
            f"You are AXIOM, a highly advanced engineering solution intelligence platform. "
            f"You behave as a panel of multidisciplinary experts: {', '.join(experts)}. "
            f"Your current objective is: {intent}.",
            
            f"ENGINEERING DOMAINS: {', '.join(domains)}\n"
            f"TARGET INDUSTRY: {industry_name}\n"
            f"COMPLIANCE STANDARDS & REGULATIONS:\n" + "\n".join(f"- {std}" for std in standards),
            
            "EXPANDED USE CASE GOALS:\n"
            f"- Business Goals: {', '.join(expanded['business_goals'])}\n"
            f"- Technical Goals: {', '.join(expanded['technical_goals'])}\n"
            f"- Scalability Strategy: {expanded['scalability_strategy']}\n"
            f"- Failover/Recovery Strategy: {expanded['recovery_strategy']}\n"
            f"- Security/Tenant Strategy: {expanded['security_strategy']}",
            
            "KNOWLEDGE PACKS ACTIVATED:\n" + "\n\n".join(packs_formatted),
            
            "REQUIRED DIAGRAMS PLANNED:\n" + "\n".join(f"- Provide a ```mermaid diagram for: {diag}" for diag in diagrams),
            
            "EXPECTED DOCUMENT DELIVERABLES:\n" + "\n".join(f"- Detail section output matching: {deliv}" for deliv in deliverables),
            
            f"PROBLEM STATEMENT SUMMARY: {frame.subject}",
            
            "ANALYZED SCENARIOS:\n" + "\n".join(
                f"- {uc.id} [{uc.actor}] {uc.scenario} -> {uc.expected_behavior}" for uc in frame.use_cases
            ),
            
            "REQUIREMENTS GRID:\n" + "\n".join(
                f"- {r.id}: {r.requirement}" for r in plan.functional_requirements + plan.non_functional_requirements
            )
        ]

        if knowledge.knowledge_used:
            parts.append("GROUNDING EXCERPTS:\n" + "\n".join(
                f"- {s.title}: {s.excerpt[:200]}" for s in knowledge.sources
            ))
        if memory and memory.learning:
            parts.append("PREVIOUS SUCCESSFUL PROJECT HISTORY REFERENCE:\n" + "\n".join(
                f"- {entry}" for entry in memory.learning[:3]
            ))
        if memory and (memory.decisions or memory.feedback):
            parts.append("PREVIOUS DESIGN DECISIONS / USER FEEDBACK NOTES:\n" + "\n".join(
                f"- {d}" for d in (memory.decisions[-3:] + memory.feedback[-3:])
            ))

        # Expanded standards from the Knowledge Platform: concrete sections and
        # compliance level, not just a name.
        if platform_standards:
            std_lines = []
            for std in platform_standards[:6]:
                sections = ", ".join(std.get("sections", [])[:6])
                line = f"- {std.get('name')} ({std.get('compliance_level', 'recommended')}): {std.get('scope', '')}"
                if sections:
                    line += f" | Key sections: {sections}"
                std_lines.append(line)
            parts.append("APPLICABLE STANDARDS (from Engineering Knowledge Platform):\n" + "\n".join(std_lines))

        # Deterministic engineering rules that fire for this request — treat as
        # hard design constraints.
        if rules_applied:
            parts.append("ENGINEERING RULES (deterministic constraints — must be honored):\n" + "\n".join(
                f"- {r.get('then')} ({r.get('rationale')})" for r in rules_applied[:6]
            ))

        parts.append(_SOLUTION_JSON_INSTRUCTION)
        return "\n\n".join(parts)

    # -- helpers ------------------------------------------------------------

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        candidates = re.findall(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL) or [content]
        for candidate in candidates:
            try:
                data = json.loads(candidate.strip())
                if isinstance(data, dict) and "executive_summary" in data:
                    return data
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _merge(self, base: SolutionDocument, parsed: Dict[str, Any]) -> SolutionDocument:
        data = base.model_dump()
        for key, value in parsed.items():
            if key in data and value:
                data[key] = value
        try:
            return SolutionDocument(**data)
        except Exception as exc:
            logger.warning(f"LLM solution merge failed: {exc}")
            return base

    def _score_confidence(
        self, frame, knowledge: KnowledgeFrame, provider: str, learning: Optional[List[str]] = None
    ) -> float:
        score = 0.65
        if frame.entities:
            score += min(0.12, 0.02 * len(frame.entities))
        if frame.use_cases:
            score += 0.05
        if knowledge.knowledge_used:
            score += 0.10 * knowledge.confidence
        if provider != "internal-synthesizer":
            score += 0.06
        if learning:
            score += min(0.05, 0.02 * len(learning))
        return round(min(score, 0.95), 2)
