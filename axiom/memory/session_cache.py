"""
OCIF Session Service — Layer 2.

Handles conversation session caching, short-term session variables storage,
and sliding memory turn key updates in Redis (per Doc 9 Section 6).

Traces to:
  - Document 9 (Database Design) Section 6: Redis Design (session key patterns)
  - Document 6 (LLD) Section 2: Session Service
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional

from core.config import settings

logger = logging.getLogger("AxiomSessionService")


class SessionService:
    """
    Session Cache and Conversation State Manager.
    Uses Redis sliding cache windows, falling back to a local transient map for dev.
    """

    def __init__(self) -> None:
        self.redis_client = None
        self.redis_enabled = False
        
        # Local fallback maps
        self.local_sessions: Dict[str, Dict[str, Any]] = {}
        self.local_turns: Dict[str, List[Dict[str, Any]]] = {}

        if settings.redis.host:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=settings.redis.host,
                    port=settings.redis.port,
                    password=settings.redis.password,
                    decode_responses=True
                )
                self.redis_client.ping()
                self.redis_enabled = True
                logger.info(f"Redis active for Session Caching on: {settings.redis.host}:{settings.redis.port}")
            except Exception as e:
                logger.warning(f"Failed to bind Redis session cache client: {e}. Defaulting to local memory maps.")

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves session metadata from cache."""
        if self.redis_enabled and self.redis_client:
            try:
                key = f"session:{session_id}"
                data = self.redis_client.get(key)
                if data:
                    # Slide TTL forward on read
                    self.redis_client.expire(key, settings.redis.session_ttl_seconds)
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Redis get_session cache failure: {e}")
            return None
        else:
            return self.local_sessions.get(session_id)

    async def save_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Stores session metadata into cache with sliding expiration."""
        if self.redis_enabled and self.redis_client:
            try:
                key = f"session:{session_id}"
                self.redis_client.setex(
                    key,
                    settings.redis.session_ttl_seconds,
                    json.dumps(session_data)
                )
            except Exception as e:
                logger.error(f"Redis save_session cache failure: {e}")
        else:
            self.local_sessions[session_id] = session_data

    async def get_recent_turns(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Fetches sliding short-term conversation turns from memory cache.
        Key pattern per Doc 9 Section 6: memory:{session_id}:turns
        """
        if self.redis_enabled and self.redis_client:
            try:
                key = f"memory:{session_id}:turns"
                data = self.redis_client.get(key)
                if data:
                    # Slide memory window expiration on query
                    self.redis_client.expire(key, settings.redis.memory_ttl_seconds)
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Redis get_recent_turns memory failure: {e}")
            return []
        else:
            return self.local_turns.get(session_id, [])

    async def save_recent_turns(self, session_id: str, turns: List[Dict[str, Any]]) -> None:
        """
        Overwrites the sliding list of conversation turns in memory cache.
        Key pattern: memory:{session_id}:turns
        """
        if self.redis_enabled and self.redis_client:
            try:
                key = f"memory:{session_id}:turns"
                self.redis_client.setex(
                    key,
                    settings.redis.memory_ttl_seconds,
                    json.dumps(turns)
                )
            except Exception as e:
                logger.error(f"Redis save_recent_turns memory failure: {e}")
        else:
            self.local_turns[session_id] = turns

    async def append_session_turn(self, session_id: str, role: str, content: str) -> List[Dict[str, Any]]:
        """Appends a new message turn to the cache and returns the updated turns list."""
        turns = await self.get_recent_turns(session_id)
        new_turn = {
            "role": role,
            "content": content,
            "timestamp": int(time.time())
        }
        turns.append(new_turn)
        await self.save_recent_turns(session_id, turns)
        return turns
