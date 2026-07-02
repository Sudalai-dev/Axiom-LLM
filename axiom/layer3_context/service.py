"""
OCIF Context Intelligence Service Wrapper — Layer 3.

Orchestrates intent classification, technology extraction, turn history retrieval,
profile checks, and heuristics enrichment to compile a context frame from any request.

Traces to:
  - Document 6 (LLD) Section 3: Context Intelligence Service
  - Document 7 (LLD) Section 4: Context Layer contract
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.models.base import RequestContext
from axiom.core.models.context import ContextFrame
from axiom.layer3_context.intent_classifier import IntentClassifier
from axiom.layer3_context.entity_extractor import EntityExtractor
from axiom.layer3_context.memory_manager import MemoryManager
from axiom.layer3_context.profile_service import ProfileService
from axiom.layer3_context.metadata_builder import MetadataBuilder

logger = logging.getLogger("AxiomContextService")


class ContextService:
    """
    Unified entrypoint for the Layer 3 Context Intelligence Service.
    """

    def __init__(self) -> None:
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.memory_manager = MemoryManager()
        self.profile_service = ProfileService()
        self.metadata_builder = MetadataBuilder()

    async def compile_context(
        self, 
        db: AsyncSession, 
        request_context: RequestContext, 
        query: str
    ) -> ContextFrame:
        """
        Runs context compilation.
        Steps:
          1. Classify query intent and check confidence thresholds.
          2. Parse named technology entities.
          3. Retrieve session conversation turns (compaction applied if turns > 20).
          4. Fetch and validate user profile from database.
          5. Assemble the outputs into a ContextFrame.
        """
        logger.info(f"Compiling context frame. Correlation ID: {request_context.correlation_id}")

        # 1. Intent Classification
        intent, confidence, requires_clarify = self.intent_classifier.classify(query)

        # 2. Entity Extraction
        entities = self.entity_extractor.extract(query)

        # 3. Conversation Memory
        session_id = request_context.session_id or "default-session"
        memory = await self.memory_manager.get_conversation_memory(db, session_id)

        # 4. User Profile validation
        profile_data = await self.profile_service.get_active_profile(db, request_context.user)

        # 5. Metadata Consolidation
        context_frame = self.metadata_builder.build_frame(
            request_context=request_context,
            intent=intent,
            intent_confidence=confidence,
            requires_clarification=requires_clarify,
            entities=entities,
            memory=memory,
            profile_data=profile_data
        )

        return context_frame

    async def record_user_turn(
        self,
        db: AsyncSession,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str
    ) -> None:
        """Helper to save a turn directly into conversation history cache and database."""
        await self.memory_manager.persist_turn(db, session_id, tenant_id, role, content)
