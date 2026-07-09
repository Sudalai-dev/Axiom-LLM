"""
Reasoning Engine (Engine 6) — the heart of Axiom.

This is the ONLY place in the platform where LLM inference happens.
Provider adaptation is isolated to the InferenceAdapter so the underlying
model is fully swappable (Master Prompt invariant B.2.6).

Two reasoning paths produce the SolutionDocument draft:
  1. LLM path — the adapter asks the configured provider for the solution as
     strict JSON matching the SolutionDocument schema.
  2. SolutionSynthesizer — a deterministic engineering-reasoning fallback that
     composes a complete solution from the cognitive frames (use cases, plan,
     knowledge, memory). It guarantees contract-valid output offline and is
     also used to fill any fields the LLM left empty.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from core.config import settings
from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    ContextFrame,
    EngineName,
    EngineResult,
    Intent,
    KnowledgeFrame,
    Plan,
    ReasoningResult,
    Risk,
    RoadmapPhase,
    SolutionDocument,
    TechChoice,
)

logger = logging.getLogger("AxiomOCIF.Reasoning")


# ---------------------------------------------------------------------------
# Inference adapter — the swappable LLM boundary
# ---------------------------------------------------------------------------

class InferenceAdapter:
    """
    Neutral inference interface. Wraps the platform ModelRouter; no engine
    logic outside this class may depend on a provider's API idiosyncrasies.
    """

    def __init__(self) -> None:
        self._router = None

    def _get_router(self):
        if self._router is None:
            from inference.model_router import ModelRouter
            self._router = ModelRouter()
        return self._router

    async def complete(self, prompt: str, intent: str) -> Optional[Dict[str, Any]]:
        """
        Returns {"content": str, "model_used": str} or None when no usable
        (non-simulated) provider responds.
        """
        from core.models.base import LLMProvider
        try:
            provider_enum = LLMProvider(settings.llm.default_provider.lower())
        except ValueError:
            provider_enum = LLMProvider.AUTO

        try:
            name, impl = self._get_router().get_provider(provider_enum, intent)
            payload = await impl.generate(
                prompt=prompt,
                max_tokens=settings.llm.default_max_tokens,
                temperature=settings.llm.default_temperature,
            )
            model_used = str(payload.get("model_used", ""))
            if model_used.endswith("-simulated"):
                # Offline mock cannot author real solutions — synthesize instead.
                return None
            return {"content": payload.get("content", ""), "model_used": model_used,
                    "provider": name.value}
        except Exception as exc:
            logger.warning(f"LLM inference unavailable, using synthesizer: {exc}")
            return None


# ---------------------------------------------------------------------------
# Architecture pattern catalog for deterministic synthesis
# ---------------------------------------------------------------------------

_AIOT_PATTERN = {
    "name": "Edge-to-Cloud Event-Driven AIoT Architecture",
    "components": [
        ("Edge Gateway", "Buffers and normalizes device telemetry; store-and-forward under intermittent connectivity."),
        ("MQTT Broker", "Central pub/sub backbone for device telemetry and command topics (QoS 1, retained state)."),
        ("Stream Processor", "Consumes telemetry, applies rules/ML models, detects anomalies, and emits domain events."),
        ("Time-Series Store", "Persists raw and aggregated telemetry for querying and dashboards."),
        ("Application API", "REST/WebSocket service exposing state, history, alerts, and configuration."),
        ("Alerting Service", "Deduplicates, escalates, and routes notifications to on-call channels."),
        ("Web Dashboard", "Role-scoped real-time visualization and administration UI."),
    ],
    "stack": [
        ("Device Connectivity", "MQTT (Eclipse Mosquitto / EMQX)", "Industry-standard lightweight pub/sub for constrained devices; QoS levels fit unreliable links."),
        ("Edge Runtime", "Python edge agent in Docker", "Uniform packaging on gateways; easy protocol adapters (Modbus/OPC-UA)."),
        ("Stream Processing", "Python asyncio workers (Kafka consumers where scale demands)", "Simple to operate; upgrade path to Kafka Streams/Flink."),
        ("Time-Series Storage", "TimescaleDB (PostgreSQL extension)", "SQL ergonomics + hypertable compression; one operational database engine."),
        ("Application API", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Frontend", "React + TypeScript", "Component ecosystem for real-time dashboards; type safety."),
        ("Orchestration", "Docker Compose → Kubernetes", "Compose for development, K8s for production scale and rollout control."),
    ],
}

_EVENT_PATTERN = {
    "name": "Event-Driven Microservices Architecture",
    "components": [
        ("API Gateway", "Single entry point: authentication, rate limiting, routing."),
        ("Domain Services", "Independently deployable services owning their data and publishing domain events."),
        ("Event Backbone", "Durable pub/sub log decoupling producers from consumers."),
        ("Read-Model / Query Service", "Materialized views optimized for the UI and reporting."),
        ("Worker Pool", "Asynchronous background processing of long-running jobs."),
    ],
    "stack": [
        ("Event Backbone", "Apache Kafka", "Durable, replayable log; consumer groups for horizontal scale."),
        ("Services", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Cache / Coordination", "Redis", "Low-latency caching, distributed locks, rate limiting."),
        ("Primary Storage", "PostgreSQL", "ACID guarantees, JSONB flexibility, mature operations."),
        ("Frontend", "React + TypeScript", "Type-safe component-driven UI."),
        ("Orchestration", "Kubernetes", "Declarative deployment, autoscaling, self-healing."),
    ],
}

_WEB_PATTERN = {
    "name": "Layered Service Architecture (API-first)",
    "components": [
        ("API Gateway / Reverse Proxy", "TLS termination, routing, rate limiting."),
        ("Application Service", "Business logic behind typed REST endpoints."),
        ("Data Layer", "Repository pattern over the relational store with migrations."),
        ("Background Workers", "Async jobs: notifications, exports, scheduled tasks."),
        ("Web Client", "Responsive SPA consuming the API."),
    ],
    "stack": [
        ("Backend", "FastAPI (Python)", "Async-first, typed contracts, OpenAPI out of the box."),
        ("Database", "PostgreSQL", "ACID guarantees, JSONB flexibility, mature operations."),
        ("Cache", "Redis", "Session store and hot-path caching."),
        ("Frontend", "React + TypeScript", "Type-safe component-driven UI."),
        ("Packaging", "Docker + docker-compose", "Reproducible environments from dev to prod."),
    ],
}

_AI_PATTERN = {
    "name": "AI Inference & Retrieval Pipeline Architecture",
    "components": [
        ("Ingestion Pipeline", "Parses, chunks, and embeds source documents into the vector store."),
        ("Vector Store", "Similarity search over embedded knowledge."),
        ("Inference Orchestrator", "Builds grounded prompts, routes to the model provider, validates outputs."),
        ("Model Gateway", "Provider-agnostic LLM access with fallback and cost tracking."),
        ("Application API", "Exposes query, feedback, and administration endpoints."),
        ("Evaluation Harness", "Regression suites scoring answer quality and grounding."),
    ],
    "stack": [
        ("Orchestration", "Python (FastAPI + asyncio)", "First-class AI ecosystem; async pipelines."),
        ("Vector Store", "pgvector / Qdrant", "Start embedded in PostgreSQL; dedicated engine at scale."),
        ("Model Access", "Provider-agnostic gateway (Claude/GPT/Gemini/Llama)", "No hard provider lock-in; per-task routing."),
        ("Cache / Queue", "Redis", "Embedding cache and job queue."),
        ("Frontend", "React + TypeScript", "Interactive chat/analysis UI."),
        ("Orchestration Runtime", "Docker → Kubernetes", "Standard container lifecycle."),
    ],
}


def _select_pattern(intent: str, entities: List[str]) -> Dict[str, Any]:
    entity_set = set(entities)
    if intent == Intent.AIOT_ENGINEERING.value or entity_set & {"MQTT", "OPC-UA", "Modbus", "IoT", "AIoT", "Sensors", "Edge Computing", "SCADA", "Telemetry"}:
        return _AIOT_PATTERN
    if entity_set & {"LLM", "RAG", "Embeddings", "Machine Learning", "Vector Database", "Anomaly Detection"}:
        return _AI_PATTERN
    if entity_set & {"Kafka", "RabbitMQ", "Microservices"}:
        return _EVENT_PATTERN
    return _WEB_PATTERN


# ---------------------------------------------------------------------------
# Deterministic solution synthesizer
# ---------------------------------------------------------------------------

class SolutionSynthesizer:
    """Composes a complete SolutionDocument from the cognitive frames."""

    def synthesize(
        self,
        frame: ContextFrame,
        plan: Plan,
        knowledge: KnowledgeFrame,
        learning: Optional[List[str]] = None,
    ) -> SolutionDocument:
        pattern = _select_pattern(frame.intent.value if hasattr(frame.intent, "value") else frame.intent, frame.entities)
        title = self._title(frame)
        components = pattern["components"]

        doc = SolutionDocument(
            title=title,
            executive_summary=self._executive_summary(frame, pattern),
            problem_statement=self._problem_statement(frame),
            actors=list(frame.actors),
            requirements_analysis=self._requirements_analysis(frame, plan),
            recommended_solution=self._recommended_solution(frame, pattern),
            architecture_overview=self._architecture_overview(pattern),
            technology_stack=[TechChoice(layer=l, choice=c, rationale=r) for l, c, r in pattern["stack"]],
            component_design=self._component_design(components),
            database_design=self._database_design(frame),
            api_design=self._api_design(frame),
            workflow=self._workflow(frame, components),
            security_architecture=self._security_architecture(frame),
            deployment_architecture=self._deployment_architecture(),
            monitoring_strategy=self._monitoring_strategy(),
            testing_strategy=self._testing_strategy(),
            implementation_roadmap=self._roadmap(frame, plan),
            risk_assessment=self._risks(frame),
            future_enhancements=self._future(frame),
            final_recommendations=self._final(frame, pattern, knowledge, learning),
        )
        return doc

    # -- sections -----------------------------------------------------------

    def _title(self, frame: ContextFrame) -> str:
        subject = frame.subject.rstrip(".?! ")
        return subject[:1].upper() + subject[1:] if subject else "Engineering Solution"

    def _executive_summary(self, frame: ContextFrame, pattern: Dict[str, Any]) -> str:
        entities = ", ".join(frame.entities[:6]) if frame.entities else "the requested capability"
        return (
            f"This document presents a production-ready engineering solution for the stated need: "
            f"**{frame.subject}**. The recommended approach is a **{pattern['name']}** built around "
            f"{entities}. The design covers the full realistic scope — primary user flows, "
            f"administration, failure handling, security, and operations — and concludes with a "
            f"phased implementation roadmap a team can execute immediately."
        )

    def _problem_statement(self, frame: ContextFrame) -> str:
        actors = ", ".join(frame.actors[:4])
        return (
            f"{frame.subject}\n\n"
            f"Stakeholders affected: {actors}. Beyond the literal request, a production system must "
            f"also handle configuration and onboarding, partial failures of dependencies, "
            f"unauthorized access attempts, and rapid diagnosis of incidents. This solution treats "
            f"those as first-class requirements rather than afterthoughts."
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

    def _recommended_solution(self, frame: ContextFrame, pattern: Dict[str, Any]) -> str:
        alternatives = {
            _AIOT_PATTERN["name"]: "a monolithic SCADA extension (poor scalability, vendor lock-in) and direct device-to-cloud HTTP polling (battery/bandwidth cost, no offline buffering)",
            _EVENT_PATTERN["name"]: "a modular monolith (simpler initially but couples deploy cadence) and synchronous REST chaining between services (cascading failures under load)",
            _WEB_PATTERN["name"]: "a microservices split (operational overhead unjustified at this scale) and a server-rendered monolith (limits interactive UX)",
            _AI_PATTERN["name"]: "fine-tuning a dedicated model (cost and staleness) and prompt-only integration without retrieval (hallucination risk on domain facts)",
        }
        alt = alternatives.get(pattern["name"], "simpler architectures that fail the stated non-functional requirements")
        return (
            f"Adopt a **{pattern['name']}**. Alternatives considered and rejected: {alt}. "
            f"The chosen pattern best balances delivery speed, operational simplicity, and the "
            f"reliability/scalability requirements derived from the scenario analysis. Each component "
            f"below is independently testable and replaceable, and the design avoids hard vendor "
            f"lock-in at every layer."
        )

    def _architecture_overview(self, pattern: Dict[str, Any]) -> str:
        nodes = pattern["components"]
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

    def _database_design(self, frame: ContextFrame) -> str:
        iot = bool(set(frame.entities) & {"MQTT", "IoT", "AIoT", "Sensors", "Telemetry", "Modbus", "OPC-UA"})
        if iot:
            er = (
                "erDiagram\n"
                "    DEVICE ||--o{ TELEMETRY : emits\n"
                "    DEVICE ||--o{ ALERT : triggers\n"
                "    DEVICE }o--|| SITE : located_at\n"
                "    ALERT ||--o{ NOTIFICATION : dispatches\n"
                "    USER ||--o{ NOTIFICATION : receives\n"
                "    DEVICE {\n        uuid device_id PK\n        string name\n        string protocol\n        string status\n    }\n"
                "    TELEMETRY {\n        uuid device_id FK\n        timestamptz ts\n        string metric\n        double value\n    }\n"
                "    ALERT {\n        uuid alert_id PK\n        uuid device_id FK\n        string severity\n        string state\n        timestamptz raised_at\n    }"
            )
            notes = (
                "Telemetry is stored in a TimescaleDB hypertable partitioned by time, with continuous "
                "aggregates for dashboard rollups and a retention policy for raw data. Relational "
                "entities (devices, sites, users, alerts) live in standard PostgreSQL tables with "
                "row-level tenant isolation."
            )
        else:
            er = (
                "erDiagram\n"
                "    TENANT ||--o{ USER : has\n"
                "    USER ||--o{ SESSION : opens\n"
                "    TENANT ||--o{ RESOURCE : owns\n"
                "    RESOURCE ||--o{ EVENT : generates\n"
                "    USER ||--o{ AUDIT_LOG : recorded_in\n"
                "    RESOURCE {\n        uuid resource_id PK\n        uuid tenant_id FK\n        string name\n        string status\n        timestamptz created_at\n    }\n"
                "    EVENT {\n        uuid event_id PK\n        uuid resource_id FK\n        string type\n        jsonb payload\n        timestamptz ts\n    }"
            )
            notes = (
                "PostgreSQL is the system of record. All tenant-scoped tables carry a tenant_id with "
                "row-level security; JSONB columns absorb schema-flexible payloads; schema changes are "
                "managed through versioned migrations (Alembic)."
            )
        return f"{notes}\n\n```mermaid\n{er}\n```"

    def _api_design(self, frame: ContextFrame) -> str:
        iot = bool(set(frame.entities) & {"MQTT", "IoT", "AIoT", "Sensors", "Telemetry"})
        rows = [
            "| Method | Endpoint | Purpose |",
            "|--------|----------|---------|",
            "| POST | /api/v1/auth/login | Authenticate and issue JWT |",
        ]
        if iot:
            rows += [
                "| GET | /api/v1/devices | List registered devices with status |",
                "| POST | /api/v1/devices | Register/onboard a device |",
                "| GET | /api/v1/devices/{id}/telemetry?from&to | Query historical telemetry |",
                "| GET | /api/v1/alerts?state=open | List active alerts |",
                "| POST | /api/v1/alerts/{id}/ack | Acknowledge an alert |",
                "| WS | /api/v1/stream | Real-time telemetry/alert push |",
            ]
        else:
            rows += [
                "| GET | /api/v1/resources | List resources (paginated, filtered) |",
                "| POST | /api/v1/resources | Create a resource |",
                "| GET | /api/v1/resources/{id} | Fetch a resource |",
                "| PATCH | /api/v1/resources/{id} | Update a resource |",
                "| DELETE | /api/v1/resources/{id} | Remove a resource |",
                "| GET | /api/v1/events?since= | Event history for auditing/sync |",
            ]
        return (
            "REST + JSON with OpenAPI documentation generated from typed contracts. All endpoints "
            "are versioned, authenticated (Bearer JWT), tenant-scoped, and rate-limited. Errors follow "
            "RFC 7807 problem+json.\n\n" + "\n".join(rows)
        )

    def _workflow(self, frame: ContextFrame, components) -> str:
        iot = bool(set(frame.entities) & {"MQTT", "IoT", "AIoT", "Sensors", "Telemetry"})
        if iot:
            seq = (
                "sequenceDiagram\n"
                "    participant D as Device\n"
                "    participant G as Edge Gateway\n"
                "    participant B as MQTT Broker\n"
                "    participant P as Stream Processor\n"
                "    participant S as Time-Series Store\n"
                "    participant A as Alerting Service\n"
                "    participant U as Dashboard\n"
                "    D->>G: telemetry sample\n"
                "    G->>B: publish topic site/{id}/telemetry (QoS 1)\n"
                "    B->>P: consume telemetry\n"
                "    P->>S: persist + aggregate\n"
                "    alt threshold breached\n"
                "        P->>A: raise alert event\n"
                "        A->>U: push notification (WS)\n"
                "    end\n"
                "    U->>S: query history via API"
            )
            narrative = (
                "The primary flow is telemetry ingestion → evaluation → persistence → notification. "
                "Edge buffering covers connectivity gaps; alert deduplication prevents notification storms."
            )
        else:
            first = re.sub(r"[^A-Za-z0-9]", "", components[0][0])[:12] or "Gateway"
            seq = (
                "sequenceDiagram\n"
                "    participant U as User\n"
                f"    participant G as {components[0][0]}\n"
                "    participant S as Application Service\n"
                "    participant D as Database\n"
                "    participant W as Worker\n"
                "    U->>G: authenticated request\n"
                "    G->>S: route + authorize\n"
                "    S->>D: transactional read/write\n"
                "    S-->>W: enqueue async side-effects\n"
                "    S->>U: typed response\n"
                "    W->>U: eventual notification"
            )
            narrative = (
                "Requests flow through the gateway for authentication and rate limiting, execute "
                "transactionally in the application service, and defer slow side-effects to workers."
            )
        return f"{narrative}\n\n```mermaid\n{seq}\n```"

    def _security_architecture(self, frame: ContextFrame) -> str:
        iot_extra = ""
        if set(frame.entities) & {"MQTT", "IoT", "AIoT", "Sensors", "Modbus", "OPC-UA"}:
            iot_extra = (
                "\n- **Device identity:** per-device X.509 certificates or credential rotation; "
                "mutual TLS on MQTT; topic-level ACLs so devices publish/subscribe only to their own topics."
                "\n- **OT/IT segregation:** industrial protocols (Modbus/OPC-UA) terminate at the edge "
                "gateway; nothing on the OT network is directly internet-reachable."
            )
        return (
            "- **Authentication:** OAuth2/JWT with short-lived access tokens and refresh rotation.\n"
            "- **Authorization:** role-based access control enforced at the API layer and row-level "
            "tenant isolation in the database.\n"
            "- **Transport:** TLS 1.2+ everywhere; internal service traffic on a private network.\n"
            "- **Secrets:** injected from a secrets manager; never committed or baked into images.\n"
            "- **Input handling:** schema validation at every boundary; parameterized queries; "
            "rate limiting and audit logging on all mutating endpoints." + iot_extra
        )

    def _deployment_architecture(self) -> str:
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
            "stateful services use managed offerings where available.\n\n"
            "```mermaid\n" + mermaid + "\n```"
        )

    def _monitoring_strategy(self) -> str:
        return (
            "- **Metrics:** Prometheus scrapes every service (request rate, latency P50/P95/P99, error "
            "rate, queue depth, resource saturation); Grafana dashboards per component.\n"
            "- **Logs:** structured JSON logs with correlation IDs, centrally aggregated.\n"
            "- **Traces:** OpenTelemetry spans across service boundaries for end-to-end latency analysis.\n"
            "- **Alerts:** SLO-based alerting (error budget burn), paging only on user-impacting "
            "symptoms; everything else lands on a triage dashboard.\n"
            "- **Health:** liveness/readiness endpoints on every service consumed by the orchestrator."
        )

    def _testing_strategy(self) -> str:
        return (
            "- **Unit tests** for domain logic and pure components (fast, run on every commit).\n"
            "- **Integration tests** against real database/broker instances in containers.\n"
            "- **Contract tests** on API schemas so clients and services evolve safely.\n"
            "- **End-to-end tests** covering the primary use-case flows, including failure injection "
            "(dependency down, malformed input, unauthorized access).\n"
            "- **Performance tests** establishing baseline throughput/latency before launch; regressions "
            "gate releases.\n"
            "- CI enforces all suites plus static analysis; coverage tracked on the critical path."
        )

    def _roadmap(self, frame: ContextFrame, plan: Plan) -> List[RoadmapPhase]:
        return [
            RoadmapPhase(phase="Phase 1 — Foundation (weeks 1-2)", items=[
                "Repository, CI/CD skeleton, environments, and coding standards.",
                "Core data model, migrations, and authentication.",
                "Walking skeleton: thinnest end-to-end slice of the primary use case deployed to staging.",
            ]),
            RoadmapPhase(phase="Phase 2 — Core capability (weeks 3-5)", items=[
                f"Implement the primary flows: {frame.use_cases[0].scenario if frame.use_cases else 'core feature set'}",
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

    def _risks(self, frame: ContextFrame) -> List[Risk]:
        risks = [
            Risk(risk="Scope creep beyond the analyzed use cases", likelihood="medium", impact="medium",
                 mitigation="Change control against the requirements table; new scenarios enter the backlog, not the sprint."),
            Risk(risk="Underestimated load profile degrades latency", likelihood="medium", impact="high",
                 mitigation="Performance tests before launch; horizontal scaling designed in from Phase 1."),
            Risk(risk="Security misconfiguration in deployment", likelihood="low", impact="high",
                 mitigation="Infrastructure as code with reviewed changes; automated security scanning in CI."),
        ]
        if set(frame.entities) & {"MQTT", "IoT", "AIoT", "Sensors", "Modbus", "OPC-UA"}:
            risks.append(Risk(
                risk="Unreliable device connectivity causes data loss", likelihood="high", impact="medium",
                mitigation="Edge store-and-forward buffering, QoS 1 delivery, idempotent ingestion with deduplication.",
            ))
        return risks

    def _future(self, frame: ContextFrame) -> List[str]:
        future = [
            "Multi-region deployment for latency and disaster recovery.",
            "Self-service analytics and reporting on accumulated data.",
            "Fine-grained usage metering and cost attribution per tenant.",
        ]
        if set(frame.entities) & {"MQTT", "IoT", "AIoT", "Sensors", "Machine Learning", "Anomaly Detection"}:
            future.insert(0, "Predictive maintenance models trained on accumulated telemetry.")
        return future

    def _final(
        self, frame: ContextFrame, pattern: Dict[str, Any], knowledge: KnowledgeFrame,
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
            f"Proceed with the **{pattern['name']}** as specified. Start with the Phase 1 walking "
            f"skeleton to de-risk integration early, keep every component behind a typed contract so "
            f"individual choices remain replaceable, and treat the non-functional requirements as "
            f"acceptance criteria — not aspirations.{grounding}{learning_note}"
        )


# ---------------------------------------------------------------------------
# Reasoning Engine
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


class ReasoningEngine(CognitiveEngine):
    name = EngineName.REASONING

    def __init__(self, inference: Optional[InferenceAdapter] = None) -> None:
        super().__init__()
        self.inference = inference or InferenceAdapter()
        self.synthesizer = SolutionSynthesizer()

    async def _run(self, context: CognitiveContext) -> EngineResult:
        frame = context.context
        plan = context.plan
        knowledge = context.knowledge or KnowledgeFrame()
        learning = context.memory.learning if context.memory else []

        # Deterministic engineering baseline — always available.
        base_doc = self.synthesizer.synthesize(frame, plan, knowledge, learning)
        provider_used = "internal-synthesizer"
        model_used = "axiom-solution-synthesizer"

        # LLM path (the only inference call site in the platform).
        llm_payload = await self.inference.complete(
            prompt=self._build_prompt(context), intent=context.intent
        )
        if llm_payload:
            parsed = self._extract_json(llm_payload["content"])
            if parsed:
                base_doc = self._merge(base_doc, parsed)
                provider_used = llm_payload.get("provider", "llm")
                model_used = llm_payload.get("model_used", "unknown")

        confidence = self._score_confidence(frame, knowledge, provider_used, learning)
        tradeoffs = [
            f"Chosen architecture pattern over simpler alternatives to satisfy the derived NFRs.",
            "Provider-agnostic layers preferred over managed lock-in for portability.",
            "Phased roadmap trades initial feature breadth for an early de-risked walking skeleton.",
        ]

        context.reasoning = ReasoningResult(
            solution_draft=base_doc,
            confidence=confidence,
            rationale=(
                f"Solution derived from {len(frame.use_cases)} analyzed use cases, "
                f"{len(plan.functional_requirements)} functional and "
                f"{len(plan.non_functional_requirements)} non-functional requirements"
                + (f", grounded on {len(knowledge.sources)} knowledge sources" if knowledge.knowledge_used else "")
                + "."
            ),
            tradeoffs=tradeoffs,
            provider_used=provider_used,
            model_used=model_used,
        )
        context.confidence = confidence

        return EngineResult(
            engine=self.name,
            summary=f"Solution draft composed via {provider_used} (confidence {confidence:.2f}).",
            payload={"provider": provider_used, "model": model_used, "confidence": confidence},
        )

    # -- helpers ------------------------------------------------------------

    def _build_prompt(self, context: CognitiveContext) -> str:
        frame = context.context
        plan = context.plan
        knowledge = context.knowledge or KnowledgeFrame()
        memory = context.memory

        parts = [
            "You are AXIOM, an AI Engineering Solution Architecture Platform. You transform "
            "engineering problems into complete, production-ready solution blueprints. "
            "You are precise, pragmatic, and vendor-neutral.",
            f"REQUEST: {frame.subject}",
            f"INTENT: {context.intent} | ENTITIES: {', '.join(frame.entities) or 'none'}",
            "ANALYZED USE CASES:\n" + "\n".join(
                f"- {uc.id} [{uc.actor}] {uc.scenario} -> {uc.expected_behavior}" for uc in frame.use_cases
            ),
            "REQUIREMENTS:\n" + "\n".join(
                f"- {r.id}: {r.requirement}" for r in plan.functional_requirements + plan.non_functional_requirements
            ),
        ]
        if knowledge.knowledge_used:
            parts.append("KNOWLEDGE SOURCES:\n" + "\n".join(
                f"- {s.title}: {s.excerpt[:200]}" for s in knowledge.sources
            ))
        if memory and memory.learning:
            parts.append("LEARNED FROM PAST SUCCESSFUL SOLUTIONS:\n" + "\n".join(
                f"- {entry}" for entry in memory.learning[:3]
            ))
        if memory and (memory.decisions or memory.feedback):
            parts.append("PRIOR DECISIONS/FEEDBACK:\n" + "\n".join(
                f"- {d}" for d in (memory.decisions[-3:] + memory.feedback[-3:])
            ))
        parts.append(_SOLUTION_JSON_INSTRUCTION)
        return "\n\n".join(parts)

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
        """LLM fields win when present and non-empty; synthesizer fills gaps."""
        data = base.model_dump()
        for key, value in parsed.items():
            if key in data and value:
                data[key] = value
        try:
            return SolutionDocument(**data)
        except Exception as exc:
            logger.warning(f"LLM solution merge failed, keeping synthesized draft: {exc}")
            return base

    def _score_confidence(
        self, frame, knowledge: KnowledgeFrame, provider: str, learning: Optional[List[str]] = None
    ) -> float:
        score = 0.62
        if frame.entities:
            score += min(0.12, 0.02 * len(frame.entities))
        if frame.use_cases:
            score += 0.06
        if knowledge.knowledge_used:
            score += 0.10 * knowledge.confidence
        if provider != "internal-synthesizer":
            score += 0.08
        if learning:
            score += min(0.06, 0.02 * len(learning))
        return round(min(score, 0.98), 2)
