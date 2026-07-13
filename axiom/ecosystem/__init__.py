"""
Engineering Knowledge Platform (`ecosystem/`) — AXIOM's permanent, durable,
graph-ready source of engineering intelligence.

Sits *beside* the Engineering Intelligence Engine (not inside the reasoning
pipeline). The engine consumes the platform; the platform grows from approved
solutions, ingested documents, and engineer feedback. The LLM remains only an
interchangeable inference provider — the intellectual property is this
knowledge and the reasoning architecture around it.

Public entry point: `KnowledgePlatform`.
"""

from ecosystem.analytics import KnowledgeAnalytics
from ecosystem.assembly import DynamicKnowledgeAssembler
from ecosystem.diagrams import DiagramLibrary
from ecosystem.ingestion import KnowledgeIngestor
from ecosystem.models import (
    ApprovalState,
    KnowledgeCategory,
    KnowledgeObject,
    Relationship,
    RelationType,
    VersionRecord,
)
from ecosystem.ontology import EngineeringOntology
from ecosystem.platform import KnowledgePlatform
from ecosystem.ranking import rank, score
from ecosystem.repository import EngineeringKnowledgeRepository
from ecosystem.rules import EngineeringRulesEngine
from ecosystem.seed import seed_platform
from ecosystem.standards import StandardsEngine

__all__ = [
    "KnowledgePlatform",
    "EngineeringKnowledgeRepository",
    "KnowledgeObject",
    "KnowledgeCategory",
    "ApprovalState",
    "Relationship",
    "RelationType",
    "VersionRecord",
    "StandardsEngine",
    "EngineeringRulesEngine",
    "EngineeringOntology",
    "DiagramLibrary",
    "KnowledgeAnalytics",
    "DynamicKnowledgeAssembler",
    "KnowledgeIngestor",
    "seed_platform",
    "rank",
    "score",
]
