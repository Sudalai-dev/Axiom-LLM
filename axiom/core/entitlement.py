"""Entitlement Service — the freemium daily-quota state machine.

Free users get ``OCIF_FREE_CHATS_PER_DAY`` agent calls per rolling 24h window
(``OCIF_FREE_QUOTA_WINDOW_HOURS``). The window starts on the first recorded
agent call and resets once it elapses. Paid users — and platform admins/
operators — bypass the cap entirely.

The three quota operations are deliberately separated so the API route can:
  1. ``evaluate`` before spending compute (block with 402 if exhausted), then
  2. run the agent, then
  3. ``record_agent_call`` only on a successful, billable solution.

All methods are fail-soft around the database in the same spirit as
``memory/learning_store.py``: an infrastructure error must not hard-block a
request, so a failed read degrades to "allowed on the free plan" rather than a
500. This is a monetization convenience layer, not a security boundary.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from core.config import settings
from core.models.base import UserRole
from storage.database import AsyncSessionLocal
from storage.models import Subscription

logger = logging.getLogger("AxiomEntitlement")

PLAN_FREE = "free"
PLAN_PAID = "paid"

# Roles that are never subject to the free quota (operators/staff).
_UNLIMITED_ROLES = {UserRole.PLATFORM_ADMIN.value, UserRole.TENANT_ADMIN.value}

_UNLIMITED_REMAINING = -1  # sentinel: quota does not apply (paid / privileged)


@dataclass
class EntitlementDecision:
    """Outcome of an entitlement check for a single request."""
    allowed: bool
    plan: str
    remaining: int                 # remaining free chats; -1 => unlimited
    renews_at: Optional[str]       # ISO-8601 reset time for the free window
    reason: str
    provider_hint: str             # "opencode" (free) | "" (platform auto/paid)
    free_chats_per_day: int = 0    # the applicable daily allowance

    @property
    def unlimited(self) -> bool:
        return self.remaining == _UNLIMITED_REMAINING


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalizes a possibly-naive DB datetime to timezone-aware UTC.

    SQLite round-trips datetimes as naive; treat those as UTC so window math
    is correct regardless of backend.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class EntitlementService:
    """Reads and mutates per-user :class:`Subscription` entitlement state."""

    def __init__(self, session_factory=AsyncSessionLocal) -> None:
        self._session_factory = session_factory
        self._window = timedelta(hours=settings.entitlement.free_quota_window_hours)
        self._limit = settings.entitlement.free_chats_per_day
        self._free_provider = settings.entitlement.free_provider

    # -- internals ----------------------------------------------------------

    async def _get_or_create(self, db, user_id: str, tenant_id: str) -> Subscription:
        sub = (await db.execute(
            select(Subscription).filter(Subscription.user_id == user_id)
        )).scalars().first()
        if sub is None:
            sub = Subscription(user_id=user_id, tenant_id=tenant_id, plan=PLAN_FREE, free_chats_used=0)
            db.add(sub)
            await db.commit()
            await db.refresh(sub)
        return sub

    def _is_paid(self, sub: Subscription) -> bool:
        if sub.plan != PLAN_PAID:
            return False
        paid_until = _as_aware_utc(sub.paid_until)
        # A null paid_until means a perpetual paid plan.
        return paid_until is None or paid_until > _now()

    def _window_expired(self, sub: Subscription) -> bool:
        start = _as_aware_utc(sub.quota_window_start)
        return start is None or (_now() - start) >= self._window

    def _renews_at(self, sub: Subscription) -> Optional[str]:
        start = _as_aware_utc(sub.quota_window_start)
        if start is None:
            return None
        return (start + self._window).isoformat()

    # -- public API ---------------------------------------------------------

    async def evaluate(self, user_id: str, tenant_id: str, role: str) -> EntitlementDecision:
        """Decides whether the user may make an agent call right now.

        Resets an elapsed free window (does NOT consume quota — that happens in
        :meth:`record_agent_call` after a successful call).
        """
        if role in _UNLIMITED_ROLES:
            return EntitlementDecision(
                allowed=True, plan=PLAN_PAID, remaining=_UNLIMITED_REMAINING,
                renews_at=None, reason="privileged_role", provider_hint="",
                free_chats_per_day=self._limit,
            )
        try:
            async with self._session_factory() as db:
                sub = await self._get_or_create(db, user_id, tenant_id)

                if self._is_paid(sub):
                    return EntitlementDecision(
                        allowed=True, plan=PLAN_PAID, remaining=_UNLIMITED_REMAINING,
                        renews_at=None, reason="paid_plan", provider_hint="",
                        free_chats_per_day=self._limit,
                    )

                # Free plan: reset the window if it has elapsed.
                if self._window_expired(sub) and (sub.free_chats_used or sub.quota_window_start):
                    sub.free_chats_used = 0
                    sub.quota_window_start = None
                    await db.commit()

                used = sub.free_chats_used or 0
                remaining = max(0, self._limit - used)
                allowed = remaining > 0
                return EntitlementDecision(
                    allowed=allowed,
                    plan=PLAN_FREE,
                    remaining=remaining,
                    renews_at=self._renews_at(sub),
                    reason="free_quota_available" if allowed else "free_quota_exhausted",
                    provider_hint=self._free_provider,
                    free_chats_per_day=self._limit,
                )
        except Exception as exc:  # fail-soft: never 500 on a metering hiccup
            logger.warning(f"Entitlement evaluate failed, allowing on free plan: {exc}")
            return EntitlementDecision(
                allowed=True, plan=PLAN_FREE, remaining=self._limit,
                renews_at=None, reason="degraded_allow", provider_hint=self._free_provider,
                free_chats_per_day=self._limit,
            )

    async def record_agent_call(self, user_id: str, tenant_id: str, role: str) -> None:
        """Consumes one free-quota unit after a successful agent call.

        No-op for paid/privileged users. Starts the 24h window on the first
        call of a fresh window.
        """
        if role in _UNLIMITED_ROLES:
            return
        try:
            async with self._session_factory() as db:
                sub = await self._get_or_create(db, user_id, tenant_id)
                if self._is_paid(sub):
                    return
                if self._window_expired(sub):
                    sub.free_chats_used = 0
                    sub.quota_window_start = _now()
                elif sub.quota_window_start is None:
                    sub.quota_window_start = _now()
                sub.free_chats_used = (sub.free_chats_used or 0) + 1
                await db.commit()
        except Exception as exc:
            logger.warning(f"Entitlement record_agent_call failed (usage under-counts): {exc}")

    async def mark_paid(self, user_id: str, tenant_id: str, until: Optional[datetime] = None) -> None:
        """Upgrades a user to the paid plan (optionally time-limited)."""
        async with self._session_factory() as db:
            sub = await self._get_or_create(db, user_id, tenant_id)
            sub.plan = PLAN_PAID
            sub.paid_until = until
            await db.commit()

    async def mark_free(self, user_id: str, tenant_id: str) -> None:
        """Downgrades a user back to the free plan (e.g. on refund/expiry)."""
        async with self._session_factory() as db:
            sub = await self._get_or_create(db, user_id, tenant_id)
            sub.plan = PLAN_FREE
            sub.paid_until = None
            await db.commit()

    async def get_status(self, user_id: str, tenant_id: str, role: str) -> dict:
        """Returns a client-facing entitlement summary for the billing UI."""
        decision = await self.evaluate(user_id, tenant_id, role)
        return {
            "plan": decision.plan,
            "unlimited": decision.unlimited,
            "remaining": None if decision.unlimited else decision.remaining,
            "free_chats_per_day": self._limit,
            "renews_at": decision.renews_at,
            "price_usd": settings.entitlement.paid_plan_price_usd,
        }
