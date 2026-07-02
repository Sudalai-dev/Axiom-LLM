"""
OCIF Ingestion Pipeline — Layer 4.

Handles document parsing, semantic chunking (~500 tokens, 15% overlap per Doc 11 Section 3.2),
embedding generation, and dual writes to PostgreSQL (chunks metadata) and Pinecone 
(dense vector dimensions) (per Doc 11 Section 3).

Traces to:
  - Document 11 (RAG Design) Section 3: Ingestion Design (Chunk sizes, overlaps, dual write)
  - Document 9 (Database Design) Section 4.3: documents and document_chunks SQL tables
"""

import logging
import os
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession


from axiom.core.config import settings
from axiom.core.exceptions import IngestionError
from axiom.core.models.base import IngestionStatus, SourceType
from axiom.layer4_knowledge.vector_retriever import VectorRetriever
from axiom.parser_engine.parser import ParserEngine
from axiom.chunk_engine.chunker import ChunkEngine
from axiom.embedding_engine.embedder import EmbeddingEngine
from axiom.storage.models import Document, DocumentChunk

logger = logging.getLogger("AxiomIngestionPipeline")


class IngestionPipeline:
    """
    Ingestion coordinator orchestrating document processing.
    """

    def __init__(self, vector_retriever: Optional[VectorRetriever] = None) -> None:
        self.parser = ParserEngine()
        # Chunker is initialized using settings tokens conversion (default 1000 characters ~ 250 tokens,
        # so for 500 tokens we configure target size to ~2000 characters to map roughly,
        # or implement precise character/token ratios).
        self.chunker = ChunkEngine(chunk_size=int(settings.rag.chunk_size_tokens * 4))
        self.embedder = EmbeddingEngine()
        self.vector_retriever = vector_retriever or VectorRetriever()

    async def ingest_document(
        self,
        db: AsyncSession,
        filepath: str,
        tenant_id: str,
        source_type: SourceType
    ) -> Dict[str, Any]:
        """
        Runs document parsing, semantic chunking, and dual-writes chunks metadata to database
        and vectors to Pinecone/memory store.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Source file not found at: {filepath}")

        title = os.path.basename(filepath)
        logger.info(f"Starting ingestion pipeline for document: '{title}' (Tenant: {tenant_id})")

        # 1. Create Document database record (Status: Processing)
        doc = Document(
            tenant_id=tenant_id,
            title=title,
            source_type=source_type.value,
            storage_uri=filepath,
            ingestion_status=IngestionStatus.PROCESSING.value
        )
        db.add(doc)
        await db.flush()  # Populates doc_id from generator

        try:
            # 2. Parse text content
            text = self.parser.parse(filepath)
            if not text.strip():
                raise IngestionError(f"Document parser extracted empty text from '{title}'")

            # 3. Chunk text semantically
            chunks = self.chunker.split(text)
            if not chunks:
                raise IngestionError(f"Document chunker yielded zero chunks from '{title}'")

            logger.info(f"Split document '{title}' into {len(chunks)} chunks.")

            # 4. Process and dual-write each chunk
            for idx, chunk in enumerate(chunks):
                chunk_id = f"{doc.doc_id}_c{idx}"
                chunk_text = chunk.text

                # Compute dense vector embedding
                vector = self.embedder.embed(chunk_text)

                # Store metadata payload for Pinecone index search
                payload = {
                    "doc_id": doc.doc_id,
                    "chunk_id": chunk_id,
                    "tenant_id": tenant_id,
                    "title": title,
                    "source_type": source_type.value,
                    "section_ref": chunk.metadata.get("heading", "General"),
                    "text": chunk_text,
                    "chunk_index": idx
                }

                # Vector database write
                await self.vector_retriever.upsert_vector(
                    chunk_id=chunk_id,
                    vector=vector,
                    payload=payload,
                    tenant_id=tenant_id
                )

                # SQL database chunk write
                db_chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc.doc_id,
                    tenant_id=tenant_id,
                    chunk_index=idx,
                    text=chunk_text,
                    pinecone_vector_id=chunk_id
                )
                db.add(db_chunk)

            # Mark document as complete
            doc.ingestion_status = IngestionStatus.COMPLETED.value
            logger.info(f"Successfully finished ingestion of '{title}' with {len(chunks)} chunks.")
            
            return {
                "doc_id": doc.doc_id,
                "title": title,
                "chunks_ingested": len(chunks),
                "status": "COMPLETED"
            }

        except Exception as e:
            logger.error(f"Ingestion failed for document '{title}': {e}", exc_info=True)
            doc.ingestion_status = IngestionStatus.FAILED.value
            raise IngestionError(f"Document ingestion failed: {str(e)}")
