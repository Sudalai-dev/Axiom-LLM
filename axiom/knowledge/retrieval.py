"""
OCIF Vector Retriever Adapter — Layer 4.

Provides a unified interface for vector operations. Routes to Pinecone using
tenant namespaces in production (per Doc 11 Section 8) or falls back to
the local custom VectorEngine database for offline development.

Traces to:
  - Document 11 (RAG Design) Section 8: Performance (Pinecone namespace-per-tenant)
  - Document 9 (Database Design) Section 5: Vector Database Design
"""

import logging
from typing import List, Dict, Any, Optional

from core.config import settings
from knowledge.vector_store import VectorEngine

logger = logging.getLogger("AxiomVectorRetriever")


class VectorRetriever:
    """
    Adapter bridging local VectorEngine and Pinecone.
    """

    def __init__(self) -> None:
        self.provider = settings.vector_db.provider
        self.local_db = VectorEngine()
        self.pinecone_index = None

        if self.provider == "pinecone":
            if not settings.vector_db.api_key:
                logger.warning("Pinecone API key missing. Overriding provider to 'memory' fallback.")
                self.provider = "memory"
            else:
                try:
                    import pinecone
                    # Pinecone V2/V3 compatible initialization check
                    pc = pinecone.Pinecone(api_key=settings.vector_db.api_key)
                    self.pinecone_index = pc.Index(settings.vector_db.index_name)
                    logger.info(f"Connected to Pinecone Index: {settings.vector_db.index_name}")
                except Exception as e:
                    logger.error(f"Pinecone connection failure: {e}. Falling back to local memory vector store.")
                    self.provider = "memory"

    async def upsert_vector(
        self,
        chunk_id: str,
        vector: List[float],
        payload: Dict[str, Any],
        tenant_id: str
    ) -> None:
        """
        Inserts a single vector and payload metadata, isolated by tenant namespace.
        """
        if self.provider == "pinecone" and self.pinecone_index:
            try:
                # Upsert into tenant namespace
                self.pinecone_index.upsert(
                    vectors=[(chunk_id, vector, payload)],
                    namespace=tenant_id
                )
            except Exception as e:
                logger.error(f"Pinecone upsert failure: {e}. Attempting local database write.")
                # Write locally as fallback to avoid hard failure
                self.local_db.insert(chunk_id, vector, payload, project_id=hash(tenant_id) % 100000)
        else:
            # Map tenant_id string hash to the legacy local_db project_id (int)
            local_proj_id = hash(tenant_id) % 100000
            self.local_db.insert(chunk_id, vector, payload, project_id=local_proj_id)

    async def search_vectors(
        self,
        query_vector: List[float],
        tenant_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Queries top-K similar vector records.
        """
        if self.provider == "pinecone" and self.pinecone_index:
            try:
                response = self.pinecone_index.query(
                    vector=query_vector,
                    top_k=limit,
                    include_metadata=True,
                    namespace=tenant_id
                )
                results = []
                for match in response.get("matches", []):
                    results.append({
                        "id": match["id"],
                        "score": match["score"],
                        "payload": match.get("metadata", {})
                    })
                return results
            except Exception as e:
                logger.error(f"Pinecone query failure: {e}. Querying local memory store fallback.")
                local_proj_id = hash(tenant_id) % 100000
                return self.local_db.search(query_vector, project_id=local_proj_id, limit=limit)
        else:
            local_proj_id = hash(tenant_id) % 100000
            return self.local_db.search(query_vector, project_id=local_proj_id, limit=limit)
