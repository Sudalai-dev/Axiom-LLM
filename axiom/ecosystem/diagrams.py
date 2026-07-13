"""
Diagram Library — reusable, structured engineering diagram templates.

Each template is a DIAGRAM knowledge object whose `attributes` carry multiple
renderable representations (mermaid now; plantuml / svg / reactflow fields are
schema-complete but may be empty this increment) plus the required components
and their relationships. The Engineering Intelligence Engine / presentation
pipeline can retrieve a template by domain or type instead of re-inventing a
diagram each time.
"""

from typing import Any, Dict, List, Optional

from ecosystem.models import KnowledgeCategory, KnowledgeObject, stable_id
from ecosystem.repository import EngineeringKnowledgeRepository


DIAGRAM_SEED: List[Dict[str, Any]] = [
    {
        "title": "MQTT Edge-to-Cloud Telemetry Topology",
        "domain": "Industrial IoT",
        "diagram_type": "topology",
        "required_components": ["Field Sensors", "Edge Gateway", "MQTT Broker", "Stream Processor", "Time-Series DB"],
        "relationships": ["Sensors->Edge Gateway", "Edge Gateway->MQTT Broker", "MQTT Broker->Stream Processor", "Stream Processor->Time-Series DB"],
        "mermaid": (
            "flowchart LR\n"
            "    S[Field Sensors] --> EG[Edge Gateway]\n"
            "    EG -->|MQTT QoS1| BR[MQTT Broker]\n"
            "    BR --> SP[Stream Processor]\n"
            "    SP --> TS[(Time-Series DB)]"
        ),
    },
    {
        "title": "REST API Request/Response Flow",
        "domain": "Software Engineering",
        "diagram_type": "sequence",
        "required_components": ["Client", "API Gateway", "Auth", "Service", "Database"],
        "relationships": ["Client->API Gateway", "API Gateway->Auth", "API Gateway->Service", "Service->Database"],
        "mermaid": (
            "sequenceDiagram\n"
            "    Client->>API Gateway: HTTPS request + JWT\n"
            "    API Gateway->>Auth: validate token\n"
            "    API Gateway->>Service: routed call\n"
            "    Service->>Database: query\n"
            "    Service-->>Client: JSON response"
        ),
    },
    {
        "title": "Predictive Maintenance Reference Architecture",
        "domain": "Industrial IoT",
        "diagram_type": "architecture",
        "required_components": ["Assets", "Edge", "Ingestion", "Time-Series DB", "ML Model", "Alerting"],
        "relationships": ["Assets->Edge", "Edge->Ingestion", "Ingestion->Time-Series DB", "Time-Series DB->ML Model", "ML Model->Alerting"],
        "mermaid": (
            "flowchart LR\n"
            "    A[Assets] --> E[Edge]\n"
            "    E --> I[Ingestion]\n"
            "    I --> T[(Time-Series DB)]\n"
            "    T --> M[ML Model / RUL]\n"
            "    M --> AL[Alerting + Work Orders]"
        ),
    },
    {
        "title": "Microservices Deployment (Kubernetes)",
        "domain": "DevOps",
        "diagram_type": "deployment",
        "required_components": ["Ingress", "Services", "PostgreSQL", "Redis"],
        "relationships": ["Ingress->Services", "Services->PostgreSQL", "Services->Redis"],
        "mermaid": (
            "flowchart TB\n"
            "    ING[Ingress + TLS] --> SVC[Services]\n"
            "    SVC --> DB[(PostgreSQL)]\n"
            "    SVC --> RD[(Redis)]"
        ),
    },
]


class DiagramLibrary:
    def __init__(self, repository: Optional[EngineeringKnowledgeRepository] = None) -> None:
        self.repository = repository

    def seed(self) -> int:
        if self.repository is None:
            return 0
        objs = []
        for d in DIAGRAM_SEED:
            objs.append(KnowledgeObject(
                knowledge_id=stable_id(KnowledgeCategory.DIAGRAM.value, d["domain"], d["title"]),
                title=d["title"],
                category=KnowledgeCategory.DIAGRAM.value,
                domain=d["domain"],
                summary=f"{d['diagram_type']} diagram template for {d['domain']}",
                body=d["mermaid"],
                confidence=0.9,
                priority=5,
                tags=["diagram", d["diagram_type"]],
                attributes={
                    "diagram_type": d["diagram_type"],
                    "mermaid": d["mermaid"],
                    "plantuml": "",
                    "svg": "",
                    "reactflow": {},
                    "required_components": d["required_components"],
                    "relationships": d["relationships"],
                },
            ))
        return self.repository.bulk_add(objs)

    def for_domain(self, domain: str, limit: int = 10) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []
        return [self._to_view(o) for o in self.repository.query(
            category=KnowledgeCategory.DIAGRAM.value, domain=domain, limit=limit)]

    def query(self, diagram_type: Optional[str] = None, q: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []
        views = [self._to_view(o) for o in self.repository.query(
            category=KnowledgeCategory.DIAGRAM.value, text=q, limit=limit)]
        if diagram_type:
            views = [v for v in views if v["diagram_type"] == diagram_type]
        return views

    @staticmethod
    def _to_view(obj: KnowledgeObject) -> Dict[str, Any]:
        a = obj.attributes or {}
        return {
            "title": obj.title,
            "domain": obj.domain,
            "diagram_type": a.get("diagram_type", ""),
            "mermaid": a.get("mermaid", obj.body),
            "required_components": a.get("required_components", []),
            "relationships": a.get("relationships", []),
        }
