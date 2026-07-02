"""
OCIF Hybrid Search Engine — Layer 4.

Executes hybrid retrieval: combines semantic vector search (Pinecone) 
and lexical search (PostgreSQL BM25 Full-Text Search) fused via 
Reciprocal Rank Fusion (RRF) (per Doc 11 Section 4.1).

Traces to:
  - Document 11 (RAG Design) Section 4.1: Hybrid Search (RRF formula)
  - Document 9 (Database Design) Section 4.3: document_chunks schema (tsvector)
"""

import logging
import re
from typing import List, Dict, Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.config import settings
from axiom.layer4_knowledge.vector_retriever import VectorRetriever
from axiom.storage.models import DocumentChunk, Document

logger = logging.getLogger("AxiomHybridSearch")


class HybridSearch:
    """
    RRF-based Hybrid Lexical & Vector Search Engine.
    """

    def __init__(self, vector_retriever: Optional[VectorRetriever] = None) -> None:
        self.vector_retriever = vector_retriever or VectorRetriever()

    async def execute_search(
        self,
        db: AsyncSession,
        query: str,
        query_vector: List[float],
        tenant_id: str,
        limit: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Runs vector and lexical search, fuses them using RRF, and returns sorted chunks.
        """
        # 1. Execute Semantic Search (Pinecone/Memory)
        vector_results = await self.vector_retriever.search_vectors(
            query_vector=query_vector,
            tenant_id=tenant_id,
            limit=settings.rag.pre_fusion_top_k
        )

        # 2. Execute Lexical Search (Postgres FTS / local query fallback)
        lexical_results = await self._execute_lexical_search(db, query, tenant_id)

        # 3. Apply Reciprocal Rank Fusion (RRF)
        fused_results = self._reciprocal_rank_fusion(
            vector_results=vector_results,
            lexical_results=lexical_results,
            k=settings.rag.rrf_k
        )

        # Rank records by descending RRF score and apply top K limits
        sorted_results = sorted(fused_results.values(), key=lambda x: x["rrf_score"], reverse=True)
        return sorted_results[:limit]

    async def _execute_lexical_search(self, db: AsyncSession, query: str, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Queries text database. Uses postgres GIN FTS if dialect is PostgreSQL,
        falls back to standard SQL token parsing for SQLite.
        """
        results = []
        bind = db.bind
        dialect_name = bind.dialect.name if bind else "unknown"

        # Limit count for pre-fusion
        pre_limit = settings.rag.pre_fusion_top_k

        if dialect_name == "postgresql":
            # Native Postgres BM25 tsvector search
            try:
                # Query matches using @@ operator matching the materialized tsvector col 'tsv'
                sql = (
                    "SELECT c.chunk_id, c.text, c.chunk_index, c.doc_id, d.title, "
                    "ts_rank_cd(c.tsv, plainto_tsquery('english', :query)) as rank "
                    "FROM document_chunks c "
                    "JOIN documents d ON c.doc_id = d.doc_id "
                    "WHERE c.tenant_id = :tenant_id AND c.tsv @@ plainto_tsquery('english', :query) "
                    "ORDER BY rank DESC LIMIT :limit"
                )
                res = await db.execute(
                    text(sql),
                    {"query": query, "tenant_id": tenant_id, "limit": pre_limit}
                )
                rows = res.fetchall()
                for row in rows:
                    results.append({
                        "id": row[0],
                        "text": row[1],
                        "index": row[2],
                        "doc_id": row[3],
                        "title": row[4],
                        "lexical_score": float(row[5])
                    })
            except Exception as e:
                logger.error(f"PostgreSQL FTS error: {e}. Falling back to standard query.")
                dialect_name = "sqlite"

        if dialect_name != "postgresql":
            # Local SQLite fallback: parse query words and execute SQL matches
            words = [w.strip() for w in re.findall(r"\w+", query) if len(w) > 2]
            if not words:
                return []

            # Construct LIKE conditions
            conditions = " OR ".join(f"c.text LIKE :w{idx}" for idx in range(len(words)))
            sql = (
                f"SELECT c.chunk_id, c.text, c.chunk_index, c.doc_id, d.title "
                f"FROM document_chunks c "
                f"JOIN documents d ON c.doc_id = d.doc_id "
                f"WHERE c.tenant_id = :tenant_id AND ({conditions}) LIMIT :limit"
            )
            
            params = {"tenant_id": tenant_id, "limit": pre_limit}
            for idx, word in enumerate(words):
                params[f"w{idx}"] = f"%{word}%"

            try:
                res = await db.execute(text(sql), params)
                rows = res.fetchall()
                for row in rows:
                    # Calculate basic score based on matching word occurrences
                    matches_count = sum(1 for w in words if w.lower() in row[1].lower())
                    results.append({
                        "id": row[0],
                        "text": row[1],
                        "index": row[2],
                        "doc_id": row[3],
                        "title": row[4],
                        "lexical_score": float(matches_count)
                    })
            except Exception as e:
                logger.error(f"Local SQL lexical query failed: {e}")

        return results

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        lexical_results: List[Dict[str, Any]],
        k: int = 60
    ) -> Dict[str, Dict[str, Any]]:
        """
        Combines two ranked lists using Reciprocal Rank Fusion (RRF) algorithm:
        score(doc) = 1 / (k + rank_vector) + 1 / (k + rank_lexical)
        """
        scores: Dict[str, Dict[str, Any]] = {}

        # Process vector matches
        for rank, res in enumerate(vector_results):
            chunk_id = res["id"]
            if chunk_id not in scores:
                scores[chunk_id] = {
                    "id": chunk_id,
                    "text": res["payload"].get("text", ""),
                    "index": res["payload"].get("chunk_index", 0),
                    "doc_id": res["payload"].get("doc_id", ""),
                    "title": res["payload"].get("title", "Unknown"),
                    "source_type": res["payload"].get("source_type", "upload"),
                    "section_ref": res["payload"].get("section_ref", "General"),
                    "rrf_score": 0.0,
                    "metadata": res["payload"]
                }
            # rank is 0-indexed, add 1 for rank position
            scores[chunk_id]["rrf_score"] += 1.0 / (k + (rank + 1))

        # Process lexical matches
        for rank, res in enumerate(lexical_results):
            chunk_id = res["id"]
            if chunk_id not in scores:
                scores[chunk_id] = {
                    "id": chunk_id,
                    "text": res["text"],
                    "index": res["index"],
                    "doc_id": res["doc_id"],
                    "title": res["title"],
                    "source_type": "upload",  # default
                    "section_ref": "General",
                    "rrf_score": 0.0,
                    "metadata": {}
                }
            scores[chunk_id]["rrf_score"] += 1.0 / (k + (rank + 1))

        return scores
