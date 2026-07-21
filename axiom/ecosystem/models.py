"""
Knowledge model — the graph-ready property model of the Engineering Knowledge
Platform.

Everything the platform stores is a `KnowledgeObject` (a node) connected by
typed `Relationship` edges. Standards, patterns, rules, diagrams, failure
modes, etc. are all `KnowledgeObject`s distinguished by `category`, with
category-specific structured data carried in the flexible `attributes` JSON
field. This node + edge + properties shape is a property graph on disk, so a
future migration to a real graph database is a data move, not a redesign.

Deliberately stdlib-only (dataclasses + enums) so the platform stays
self-contained, mirroring `memory/learning_store.py`.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid

# Stable namespace so seeding is idempotent: the same (category, domain, title)
# always resolves to the same knowledge_id, turning re-seeds into upserts.
_ID_NAMESPACE = uuid.UUID("a1c1f0de-0000-4000-8000-000000000001")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def stable_id(category: str, domain: str, title: str) -> str:
    """Deterministic id for seeded knowledge, so re-seeding never duplicates."""
    key = f"{category}|{domain}|{title}".lower().strip()
    return str(uuid.uuid5(_ID_NAMESPACE, key))


class KnowledgeCategory(str, Enum):
    """The ~25 categories the platform must support (mission-specified)."""
    STANDARD = "standard"
    PATTERN = "pattern"
    ARCHITECTURE = "architecture"
    REFERENCE_ARCHITECTURE = "reference_architecture"
    BLUEPRINT = "blueprint"
    TECHNOLOGY = "technology"
    COMPONENT = "component"
    PROTOCOL = "protocol"
    FAILURE_MODE = "failure_mode"
    LESSON_LEARNED = "lesson_learned"
    CASE_STUDY = "case_study"
    CALCULATION = "calculation"
    ENGINEERING_RULE = "engineering_rule"
    CHECKLIST = "checklist"
    TEMPLATE = "template"
    GLOSSARY = "glossary"
    BEST_PRACTICE = "best_practice"
    REFERENCE_PROJECT = "reference_project"
    DOCUMENT = "document"
    DIAGRAM = "diagram"
    WORKFLOW = "workflow"
    API = "api"
    DATABASE = "database"
    SENSOR = "sensor"
    INDUSTRIAL_ASSET = "industrial_asset"


class ApprovalState(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RelationType(str, Enum):
    """Typed edges. Traversal is not implemented this increment, but the schema
    preserves every relationship for future graph reasoning."""
    PARENT_OF = "parent_of"
    CHILD_OF = "child_of"
    RELATED_TO = "related_to"
    APPLIES_STANDARD = "applies_standard"
    USES_TECHNOLOGY = "uses_technology"
    HAS_DIAGRAM = "has_diagram"
    HAS_COMPONENT = "has_component"
    HAS_DOCUMENT = "has_document"
    DEPENDS_ON = "depends_on"
    MITIGATES = "mitigates"


# Persisted columns of `knowledge_objects`, in order. The repository relies on
# this being the exact column list.
COLUMNS: List[str] = [
    "knowledge_id", "version", "title", "summary", "body", "category",
    "domain", "industry", "tags", "confidence", "usage_count", "success_rate",
    "priority", "freshness", "rating", "approval_count", "approval_status",
    "author", "reviewer", "user_id", "source_document", "created_at",
    "updated_at", "attributes",
]

# The "*" user marks globally-visible (seeded/organizational) knowledge that
# every user can read.
GLOBAL_SCOPE = "*"


@dataclass
class Relationship:
    source_id: str
    relation_type: str
    target_id: str


@dataclass
class VersionRecord:
    knowledge_id: str
    version: int
    body: str
    attributes: Dict[str, Any]
    reviewer: str
    reason: str
    change_summary: str
    approval_notes: str
    created_at: str


@dataclass
class KnowledgeObject:
    """A single node in the Engineering Knowledge Platform."""
    title: str = ""
    category: str = KnowledgeCategory.DOCUMENT.value
    domain: str = ""
    industry: str = ""
    summary: str = ""
    body: str = ""
    knowledge_id: str = field(default_factory=new_id)
    version: int = 1
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.80
    usage_count: int = 0
    success_rate: float = 0.0
    priority: int = 0
    freshness: float = 1.0
    rating: float = 0.0
    approval_count: int = 0
    approval_status: str = ApprovalState.APPROVED.value
    author: str = "system"
    reviewer: str = ""
    user_id: str = GLOBAL_SCOPE
    source_document: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    attributes: Dict[str, Any] = field(default_factory=dict)

    # Relationship-derived views — hydrated on load from the edge table, never
    # persisted as columns (they are projections of `knowledge_relationships`).
    related_knowledge: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    applicable_standards: List[str] = field(default_factory=list)
    applicable_technologies: List[str] = field(default_factory=list)
    related_diagrams: List[str] = field(default_factory=list)
    related_components: List[str] = field(default_factory=list)
    related_documents: List[str] = field(default_factory=list)

    def to_row(self) -> tuple:
        """Serialize to a tuple matching COLUMNS for SQLite insertion."""
        return (
            self.knowledge_id, self.version, self.title, self.summary, self.body,
            self.category, self.domain, self.industry, json.dumps(self.tags),
            self.confidence, self.usage_count, self.success_rate, self.priority,
            self.freshness, self.rating, self.approval_count, self.approval_status,
            self.author, self.reviewer, self.user_id, self.source_document,
            self.created_at, self.updated_at, json.dumps(self.attributes),
        )

    @classmethod
    def from_row(cls, row: tuple) -> "KnowledgeObject":
        data = dict(zip(COLUMNS, row))
        data["tags"] = json.loads(data["tags"]) if data["tags"] else []
        data["attributes"] = json.loads(data["attributes"]) if data["attributes"] else {}
        return cls(**data)

    def to_public_dict(self) -> Dict[str, Any]:
        """User-facing representation (API responses / analytics)."""
        return {
            "knowledge_id": self.knowledge_id,
            "version": self.version,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "domain": self.domain,
            "industry": self.industry,
            "tags": self.tags,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "priority": self.priority,
            "approval_status": self.approval_status,
            "updated_at": self.updated_at,
            "attributes": self.attributes,
            "related_knowledge": self.related_knowledge,
            "applicable_standards": self.applicable_standards,
            "applicable_technologies": self.applicable_technologies,
            "related_diagrams": self.related_diagrams,
        }
