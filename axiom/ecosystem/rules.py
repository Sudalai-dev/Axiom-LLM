"""
Engineering Rules Engine — deterministic, reusable engineering knowledge.

Rules encode organizational engineering judgement as data ("if a critical alarm
is involved, use MQTT QoS >= 1"), independent of the LLM. `evaluate()` returns
the rules that fire for a given request so the Engineering Intelligence Engine
can inject them as hard constraints into the prompt. Rules are also persisted
into the repository as ENGINEERING_RULE knowledge objects so they are
queryable, rankable, and analyzable like any other knowledge.
"""

from typing import Any, Dict, List, Optional

from ecosystem.models import KnowledgeCategory, KnowledgeObject, stable_id
from ecosystem.repository import EngineeringKnowledgeRepository


# Each rule matches when ANY of its `when` signals is present in the request.
# A signal is a lowercase substring checked against the message, the intent, the
# entities, and the domains list (all lowercased and joined).
SEED_RULES: List[Dict[str, Any]] = [
    {
        "name": "Critical alarms require guaranteed delivery",
        "domain": "Industrial IoT",
        "when": ["critical alarm", "safety", "shutdown", "emergency"],
        "then": "Use MQTT QoS 1 (at-least-once) or QoS 2 (exactly-once) for the alarm topic.",
        "rationale": "A dropped critical-alarm message can mask a hazardous condition.",
        "standards": ["MQTT v5.0", "IEC 62443"],
    },
    {
        "name": "High-volume telemetry uses lightweight delivery",
        "domain": "Industrial IoT",
        "when": ["telemetry", "sensor data", "metric", "sampling"],
        "then": "Use MQTT QoS 0 (at-most-once) for high-frequency non-critical telemetry.",
        "rationale": "QoS 0 minimizes broker load and bandwidth where occasional loss is acceptable.",
        "standards": ["MQTT v5.0"],
    },
    {
        "name": "High availability requires broker redundancy",
        "domain": "Industrial IoT",
        "when": ["high availability", "ha", "redundant", "no single point", "99.9", "fault-tolerant"],
        "then": "Deploy a clustered/redundant MQTT broker with shared subscriptions and automatic failover.",
        "rationale": "A single broker is a single point of failure for the entire telemetry backbone.",
        "standards": ["MQTT v5.0"],
    },
    {
        "name": "Sensitive data must be encrypted at rest",
        "domain": "Cybersecurity",
        "when": ["phi", "pii", "patient", "health", "payment", "card", "financial", "hipaa", "pci"],
        "then": "Encrypt sensitive data at rest (AES-256) and in transit (TLS 1.2+); scope access with RBAC + audit logging.",
        "rationale": "Regulatory regimes (HIPAA, PCI-DSS, GDPR) mandate encryption and access controls for regulated data.",
        "standards": ["HIPAA", "PCI-DSS 4.0", "ISO 27001"],
    },
    {
        "name": "Public web surfaces need the OWASP baseline",
        "domain": "Cybersecurity",
        "when": ["web", "public api", "internet-facing", "frontend", "login", "authentication"],
        "then": "Apply the OWASP Top 10 baseline: input validation, output encoding, access control, and dependency scanning.",
        "rationale": "Internet-facing surfaces are the primary attack vector; the OWASP Top 10 covers the most exploited classes.",
        "standards": ["OWASP Top 10"],
    },
    {
        "name": "Predictive maintenance needs time-series storage",
        "domain": "Industrial IoT",
        "when": ["predictive maintenance", "remaining useful life", "anomaly detection", "vibration", "trending"],
        "then": "Persist telemetry in a time-series database (e.g. TimescaleDB/InfluxDB) with retention + downsampling policies.",
        "rationale": "Predictive models require efficient long-horizon time-series queries a relational store handles poorly.",
        "standards": ["ISA-95"],
    },
]


class EngineeringRulesEngine:
    def __init__(self, repository: Optional[EngineeringKnowledgeRepository] = None) -> None:
        self.repository = repository
        self.rules: List[Dict[str, Any]] = list(SEED_RULES)

    def seed(self) -> int:
        """Persist the seed rules as ENGINEERING_RULE knowledge objects."""
        if self.repository is None:
            return 0
        objs = []
        for rule in SEED_RULES:
            objs.append(KnowledgeObject(
                knowledge_id=stable_id(KnowledgeCategory.ENGINEERING_RULE.value, rule["domain"], rule["name"]),
                title=rule["name"],
                category=KnowledgeCategory.ENGINEERING_RULE.value,
                domain=rule["domain"],
                summary=rule["then"],
                body=f"{rule['then']}\n\nRationale: {rule['rationale']}",
                confidence=0.95,
                priority=8,
                tags=["rule"] + [s.lower() for s in rule.get("standards", [])],
                attributes={
                    "when": rule["when"],
                    "then": rule["then"],
                    "rationale": rule["rationale"],
                    "standards": rule.get("standards", []),
                },
            ))
        return self.repository.bulk_add(objs)

    def evaluate(
        self,
        message: str = "",
        domains: Optional[List[str]] = None,
        intent: str = "",
        entities: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return the rules that fire for this request."""
        haystack = " ".join([
            (message or "").lower(),
            (intent or "").lower(),
            " ".join(d.lower() for d in (domains or [])),
            " ".join(e.lower() for e in (entities or [])),
        ])
        applied = []
        for rule in self.rules:
            if any(signal in haystack for signal in rule["when"]):
                applied.append({
                    "name": rule["name"],
                    "domain": rule["domain"],
                    "then": rule["then"],
                    "rationale": rule["rationale"],
                    "standards": rule.get("standards", []),
                })
        return applied
