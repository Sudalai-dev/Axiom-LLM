"""
Local-dev bootstrap seeding — admin user, policy, tool, and startup ingestion
of root-level markdown documents into the knowledge base.

Production deployments replace this with real migrations (Alembic); this exists
purely so a freshly cloned repo (or a fresh Docker container) is immediately
usable.
"""

import glob
import json
import logging
import os
from pathlib import Path

from sqlalchemy import delete, select

from api.routes.deps import SEED_USER_ID, SEED_USERNAME, knowledge_service
from core.config import settings
from core.models.base import IngestionStatus
from core.security import hash_password
from storage.database import AsyncSessionLocal, async_engine
from storage.models import (
    Base, Document, DocumentChunk, Policy, Tool, User,
)

logger = logging.getLogger("AxiomSeed")


async def ensure_seed_data() -> None:
    """Creates the admin user, default policy, tool, and bootstraps vector documents."""
    async with async_engine.begin() as conn:
        # Create tables if missing (dev convenience — production uses migrations)
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_schema_columns(conn)

    async with AsyncSessionLocal() as db:
        await _seed_admin(db)
        await _seed_default_policy(db)
        await _seed_default_tool(db)
        await _bootstrap_knowledge_base(db)


async def _ensure_schema_columns(conn) -> None:
    """Adds columns introduced after the initial release to an existing SQLite DB.

    ``Base.metadata.create_all`` creates missing tables but never ALTERs an
    existing one, so a database seeded before the freemium layer existed would
    be missing ``users.hashed_password``. This lightweight, idempotent
    migration closes that gap for local/dev SQLite; production uses real
    migrations (Alembic) and skips this.
    """
    if "sqlite" not in str(async_engine.url):
        return
    result = await conn.exec_driver_sql("PRAGMA table_info(users)")
    columns = {row[1] for row in result.fetchall()}
    if "hashed_password" not in columns:
        await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255)")
        logger.info("Migrated users table: added hashed_password column.")


async def _seed_admin(db) -> None:
    admin_hash = hash_password(settings.bootstrap.admin_password)

    existing = (await db.execute(
        select(User).filter(User.user_id == SEED_USER_ID)
    )).scalars().first()

    if existing:
        # Backfill the password for admins seeded before the auth rework so the
        # account remains usable after upgrading. (Idempotent: only sets it once.)
        if not existing.hashed_password:
            existing.hashed_password = admin_hash
            await db.commit()
            logger.info("Backfilled admin password hash.")
        return

    db.add(User(
        user_id=SEED_USER_ID,
        external_idp_subject=SEED_USERNAME,
        email="admin@axiom.local",
        role="platform_admin",
        department="Engineering",
        hashed_password=admin_hash,
    ))
    await db.commit()
    logger.info("Seeded admin user.")


async def _seed_default_policy(db) -> None:
    policy_name = "default-financial-limits-policy"
    existing = (await db.execute(
        select(Policy).filter(Policy.user_id == SEED_USER_ID, Policy.name == policy_name)
    )).scalars().first()
    if existing:
        return

    rule_def = {"rules": [{"field": "amount", "operator": "lte", "value": 500.0, "effect": "allow"}]}
    db.add(Policy(
        user_id=SEED_USER_ID,
        name=policy_name,
        rule_definition=json.dumps(rule_def),
        risk_threshold=0.7,
        is_active=True,
    ))
    await db.commit()
    logger.info(f"Seeded policy: {policy_name}")


async def _seed_default_tool(db) -> None:
    existing = (await db.execute(
        select(Tool).filter(Tool.user_id == SEED_USER_ID, Tool.name == "code_generator_tool")
    )).scalars().first()
    if existing:
        return

    input_schema = {"type": "object", "properties": {"language": {"type": "string"}, "framework": {"type": "string"}}, "required": ["language"]}
    output_schema = {"type": "object", "properties": {"status": {"type": "string"}, "content": {"type": "string"}}}
    db.add(Tool(
        user_id=SEED_USER_ID,
        name="code_generator_tool",
        description="Generates standard code templates for developer sessions",
        input_schema=json.dumps(input_schema),
        output_schema=json.dumps(output_schema),
        risk_level="low",
        requires_approval=False,
        endpoint="local",
        is_active=True,
    ))
    await db.commit()
    logger.info("Seeded default tool.")


async def _bootstrap_knowledge_base(db) -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    md_files = [
        f for f in glob.glob(str(project_root / "*.md"))
        if os.path.basename(f).upper() != "CLAUDE.MD"
    ] + glob.glob(str(project_root / "docs" / "**" / "*.md"), recursive=True)
    logger.info(f"Bootstrapping vector knowledge base. Found {len(md_files)} markdown documents.")

    for filepath in md_files:
        title = os.path.basename(filepath)

        doc_query = await db.execute(
            select(Document).filter(Document.title == title, Document.user_id == SEED_USER_ID)
        )
        existing_doc = doc_query.scalars().first()

        if existing_doc and existing_doc.ingestion_status == IngestionStatus.COMPLETED.value:
            chunks_query = await db.execute(
                select(DocumentChunk).filter(DocumentChunk.doc_id == existing_doc.doc_id)
            )
            for chunk in chunks_query.scalars().all():
                vector = knowledge_service.embedder.embed(chunk.text)
                payload = {
                    "doc_id": existing_doc.doc_id,
                    "chunk_id": chunk.chunk_id,
                    "user_id": SEED_USER_ID,
                    "title": title,
                    "source_type": existing_doc.source_type,
                    "section_ref": "General",
                    "text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                }
                await knowledge_service.vector_retriever.upsert_vector(
                    chunk_id=chunk.chunk_id, vector=vector, payload=payload, user_id=SEED_USER_ID
                )
        else:
            if existing_doc:
                await db.execute(delete(Document).filter(Document.doc_id == existing_doc.doc_id))
                await db.commit()
            try:
                await knowledge_service.ingest(db=db, filepath=filepath, user_id=SEED_USER_ID, source_type="upload")
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to ingest document '{title}': {e}")
                await db.rollback()
