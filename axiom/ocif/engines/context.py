"""
Context Engine (Engine 2) — intent understanding + use-case analysis.

Determines what is being asked (intent), extracts technology entities and
actors, and expands the request into the internal set of use cases that the
solution will be designed against.
"""

import re
from typing import List

from ocif.engine import CognitiveEngine
from ocif.frames import (
    CognitiveContext,
    ContextFrame,
    EngineName,
    EngineResult,
    Intent,
    UseCase,
)

# ---------------------------------------------------------------------------
# Technology entity lexicon (domains of expertise, Master Prompt Part A)
# ---------------------------------------------------------------------------

TECH_LEXICON = {
    # AIoT / industrial
    "mqtt": "MQTT", "opc-ua": "OPC-UA", "opcua": "OPC-UA", "modbus": "Modbus",
    "sensor": "Sensors", "edge": "Edge Computing", "plc": "PLC", "scada": "SCADA",
    "iot": "IoT", "aiot": "AIoT", "telemetry": "Telemetry",
    # Messaging / data
    "kafka": "Kafka", "redis": "Redis", "rabbitmq": "RabbitMQ", "websocket": "WebSockets",
    "timescale": "TimescaleDB", "influxdb": "InfluxDB",
    # Databases
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "mysql": "MySQL",
    "mongodb": "MongoDB", "sqlite": "SQLite", "database": "Database",
    "sql": "SQL", "vector db": "Vector Database", "elasticsearch": "Elasticsearch",
    # Backend / frontend
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "python": "Python",
    "react": "React", "typescript": "TypeScript", "node": "Node.js", "grpc": "gRPC",
    "rest": "REST API", "graphql": "GraphQL", "api": "API",
    # Infra / cloud
    "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "aws": "AWS", "azure": "Azure", "gcp": "GCP", "terraform": "Terraform",
    "ci/cd": "CI/CD", "microservice": "Microservices", "serverless": "Serverless",
    "nginx": "NGINX", "load balancer": "Load Balancing",
    # AI / ML
    "llm": "LLM", "rag": "RAG", "embedding": "Embeddings", "machine learning": "Machine Learning",
    "ml": "Machine Learning", "anomaly": "Anomaly Detection", "computer vision": "Computer Vision",
    # Security
    "oauth": "OAuth2", "jwt": "JWT", "tls": "TLS", "rbac": "RBAC", "sso": "SSO",
    # Monitoring
    "prometheus": "Prometheus", "grafana": "Grafana", "opentelemetry": "OpenTelemetry",
}

_INTENT_RULES = [
    (Intent.AIOT_ENGINEERING, r"\b(mqtt|opc-?ua|modbus|iot|aiot|sensor|plc|scada|edge computing|telemetry)\b"),
    (Intent.CODE_GENERATION, r"\b(write|generate|implement|refactor|fix)\b.*\b(code|function|class|script|endpoint|module|test)\b|```"),
    (Intent.DOCUMENTATION, r"\b(brd|prd|srs|hld|lld|documentation|user manual|api docs?|design document|technical report)\b"),
    (Intent.REVIEW, r"\b(review|audit|evaluate|assess|critique)\b"),
    (Intent.SOLUTION_DESIGN, r"\b(design|architect|build|create|develop|propose|plan|blueprint|platform|system|solution|architecture|pipeline|service)\b"),
]

_TRIVIAL_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|thanks?( you)?|ok(ay)?|good (morning|evening|afternoon)|"
    r"who are you\??|what can you do\??|help\??|yes|no|bye)\s*[!.?]*\s*$",
    re.IGNORECASE,
)

# Actor inference keyed on domain signals
_ACTOR_RULES = [
    (r"\b(operator|plant|factory|industrial|machine|shop floor)\b", "Plant Operator"),
    (r"\b(sensor|device|gateway|edge|telemetry|iot|mqtt|modbus|opc)\b", "Field Device / Edge Gateway"),
    (r"\b(admin|administrator|tenant|configuration)\b", "System Administrator"),
    (r"\b(alert|notify|escalat|on-call|incident)\b", "On-call Engineer"),
    (r"\b(dashboard|report|analytics|kpi|visuali[sz])\b", "Business Analyst"),
    (r"\b(customer|client|user|subscriber)\b", "End User"),
    (r"\b(developer|api|integrat|sdk)\b", "Integration Developer"),
    (r"\b(compliance|audit|regulat|security)\b", "Compliance Officer"),
]


class ContextEngine(CognitiveEngine):
    name = EngineName.CONTEXT

    async def _run(self, context: CognitiveContext) -> EngineResult:
        text = context.perception.normalized_text if context.perception else (context.task or "")
        lowered = text.lower()

        is_trivial = bool(_TRIVIAL_PATTERNS.match(text)) or (
            len(text.split()) <= 3 and not any(k in lowered for k in TECH_LEXICON)
        )

        entities = self._extract_entities(lowered)
        intent = Intent.TRIVIAL_CLARIFICATION if is_trivial else self._classify_intent(lowered)
        actors = self._infer_actors(lowered)
        use_cases = [] if is_trivial else self._expand_use_cases(text, actors, entities, intent)

        subject = text if len(text) <= 200 else text[:197] + "..."

        context.context = ContextFrame(
            intent=intent,
            entities=entities,
            actors=actors,
            use_cases=use_cases,
            project=context.project,
            conversation_state={"conversation_id": context.conversation_id},
            is_trivial=is_trivial,
            subject=subject,
        )
        context.intent = intent.value
        context.entities = entities

        return EngineResult(
            engine=self.name,
            summary=(
                f"Intent '{intent.value}'; {len(entities)} entities; "
                f"{len(use_cases)} use cases expanded."
            ),
            payload={
                "intent": intent.value,
                "entities": entities,
                "use_case_count": len(use_cases),
                "is_trivial": is_trivial,
            },
        )

    # -- helpers ------------------------------------------------------------

    def _extract_entities(self, lowered: str) -> List[str]:
        found = []
        for key, canonical in TECH_LEXICON.items():
            if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", lowered) and canonical not in found:
                found.append(canonical)
        return found

    def _classify_intent(self, lowered: str) -> Intent:
        for intent, pattern in _INTENT_RULES:
            if re.search(pattern, lowered):
                return intent
        return Intent.GENERAL_ENGINEERING

    def _infer_actors(self, lowered: str) -> List[str]:
        actors = [actor for pattern, actor in _ACTOR_RULES if re.search(pattern, lowered)]
        if not actors:
            actors = ["End User", "System Administrator"]
        return actors

    def _expand_use_cases(
        self, text: str, actors: List[str], entities: List[str], intent: Intent
    ) -> List[UseCase]:
        """
        Expands the single request into the full internal set of scenarios
        the solution must be designed against (happy path, admin/config,
        failure handling, security, observability).
        """
        subject = text if len(text) <= 120 else text[:117] + "..."
        primary = actors[0]
        use_cases = [
            UseCase(
                id="UC-1",
                actor=primary,
                scenario=f"Primary flow: {subject}",
                expected_behavior="The system fulfils the core request end-to-end with correct, validated results.",
            ),
            UseCase(
                id="UC-2",
                actor="System Administrator",
                scenario="Configure, onboard, and manage the system (tenants, thresholds, integrations, access).",
                expected_behavior="Administrative changes are applied safely, audited, and take effect without downtime.",
            ),
            UseCase(
                id="UC-3",
                actor=primary,
                scenario="A dependent component or upstream source fails or degrades mid-operation.",
                expected_behavior="The system degrades gracefully, retries/buffers where safe, and surfaces actionable errors.",
            ),
            UseCase(
                id="UC-4",
                actor="Compliance Officer",
                scenario="Unauthorized or malformed access is attempted against the system.",
                expected_behavior="Requests are authenticated, authorized (least privilege), rejected cleanly, and audit-logged.",
            ),
            UseCase(
                id="UC-5",
                actor="On-call Engineer",
                scenario="The system misbehaves in production and must be diagnosed quickly.",
                expected_behavior="Metrics, logs, traces, and alerts pinpoint the failing component within minutes.",
            ),
        ]

        # Domain-specific expansions
        if intent == Intent.AIOT_ENGINEERING or any(
            e in entities for e in ("MQTT", "IoT", "AIoT", "Sensors", "Modbus", "OPC-UA")
        ):
            use_cases.append(
                UseCase(
                    id=f"UC-{len(use_cases) + 1}",
                    actor="Field Device / Edge Gateway",
                    scenario="Devices publish telemetry under intermittent connectivity and bursty load.",
                    expected_behavior="Messages are buffered at the edge, delivered at-least-once, deduplicated, and back-pressure is handled.",
                )
            )
        if len(actors) > 1:
            for idx, actor in enumerate(actors[1:3], start=len(use_cases) + 1):
                use_cases.append(
                    UseCase(
                        id=f"UC-{idx}",
                        actor=actor,
                        scenario=f"{actor} interacts with the delivered capability for their role-specific workflow.",
                        expected_behavior="Role-scoped views and permissions expose exactly the data and actions this actor needs.",
                    )
                )
        return use_cases
