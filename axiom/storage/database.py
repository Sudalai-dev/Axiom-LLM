"""
OCIF Database Connections — Session Lifecycle Management.

Configures connection engines and session pools for PostgreSQL and SQLite.
Supports asynchronous sessions for FastAPI endpoints (Layer 2) and synchronous
fallback engines for local administration and migrations.

Traces to:
  - Document 9 (Database Design) Section 2: Database Strategy
  - Document 8 (System Architecture) Section 2.2: Deployment Topology
"""

import logging
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from core.config import settings

logger = logging.getLogger("AxiomDatabase")

# Setup declarative base
Base = declarative_base()

# Base Database URLs from config
db_url = settings.database.url
sync_db_url = settings.database.sync_url

logger.info(f"Initializing database engines. Async URL: {db_url.split('@')[-1] if '@' in db_url else db_url}")

# Async engine & session pool for FastAPI endpoints
async_engine_kwargs = {}
if "sqlite" in db_url:
    async_engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    async_engine_kwargs["pool_size"] = settings.database.pool_size
    async_engine_kwargs["max_overflow"] = settings.database.max_overflow

async_engine = create_async_engine(
    db_url,
    **async_engine_kwargs
)


AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Synchronous engine & session pool for background tasks, tests, or migrations
sync_engine = create_engine(
    sync_db_url,
    connect_args={"check_same_thread": False} if "sqlite" in sync_db_url else {},
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injector for FastAPI routes.
    Yields an active asynchronous transaction session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
