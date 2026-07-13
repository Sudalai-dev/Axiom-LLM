"""
Knowledge Ranking Engine.

Deterministic score over a `KnowledgeObject`'s quality/utility signals so the
Engineering Intelligence Engine always retrieves the highest-ranked knowledge
first. Pure functions — no I/O, no state.

Signals (mission-specified): confidence, usage, engineer rating, approval
count, freshness, success rate, priority.
"""

from datetime import datetime, timezone
from math import log1p
from typing import List

from ecosystem.models import KnowledgeObject

# Relative weights. Tuned so a fresh, high-confidence, well-used, engineer-rated
# object outranks a stale unused one, without any single signal dominating.
_WEIGHTS = {
    "confidence": 0.28,
    "success_rate": 0.20,
    "rating": 0.16,
    "usage": 0.14,
    "freshness": 0.12,
    "approval": 0.05,
    "priority": 0.05,
}

_FRESHNESS_HALF_LIFE_DAYS = 180.0  # a 6-month-old entry keeps ~half its freshness


def _freshness(obj: KnowledgeObject) -> float:
    """Recency of the last update, decayed toward 0 as the entry ages."""
    try:
        updated = datetime.fromisoformat(obj.updated_at)
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - updated).total_seconds() / 86400.0)
        return 0.5 ** (age_days / _FRESHNESS_HALF_LIFE_DAYS)
    except Exception:
        return float(obj.freshness or 0.0)


def score(obj: KnowledgeObject) -> float:
    """Composite rank score in ~[0, 1]. Higher is better."""
    usage_norm = min(1.0, log1p(max(0, obj.usage_count)) / log1p(100))
    approval_norm = min(1.0, log1p(max(0, obj.approval_count)) / log1p(20))
    priority_norm = min(1.0, max(0, obj.priority) / 10.0)
    rating_norm = min(1.0, max(0.0, obj.rating) / 5.0)
    return round(
        _WEIGHTS["confidence"] * max(0.0, min(1.0, obj.confidence))
        + _WEIGHTS["success_rate"] * max(0.0, min(1.0, obj.success_rate))
        + _WEIGHTS["rating"] * rating_norm
        + _WEIGHTS["usage"] * usage_norm
        + _WEIGHTS["freshness"] * _freshness(obj)
        + _WEIGHTS["approval"] * approval_norm
        + _WEIGHTS["priority"] * priority_norm,
        6,
    )


def rank(objects: List[KnowledgeObject]) -> List[KnowledgeObject]:
    """Return objects sorted by descending rank score (stable for ties)."""
    return sorted(objects, key=score, reverse=True)
