"""Entitlement quota state-machine tests.

Exercises the daily free-chat quota: 5 allowed per window, the 6th blocked,
the window reset after 24h, and paid/privileged bypass. Uses an isolated
temp-file SQLite database with a custom session factory so it never touches
the dev database.

Each test runs its full setup + logic inside a single ``asyncio.run`` so the
async engine's connection pool is bound to exactly one event loop (avoids the
order-dependent "no current event loop" / cross-loop errors that
``get_event_loop()`` causes under Python 3.13).
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.entitlement import EntitlementService
from storage.database import Base
from storage.models import Subscription  # noqa: F401 — registers the model on Base

USER = "u-1"
TENANT = "t-1"


async def _make_service(tmp_path):
    db_file = tmp_path / "entitlement_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return EntitlementService(session_factory=factory), factory


def test_five_free_chats_allowed_sixth_blocked(tmp_path):
    async def run():
        svc, _ = await _make_service(tmp_path)
        for i in range(5):
            decision = await svc.evaluate(USER, TENANT, "end_user")
            assert decision.allowed, f"call {i} should be allowed"
            assert decision.plan == "free"
            assert decision.remaining == 5 - i
            await svc.record_agent_call(USER, TENANT, "end_user")

        blocked = await svc.evaluate(USER, TENANT, "end_user")
        assert not blocked.allowed
        assert blocked.remaining == 0
        assert blocked.reason == "free_quota_exhausted"
        assert blocked.renews_at is not None

    asyncio.run(run())


def test_window_resets_after_24h(tmp_path):
    async def run():
        svc, factory = await _make_service(tmp_path)
        for _ in range(5):
            await svc.record_agent_call(USER, TENANT, "end_user")
        assert not (await svc.evaluate(USER, TENANT, "end_user")).allowed

        # Backdate the window start beyond the 24h horizon.
        async with factory() as db:
            sub = (await db.execute(
                select(Subscription).filter(Subscription.user_id == USER)
            )).scalars().first()
            sub.quota_window_start = datetime.now(timezone.utc) - timedelta(hours=25)
            await db.commit()

        renewed = await svc.evaluate(USER, TENANT, "end_user")
        assert renewed.allowed
        assert renewed.remaining == 5

    asyncio.run(run())


def test_paid_plan_bypasses_quota(tmp_path):
    async def run():
        svc, _ = await _make_service(tmp_path)
        for _ in range(10):
            await svc.record_agent_call(USER, TENANT, "end_user")
        await svc.mark_paid(USER, TENANT)
        decision = await svc.evaluate(USER, TENANT, "end_user")
        assert decision.allowed
        assert decision.plan == "paid"
        assert decision.unlimited
        assert decision.provider_hint == ""  # platform provider, not OpenCode

    asyncio.run(run())


def test_privileged_role_is_unlimited(tmp_path):
    async def run():
        svc, _ = await _make_service(tmp_path)
        decision = await svc.evaluate(USER, TENANT, "platform_admin")
        assert decision.allowed and decision.unlimited
        # Recording is a no-op for privileged roles.
        await svc.record_agent_call(USER, TENANT, "platform_admin")
        assert (await svc.evaluate(USER, TENANT, "platform_admin")).unlimited

    asyncio.run(run())


def test_status_shape_for_free_user(tmp_path):
    async def run():
        svc, _ = await _make_service(tmp_path)
        status = await svc.get_status(USER, TENANT, "end_user")
        assert status["plan"] == "free"
        assert status["remaining"] == 5
        assert status["free_chats_per_day"] == 5
        assert status["unlimited"] is False

    asyncio.run(run())
