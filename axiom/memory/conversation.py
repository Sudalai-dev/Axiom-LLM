"""
OCIF Memory Manager — Layer 3.

Manages conversational memory, pulls recent turn records from the cache,
and executes the compaction algorithm (summarizing when turns > 20)
to maintain token count bounds (per Doc 6 Section 3.3).

Traces to:
  - Document 6 (LLD) Section 3.3: Memory Compaction
  - Document 9 (Database Design) Section 4.2: Session and Turn schemas
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.context import ConversationMemory, MemoryTurn
from memory.session_cache import SessionService
from storage.models import ConversationTurn, Session

logger = logging.getLogger("AxiomMemoryManager")


class MemoryManager:
    """
    Coordinates session turns loading, database persistence, and memory compaction.
    """

    def __init__(self, session_service: Optional[SessionService] = None) -> None:
        self.session_service = session_service or SessionService()

    async def get_conversation_memory(self, db: AsyncSession, session_id: str) -> ConversationMemory:
        """
        Loads session turns from Redis cache. If empty, falls back to database records,
        caches them, applies compaction, and returns the ConversationMemory DTO.
        """
        # 1. Try loading from Redis cache
        cached_turns = await self.session_service.get_recent_turns(session_id)
        
        turns_list = []
        if cached_turns:
            for t in cached_turns:
                turns_list.append(
                    MemoryTurn(
                        role=t.get("role", "user"),
                        content=t.get("content", ""),
                    )
                )
        else:
            # 2. Fall back to Database turns history
            try:
                result = await db.execute(
                    select(ConversationTurn)
                    .filter(ConversationTurn.session_id == session_id)
                    .order_by(ConversationTurn.created_at.asc())
                )
                db_turns = result.scalars().all()
                
                cache_payload = []
                for dt in db_turns:
                    turns_list.append(
                        MemoryTurn(
                            role=dt.role,
                            content=dt.content,
                            timestamp=dt.created_at
                        )
                    )
                    cache_payload.append({
                        "role": dt.role,
                        "content": dt.content,
                        "timestamp": int(dt.created_at.timestamp())
                    })
                
                # Update cache
                if cache_payload:
                    await self.session_service.save_recent_turns(session_id, cache_payload)
            except Exception as e:
                logger.error(f"Failed to fetch conversation turns from database: {e}")

        # 3. Apply compaction checks per Doc 6 Section 3.3
        total_turns = len(turns_list)
        is_compacted = False
        summary = None

        if total_turns > 20:
            logger.info(f"Turns count {total_turns} exceeds limit of 20. Executing memory compaction...")
            is_compacted = True
            
            # Simple rule-based compaction: keep initial system/user context (turns 0-2)
            # and append last 10 turns, replacing the middle with a semantic stub
            head = turns_list[:2]
            tail = turns_list[-10:]
            
            summary = (
                f"Conversation history compacted. Total turns: {total_turns}. "
                f"Initial request: '{turns_list[0].content[:60]}...' "
                f"Last user turn: '{turns_list[-2].content[:60]}...'" if total_turns >= 2 else ""
            )
            
            # Form the compacted turns list
            compacted_turns = head + [
                MemoryTurn(
                    role="system",
                    content=f"[SYSTEM NOTICE: {total_turns - 12} older turns have been compacted to conserve token budget.]"
                )
            ] + tail
            
            return ConversationMemory(
                turns=compacted_turns,
                is_compacted=is_compacted,
                summary=summary
            )

        return ConversationMemory(
            turns=turns_list,
            is_compacted=is_compacted,
            summary=summary
        )

    async def persist_turn(self, db: AsyncSession, session_id: str, tenant_id: str, role: str, content: str) -> None:
        """
        Persists a new turn to both cache and SQL database.
        """
        # Save to Redis Cache
        await self.session_service.append_session_turn(session_id, role, content)

        # Save to Database
        try:
            db_turn = ConversationTurn(
                session_id=session_id,
                tenant_id=tenant_id,
                role=role,
                content=content
            )
            db.add(db_turn)
            # Commit handled in db lifecycle manager
        except Exception as e:
            logger.error(f"Failed to persist conversation turn to database: {e}")
            raise
