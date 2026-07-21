"""Phase 8 — PostgreSQL foundation: AXIOM_DATABASE_URL resolution.

A single AXIOM_DATABASE_URL points AXIOM at Postgres in production; the app URL
must use the async driver (asyncpg) and the Alembic URL the sync driver
(psycopg2/plain). With no override, AXIOM falls back to a local SQLite file so
the suite (and any offline run) needs nothing external.
"""

from core.config import DatabaseConfig


def test_no_override_falls_back_to_sqlite():
    cfg = DatabaseConfig()   # no password, no url_override
    assert cfg.url.startswith("sqlite+aiosqlite:///")
    assert cfg.sync_url.startswith("sqlite:///")


def test_postgres_url_override_normalises_async_and_sync_drivers():
    cfg = DatabaseConfig(url_override="postgresql://u:p@db:5432/axiom")
    # App (async) → asyncpg; Alembic (sync) → plain psycopg2 URL.
    assert cfg.url == "postgresql+asyncpg://u:p@db:5432/axiom"
    assert cfg.sync_url == "postgresql://u:p@db:5432/axiom"


def test_override_already_async_is_left_intact_and_desugared_for_sync():
    cfg = DatabaseConfig(url_override="postgresql+asyncpg://u:p@db/axiom")
    assert cfg.url == "postgresql+asyncpg://u:p@db/axiom"
    assert cfg.sync_url == "postgresql://u:p@db/axiom"


def test_sqlite_override_normalises_both_directions():
    cfg = DatabaseConfig(url_override="sqlite:///./data/x.db")
    assert cfg.url == "sqlite+aiosqlite:///./data/x.db"
    assert cfg.sync_url == "sqlite:///./data/x.db"


def test_override_wins_over_discrete_fields():
    cfg = DatabaseConfig(password="secret", url_override="postgresql://u:p@db/axiom")
    assert cfg.url == "postgresql+asyncpg://u:p@db/axiom"
