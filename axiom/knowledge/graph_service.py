"""
OCIF Knowledge Graph Service — Layer 4.

Interacts with the local-first Graph Database (SQLite) to traverse entity-relationships,
merging graph paths into the EnrichedContext query context (per Doc 11 Section 6).

Traces to:
  - Document 11 (RAG Design) Section 6: Knowledge Graph Integration
  - Document 9 (Database Design) Section 2: Database Strategy (Graph DB wrapper)
"""

import logging
from typing import List, Dict, Any, Optional



from core.models.context import EntityInfo
from knowledge.graph import KnowledgeGraph

logger = logging.getLogger("AxiomKGService")


class KnowledgeGraphService:
    """
    Service running concept queries against local SQLite-backed KnowledgeGraph.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.graph = KnowledgeGraph(db_path=db_path)

    def retrieve_relationships(self, entities: List[EntityInfo]) -> List[str]:
        """
        Queries directed graph relationships originating from recognized technology entities.
        Formats paths to show entities relations.
        """
        relations_found = []
        for entity in entities:
            term = entity.term
            try:
                # Query sqlite concepts graph database
                records = self.graph.query_relations_from(term)
                for rec in records:
                    target = rec["target"]
                    relationship = rec["relationship"]
                    target_type = rec["type"]
                    
                    # Format as entity relationship triple string
                    relation_str = f"{term} ({entity.type}) -> {relationship} -> {target} ({target_type})"
                    relations_found.append(relation_str)
            except Exception as e:
                logger.error(f"Failed to query knowledge graph relations for entity '{term}': {e}")

        # Remove duplicate records and limit size
        unique_relations = list(set(relations_found))
        logger.debug(f"Retrieved {len(unique_relations)} relationships from Knowledge Graph.")
        return unique_relations[:10]
