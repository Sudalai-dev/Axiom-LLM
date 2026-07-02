"""
OCIF Knowledge Enrichment Service Wrapper — Layer 4.

Coordinates embedding generation, hybrid lexical-vector search, RRF rank fusion,
no-grounding threshold checks (per Doc 11 Section 4.3), citation builders, and
Knowledge Graph relationship context pulls to produce the EnrichedContext frame.

Traces to:
  - Document 7 (LLD) Section 5: Knowledge Layer contract
  - Document 11 (RAG Design) Section 4.3: No-Grounding Handling
  - Document 11 (RAG Design) Section 6: Knowledge Graph Integration
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.config import settings
from axiom.core.models.base import RequestContext
from axiom.core.models.context import ContextFrame
from axiom.core.models.knowledge import EnrichedContext, GroundedChunk
from axiom.embedding_engine.embedder import EmbeddingEngine
from axiom.layer4_knowledge.vector_retriever import VectorRetriever
from axiom.layer4_knowledge.hybrid_search import HybridSearch
from axiom.layer4_knowledge.citation_builder import CitationBuilder
from axiom.layer4_knowledge.kg_service import KnowledgeGraphService
from axiom.layer4_knowledge.ingestion_pipeline import IngestionPipeline

logger = logging.getLogger("AxiomKnowledgeService")


class KnowledgeService:
    """
    Unified entrypoint for the Layer 4 Knowledge Enrichment (RAG) Service.
    """

    def __init__(self) -> None:
        self.embedder = EmbeddingEngine()
        self.vector_retriever = VectorRetriever()
        self.hybrid_search = HybridSearch(vector_retriever=self.vector_retriever)
        self.citation_builder = CitationBuilder()
        self.kg_service = KnowledgeGraphService()
        self.ingestion_pipeline = IngestionPipeline(vector_retriever=self.vector_retriever)

    async def enrich_context(self, db: AsyncSession, context_frame: ContextFrame) -> EnrichedContext:
        """
        Enriches a ContextFrame with grounded knowledge chunks and graph relationships.
        
        Enforces no-grounding logic based on vector similarity thresholds.
        """
        request_context = context_frame.request_context
        query = context_frame.request_context.metadata.get("query") or context_frame.request_context.session_id
        # Fallback if query not in request metadata
        if not query:
            # Reconstruct query terms or fetch from history
            if context_frame.memory.turns:
                query = context_frame.memory.turns[-1].content
            else:
                query = "general"

        logger.info(f"Enriching context frame for tenant: {request_context.tenant.tenant_id}")

        # 1. Compute query vector embedding
        query_vector = self.embedder.embed(query)

        # 2. Check raw vector cosine similarity scores to identify grounding presence
        # Per Doc 11 Section 4.3: Cosine threshold validation
        raw_vector_matches = await self.vector_retriever.search_vectors(
            query_vector=query_vector,
            tenant_id=request_context.tenant.tenant_id,
            limit=1
        )
        
        top_cosine_score = 0.0
        if raw_vector_matches:
            top_cosine_score = raw_vector_matches[0]["score"]

        threshold = settings.vector_db.similarity_threshold
        no_grounding = False
        retrieval_confidence = 0.0

        if top_cosine_score < threshold:
            logger.warning(
                f"Top semantic matching score ({top_cosine_score:.4f}) is below "
                f"similarity threshold ({threshold:.2f}). Triggering No-Grounding logic."
            )
            no_grounding = True
        else:
            retrieval_confidence = float(top_cosine_score)

        # 3. Perform RRF Hybrid Search
        fused_chunks = []
        if not no_grounding:
            raw_fused = await self.hybrid_search.execute_search(
                db=db,
                query=query,
                query_vector=query_vector,
                tenant_id=request_context.tenant.tenant_id,
                limit=settings.rag.post_fusion_top_k
            )
            # Map search dicts to GroundedChunk Pydantic DTOs
            fused_chunks = self.citation_builder.build_citations(raw_fused)

        # 4. Ingest entity-relationship paths from Knowledge Graph
        kg_relations = self.kg_service.retrieve_relationships(context_frame.entities)

        # 5. Assemble and return the EnrichedContext payload
        enriched = EnrichedContext(
            retrieval_confidence=retrieval_confidence,
            no_grounding_found=no_grounding,
            retrieved_chunks=fused_chunks,
            kg_relations=kg_relations,
            context_frame=context_frame,
            request_context=request_context
        )

        return enriched

    async def ingest(
        self,
        db: AsyncSession,
        filepath: str,
        tenant_id: str,
        source_type: str = "upload"
    ) -> Dict[str, Any]:
        """Exposes doc ingestion utility to outer gateway API layers."""
        from axiom.core.models.base import SourceType
        try:
            source_enum = SourceType(source_type)
        except ValueError:
            source_enum = SourceType.UPLOAD

        return await self.ingestion_pipeline.ingest_document(db, filepath, tenant_id, source_enum)
