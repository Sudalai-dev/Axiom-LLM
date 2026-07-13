"""
Platform seeding — migrates AXIOM's in-code engineering knowledge into the
durable Engineering Knowledge Platform.

Seeds (all with stable, content-derived ids so re-seeding upserts rather than
duplicates):
  * the legacy hardcoded `KNOWLEDGE_PACKS`  -> patterns / failure modes /
    best practices / reference architectures
  * `STANDARDS_REGISTRY`                     -> Standards Engine
  * `FAILURE_ANALYSIS_TEMPLATES`             -> failure modes
  * seeded engineering rules, ontology, and diagram templates

This is the point where AXIOM's intelligence stops living in source code and
starts living in an evolvable, human-governed repository. The hardcoded packs
remain in place as the guaranteed fallback.
"""

from typing import Any, Dict, List, Optional

from ecosystem.models import KnowledgeCategory, KnowledgeObject, stable_id
from ecosystem.repository import EngineeringKnowledgeRepository

_SEED_MARKER = "seeded_v1"

# KNOWLEDGE_PACKS key -> the domain label the DomainClassifier emits, so the
# assembler (which queries by those labels) finds this knowledge.
_PACK_DOMAIN = {
    "software/backend": "Software Engineering",
    "software/frontend": "Software Engineering",
    "database": "Database Engineering",
    "cloud": "DevOps",
    "mqtt": "Industrial IoT",
    "industrial/hvac": "Mechanical Engineering",
    "robotics": "Mechanical Engineering",
    "networking/security": "Cybersecurity",
}

_FAILURE_DOMAIN = {
    "mechanical": "Mechanical Engineering",
    "electrical": "Electrical Engineering",
    "software": "Software Engineering",
    "networking": "DevOps",
    "cloud": "DevOps",
    "industrial": "Industrial IoT",
}


def _obj(category: str, domain: str, title: str, summary: str = "", body: str = "",
         confidence: float = 0.85, priority: int = 4, tags: Optional[List[str]] = None,
         attributes: Optional[Dict[str, Any]] = None) -> KnowledgeObject:
    return KnowledgeObject(
        knowledge_id=stable_id(category, domain, title),
        title=title,
        category=category,
        domain=domain,
        summary=summary or title,
        body=body or summary or title,
        confidence=confidence,
        priority=priority,
        tags=tags or [],
        attributes=attributes or {},
    )


def _seed_knowledge_packs(repo: EngineeringKnowledgeRepository) -> int:
    from ocif.engines.engineering_intelligence import KNOWLEDGE_PACKS

    objs: List[KnowledgeObject] = []
    for key, pack in KNOWLEDGE_PACKS.items():
        domain = _PACK_DOMAIN.get(key, "Software Engineering")
        # Reference architecture node for the pack itself.
        ref = _obj(KnowledgeCategory.REFERENCE_ARCHITECTURE.value, domain, pack["name"],
                   summary=pack["name"], confidence=0.9, priority=6,
                   tags=["seed", key], attributes={"pack_key": key})
        objs.append(ref)
        for p in pack.get("patterns", []):
            objs.append(_obj(KnowledgeCategory.PATTERN.value, domain, p, summary=p, priority=5, tags=["seed", key]))
        for cp in pack.get("common_problems", []):
            objs.append(_obj(KnowledgeCategory.FAILURE_MODE.value, domain, cp, summary=cp, tags=["seed", "common_problem", key]))
        for fm in pack.get("failure_modes", []):
            objs.append(_obj(KnowledgeCategory.FAILURE_MODE.value, domain, fm, summary=fm, tags=["seed", "failure_mode", key]))
        for rec in pack.get("recommendations", []):
            objs.append(_obj(KnowledgeCategory.BEST_PRACTICE.value, domain, rec, summary=rec, priority=5, tags=["seed", key]))
    return repo.bulk_add(objs)


def _seed_failure_templates(repo: EngineeringKnowledgeRepository) -> int:
    from datasets.registry import FAILURE_ANALYSIS_TEMPLATES

    objs: List[KnowledgeObject] = []
    for group, templates in FAILURE_ANALYSIS_TEMPLATES.items():
        domain = _FAILURE_DOMAIN.get(group, "Software Engineering")
        for t in templates:
            title = t["problem"]
            body = (
                f"Symptoms: {', '.join(t.get('symptoms', []))}\n"
                f"Possible causes: {', '.join(t.get('possible_causes', []))}\n"
                f"Diagnostic tests: {', '.join(t.get('tests', []))}\n"
                f"Preventive action: {t.get('preventive_action', '')}"
            )
            objs.append(_obj(
                KnowledgeCategory.FAILURE_MODE.value, domain, title,
                summary=title, body=body, confidence=0.9, priority=6,
                tags=["seed", "rca", group],
                attributes={
                    "symptoms": t.get("symptoms", []),
                    "possible_causes": t.get("possible_causes", []),
                    "tests": t.get("tests", []),
                    "preventive_action": t.get("preventive_action", ""),
                },
            ))
    return repo.bulk_add(objs)


def seed_platform(
    repository: EngineeringKnowledgeRepository,
    standards_engine=None,
    rules_engine=None,
    ontology=None,
    diagram_library=None,
    force: bool = False,
) -> Dict[str, int]:
    """Idempotent. Returns a per-source count of objects seeded (0s on a
    no-op re-run unless force=True)."""
    if not force and repository.meta_get(_SEED_MARKER):
        return {"skipped": 1}

    counts: Dict[str, int] = {}
    counts["knowledge_packs"] = _seed_knowledge_packs(repository)
    counts["failure_templates"] = _seed_failure_templates(repository)
    if standards_engine is not None:
        counts["standards"] = standards_engine.seed()
    if rules_engine is not None:
        counts["rules"] = rules_engine.seed()
    if ontology is not None:
        counts["ontology_nodes"] = ontology.seed()
    if diagram_library is not None:
        counts["diagrams"] = diagram_library.seed()

    repository.meta_set(_SEED_MARKER, "1")
    return counts
