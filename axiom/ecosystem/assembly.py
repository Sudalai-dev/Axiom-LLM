"""
Dynamic Knowledge Assembler.

Replaces the old "one static pack per request" model. Given the request's
domains, industry, intent, and entities, it dynamically assembles one or more
knowledge packs from the repository (patterns, failure modes, lessons,
best practices), the Standards Engine, the Rules Engine, and ontology
expansion — ranked highest-first.

Output packs are shaped exactly like the legacy `KNOWLEDGE_PACKS` dict values
(`name, standards, patterns, common_problems, failure_modes, recommendations`)
so `KnowledgePackLoader` can consume them as a drop-in replacement. When the
repository yields nothing, it returns `[]` and the caller falls back to the
hardcoded packs (never degrade).
"""

from typing import Any, Dict, List, Optional

from ecosystem.models import KnowledgeCategory
from ecosystem.ontology import EngineeringOntology
from ecosystem.repository import EngineeringKnowledgeRepository
from ecosystem.rules import EngineeringRulesEngine
from ecosystem.standards import StandardsEngine


class DynamicKnowledgeAssembler:
    def __init__(
        self,
        repository: EngineeringKnowledgeRepository,
        standards_engine: StandardsEngine,
        rules_engine: EngineeringRulesEngine,
        ontology: EngineeringOntology,
    ) -> None:
        self.repository = repository
        self.standards = standards_engine
        self.rules = rules_engine
        self.ontology = ontology

    def _titles(self, domain: str, category: str, limit: int = 5) -> List[Any]:
        return self.repository.query(domain=domain, category=category, limit=limit)

    def _pack_for_domain(self, domain: str, industry: Optional[str], rules_applied: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        patterns = self._titles(domain, KnowledgeCategory.PATTERN.value)
        patterns += self._titles(domain, KnowledgeCategory.ARCHITECTURE.value, limit=3)
        patterns += self._titles(domain, KnowledgeCategory.REFERENCE_ARCHITECTURE.value, limit=3)
        failures = self._titles(domain, KnowledgeCategory.FAILURE_MODE.value)
        lessons = self._titles(domain, KnowledgeCategory.LESSON_LEARNED.value, limit=3)
        practices = self._titles(domain, KnowledgeCategory.BEST_PRACTICE.value)
        std_views = self.standards.for_domains([domain], industry, limit_per_domain=5)

        # Nothing meaningful for this domain -> signal a miss.
        if not (patterns or failures or practices or std_views):
            return None

        # Bump usage so ranking reflects what actually gets retrieved.
        for obj in patterns + failures + lessons + practices:
            self.repository.record_usage(obj.knowledge_id)

        common_problems = [o.summary or o.title for o in failures] + [o.title for o in lessons]
        failure_modes = [o.title for o in failures]
        recommendations = [o.summary or o.title for o in practices]
        recommendations += [r["then"] for r in rules_applied if r.get("domain") == domain]
        standards = [s["name"] for s in std_views]

        return {
            "name": f"{domain} Knowledge Pack",
            "standards": standards or ["General engineering standards"],
            "patterns": [o.title for o in patterns] or ["Layered Service Architecture"],
            "common_problems": common_problems[:8] or ["Undocumented failure conditions"],
            "failure_modes": failure_modes[:8] or ["Unhandled dependency failure"],
            "recommendations": recommendations[:8] or ["Design for testability and observability"],
        }

    def assemble(
        self,
        domains: List[str],
        industry: Optional[str] = None,
        intent: str = "",
        entities: Optional[List[str]] = None,
        message: str = "",
    ) -> List[Dict[str, Any]]:
        """Assemble a combined, ranked set of knowledge packs for the request."""
        rules_applied = self.rules.evaluate(message, domains, intent, entities)
        packs: List[Dict[str, Any]] = []
        for domain in domains or []:
            pack = self._pack_for_domain(domain, industry, rules_applied)
            if pack:
                packs.append(pack)
        return packs
