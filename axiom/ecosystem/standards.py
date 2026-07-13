"""
Standards Engine — an expanded, queryable view of engineering standards.

Seeds from the real `STANDARDS_REGISTRY` in `datasets/registry.py` and enriches
each standard into the mission's expanded model (scope, domains, industries,
sections, requirements, compliance level, related standards, architecture
impact). A query returns the *relevant sections and requirements* of a
standard, not merely its name — so the Engineering Intelligence Engine can cite
concrete constraints.

Standards are persisted as STANDARD knowledge objects in the shared repository,
so they rank, version, and analyze like any other knowledge; this class is a
typed facade over that store.
"""

from typing import Any, Dict, List, Optional

from ecosystem.models import KnowledgeCategory, KnowledgeObject, stable_id
from ecosystem.repository import EngineeringKnowledgeRepository

# Which structured key in a STANDARDS_REGISTRY entry enumerates its
# sections/requirements, per standard shape.
_SECTION_KEYS = [
    "key_models", "key_parts", "key_clauses", "key_functions",
    "vulnerabilities", "key_rules", "key_principles", "constraints", "features",
]

# Standard key -> (domains, industries, compliance_level). Compliance level:
# "mandatory" for regulated regimes, "recommended" otherwise.
_STANDARD_MAP: Dict[str, Dict[str, Any]] = {
    "isa_95":      {"domains": ["Industrial IoT"], "industries": ["industrial_iot", "manufacturing"], "compliance": "recommended"},
    "iec_62443":   {"domains": ["Industrial IoT", "Cybersecurity"], "industries": ["industrial_iot", "energy"], "compliance": "mandatory"},
    "iso_27001":   {"domains": ["Cybersecurity", "DevOps"], "industries": ["generic_software", "ai_ml_platform"], "compliance": "recommended"},
    "nist_csf":    {"domains": ["Cybersecurity"], "industries": ["generic_software", "energy"], "compliance": "recommended"},
    "owasp_top10": {"domains": ["Cybersecurity", "Software Engineering"], "industries": ["generic_software", "retail_ecommerce"], "compliance": "recommended"},
    "hipaa":       {"domains": ["Cybersecurity", "Software Engineering"], "industries": ["healthcare"], "compliance": "mandatory"},
    "pci_dss":     {"domains": ["Cybersecurity"], "industries": ["banking_fintech", "retail_ecommerce"], "compliance": "mandatory"},
    "gdpr":        {"domains": ["Cybersecurity", "Software Engineering"], "industries": ["generic_software", "retail_ecommerce"], "compliance": "mandatory"},
    "iso_9001":    {"domains": ["Enterprise Architecture"], "industries": ["manufacturing", "generic_software"], "compliance": "recommended"},
    "mqtt_v5":     {"domains": ["Industrial IoT"], "industries": ["industrial_iot", "automotive", "agriculture"], "compliance": "recommended"},
    "openapi_3":   {"domains": ["Software Engineering"], "industries": ["generic_software"], "compliance": "recommended"},
    "rest":        {"domains": ["Software Engineering"], "industries": ["generic_software"], "compliance": "recommended"},
    "graphql":     {"domains": ["Software Engineering"], "industries": ["generic_software"], "compliance": "recommended"},
}


class StandardsEngine:
    def __init__(self, repository: Optional[EngineeringKnowledgeRepository] = None) -> None:
        self.repository = repository

    # -- seeding -------------------------------------------------------------

    @staticmethod
    def _expand(key: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Turn a raw STANDARDS_REGISTRY entry into the expanded standard model."""
        meta = _STANDARD_MAP.get(key, {"domains": ["Software Engineering"], "industries": ["generic_software"], "compliance": "recommended"})
        sections: List[str] = []
        for sk in _SECTION_KEYS:
            if isinstance(raw.get(sk), list):
                sections.extend(raw[sk])
        requirements_count = raw.get("requirements_count")
        return {
            "key": key,
            "name": raw.get("name", key),
            "full_name": raw.get("full_name", ""),
            "scope": raw.get("scope", ""),
            "architecture_impact": raw.get("architecture_impact", ""),
            "standard_ref": raw.get("standard_ref", ""),
            "domains": meta["domains"],
            "industries": meta["industries"],
            "compliance_level": meta["compliance"],
            "sections": sections,
            "requirements_count": requirements_count,
        }

    def seed(self) -> int:
        if self.repository is None:
            return 0
        from datasets.registry import STANDARDS_REGISTRY

        objs: List[KnowledgeObject] = []
        for key, raw in STANDARDS_REGISTRY.items():
            std = self._expand(key, raw)
            primary_domain = std["domains"][0] if std["domains"] else ""
            objs.append(KnowledgeObject(
                knowledge_id=stable_id(KnowledgeCategory.STANDARD.value, primary_domain, std["name"]),
                title=std["name"],
                category=KnowledgeCategory.STANDARD.value,
                domain=primary_domain,
                industry=std["industries"][0] if std["industries"] else "",
                summary=f"{std['full_name']} — {std['scope']}",
                body=std["architecture_impact"],
                confidence=0.97,
                priority=9 if std["compliance_level"] == "mandatory" else 6,
                tags=["standard", key] + [d.lower() for d in std["domains"]],
                attributes=std,
            ))
        return self.repository.bulk_add(objs)

    # -- queries -------------------------------------------------------------

    def _to_view(self, obj: KnowledgeObject) -> Dict[str, Any]:
        a = obj.attributes or {}
        return {
            "name": obj.title,
            "full_name": a.get("full_name", ""),
            "scope": a.get("scope", ""),
            "domains": a.get("domains", [obj.domain]),
            "industries": a.get("industries", []),
            "compliance_level": a.get("compliance_level", "recommended"),
            "sections": a.get("sections", []),
            "requirements_count": a.get("requirements_count"),
            "architecture_impact": a.get("architecture_impact", obj.body),
            "standard_ref": a.get("standard_ref", ""),
        }

    def query(self, domain: Optional[str] = None, industry: Optional[str] = None, q: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if self.repository is None:
            return []
        results = self.repository.query(
            category=KnowledgeCategory.STANDARD.value, domain=domain, text=q, limit=limit,
        )
        views = [self._to_view(o) for o in results]
        if industry:
            views = [v for v in views if industry.lower() in [i.lower() for i in v["industries"]]] or views
        return views

    def for_domains(self, domains: List[str], industry: Optional[str] = None, limit_per_domain: int = 6) -> List[Dict[str, Any]]:
        """Standards applicable to any of the given domains (deduped by name),
        with mandatory ones for the industry surfaced first."""
        if self.repository is None:
            return []
        seen: Dict[str, Dict[str, Any]] = {}
        for domain in domains or []:
            for view in self.query(domain=domain, limit=limit_per_domain):
                seen.setdefault(view["name"], view)
        if industry:
            for view in self.query(limit=50):
                if industry.lower() in [i.lower() for i in view["industries"]]:
                    seen.setdefault(view["name"], view)
        views = list(seen.values())
        views.sort(key=lambda v: 0 if v["compliance_level"] == "mandatory" else 1)
        return views
