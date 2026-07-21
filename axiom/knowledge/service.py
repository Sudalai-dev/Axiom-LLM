"""
Knowledge Service — unified entrypoint for the knowledge layer.

Coordinates document ingestion (parse -> chunk -> embed -> vector store) and
exposes the embedder + vector retriever that back the OCIF Knowledge Engine's
retriever bridge.
"""

import logging
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.embedder import EmbeddingEngine
from knowledge.ingestion import IngestionPipeline
from knowledge.retrieval import VectorRetriever

logger = logging.getLogger("AxiomKnowledgeService")


class KnowledgeService:
    """Facade over the knowledge infrastructure (RAG backbone)."""

    def __init__(self) -> None:
        self.embedder = EmbeddingEngine()
        self.vector_retriever = VectorRetriever()
        self.ingestion_pipeline = IngestionPipeline(vector_retriever=self.vector_retriever)

    async def ingest(
        self,
        db: AsyncSession,
        filepath: str,
        user_id: str,
        source_type: str = "upload"
    ) -> Dict[str, Any]:
        """Ingests a document into the user's knowledge base."""
        from core.models.base import SourceType
        try:
            source_enum = SourceType(source_type)
        except ValueError:
            source_enum = SourceType.UPLOAD

        return await self.ingestion_pipeline.ingest_document(db, filepath, user_id, source_enum)
