"""
Knowledge Analytics — visibility into what AXIOM knows and where the gaps are.

Reports coverage (domain / industry / category / standards), freshness,
most/least used knowledge, missing domains and standards, and an overall
quality signal. Read-only over the repository; drives the
`/api/v1/platform/analytics` endpoint and future knowledge-evolution decisions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ecosystem.models import KnowledgeCategory
from ecosystem.repository import EngineeringKnowledgeRepository
from ecosystem.standards import StandardsEngine

# The engineering domains AXIOM aims to cover (mission-specified). Used to
# surface gaps.
EXPECTED_DOMAINS = [
    "Software Engineering", "Artificial Intelligence", "Industrial IoT",
    "Mechanical Engineering", "Electrical Engineering", "Cloud Computing",
    "Networking", "Cybersecurity", "Automation", "Embedded Systems",
    "DevOps", "Enterprise Architecture", "Business Analysis", "Data Engineering",
    "Database Engineering",
]

EXPECTED_STANDARDS = [
    "ISA-95", "IEC 62443", "ISO 27001", "NIST CSF", "OWASP Top 10", "HIPAA",
    "PCI-DSS 4.0", "GDPR", "MQTT v5.0", "OpenAPI 3.0", "REST",
]

_STALE_DAYS = 365.0


class KnowledgeAnalytics:
    def __init__(self, repository: EngineeringKnowledgeRepository, standards_engine: Optional[StandardsEngine] = None) -> None:
        self.repository = repository
        self.standards_engine = standards_engine

    def coverage(self) -> Dict[str, Any]:
        domain_counts = self.repository.domain_counts()
        category_counts = self.repository.category_counts()
        present_domains = {d for d in domain_counts if d}
        missing_domains = [d for d in EXPECTED_DOMAINS if d not in present_domains]

        present_standards = {v["name"] for v in (self.standards_engine.query(limit=100) if self.standards_engine else [])}
        missing_standards = [s for s in EXPECTED_STANDARDS if s not in present_standards]

        most_used = [
            {"title": o.title, "category": o.category, "usage_count": o.usage_count}
            for o in self.repository.most_used(limit=5)
        ]
        least_used = [
            {"title": o.title, "category": o.category, "usage_count": o.usage_count}
            for o in self.repository.least_used(limit=5)
        ]

        total = self.repository.count()
        return {
            "total_objects": total,
            "domain_coverage": domain_counts,
            "category_coverage": category_counts,
            "standards_count": category_counts.get(KnowledgeCategory.STANDARD.value, 0),
            "missing_domains": missing_domains,
            "missing_standards": missing_standards,
            "domain_coverage_pct": round(100.0 * (len(EXPECTED_DOMAINS) - len(missing_domains)) / len(EXPECTED_DOMAINS), 1),
            "standards_coverage_pct": round(100.0 * (len(EXPECTED_STANDARDS) - len(missing_standards)) / len(EXPECTED_STANDARDS), 1),
            "most_used": most_used,
            "least_used": least_used,
            "quality": self._quality(),
            "freshness": self._freshness(),
        }

    def _quality(self) -> Dict[str, Any]:
        """Average confidence across all knowledge (a coarse quality signal)."""
        objs = self.repository.query(approved_only=False, ranked=False, limit=1000)
        if not objs:
            return {"avg_confidence": 0.0, "sampled": 0}
        avg = sum(o.confidence for o in objs) / len(objs)
        return {"avg_confidence": round(avg, 3), "sampled": len(objs)}

    def _freshness(self) -> Dict[str, Any]:
        objs = self.repository.query(approved_only=False, ranked=False, limit=1000)
        if not objs:
            return {"stale_count": 0, "stale_fraction": 0.0, "sampled": 0}
        now = datetime.now(timezone.utc)
        stale = 0
        for o in objs:
            try:
                updated = datetime.fromisoformat(o.updated_at)
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if (now - updated).total_seconds() / 86400.0 > _STALE_DAYS:
                    stale += 1
            except Exception:
                continue
        return {
            "stale_count": stale,
            "stale_fraction": round(stale / len(objs), 3),
            "sampled": len(objs),
        }
