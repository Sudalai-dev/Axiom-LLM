"""
Engineering Knowledge Platform — the single façade the rest of AXIOM depends on.

Bundles the durable repository and every typed engine (Standards, Rules,
Ontology, Diagrams, Analytics), the Dynamic Knowledge Assembler, and the
document Ingestor into one object. The Engineering Intelligence Engine receives
one `KnowledgePlatform` instance (injected, optional) and consumes it — it never
constructs its own, and it never imports the individual engines.

The platform sits *beside* the Engineering Intelligence Engine, not inside the
reasoning pipeline: the engine orchestrates, the platform supplies knowledge.
"""

from typing import Any, Dict, List, Optional

from ecosystem.analytics import KnowledgeAnalytics
from ecosystem.assembly import DynamicKnowledgeAssembler
from ecosystem.diagrams import DiagramLibrary
from ecosystem.ingestion import KnowledgeIngestor
from ecosystem.ontology import EngineeringOntology
from ecosystem.repository import EngineeringKnowledgeRepository
from ecosystem.rules import EngineeringRulesEngine
from ecosystem.seed import seed_platform
from ecosystem.standards import StandardsEngine


class KnowledgePlatform:
    def __init__(self, db_path: Optional[str] = None) -> None:
        self.repository = EngineeringKnowledgeRepository(db_path)
        self.standards = StandardsEngine(self.repository)
        self.rules = EngineeringRulesEngine(self.repository)
        self.ontology = EngineeringOntology(self.repository)
        self.diagrams = DiagramLibrary(self.repository)
        self.analytics = KnowledgeAnalytics(self.repository, self.standards)
        self.ingestor = KnowledgeIngestor(self.repository)
        self.assembler = DynamicKnowledgeAssembler(
            self.repository, self.standards, self.rules, self.ontology
        )

    def seed(self, force: bool = False) -> Dict[str, int]:
        return seed_platform(
            self.repository,
            standards_engine=self.standards,
            rules_engine=self.rules,
            ontology=self.ontology,
            diagram_library=self.diagrams,
            force=force,
        )

    # -- consumed by the Engineering Intelligence Engine --------------------

    def assemble_packs(
        self,
        domains: List[str],
        industry: Optional[str] = None,
        intent: str = "",
        entities: Optional[List[str]] = None,
        message: str = "",
    ) -> List[Dict[str, Any]]:
        return self.assembler.assemble(domains, industry, intent, entities, message)

    def standards_for(self, domains: List[str], industry: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.standards.for_domains(domains, industry)

    def rules_for(self, message: str, domains: List[str], intent: str = "", entities: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        return self.rules.evaluate(message, domains, intent, entities)
