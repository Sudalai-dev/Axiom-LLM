"""Alembic migration environment for AXIOM.

The database URL comes from AXIOM's own config (core.config.settings.database),
so migrations always target the same database the app uses: PostgreSQL when
AXIOM_DATABASE_URL is set, the local SQLite file otherwise. Importing
storage.models registers every table on Base.metadata for autogenerate.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.config import settings
from storage.database import Base
import storage.models  # noqa: F401 — side-effect: registers all tables on Base.metadata

config = context.config
# Inject AXIOM's resolved sync URL (psycopg2 for Postgres / sqlite for local).
config.set_main_option("sqlalchemy.url", settings.database.sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live DB connection (`alembic upgrade --sql`)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,   # safe ALTERs on SQLite
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Batch mode lets SQLite do table-rebuild ALTERs; harmless on Postgres.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
