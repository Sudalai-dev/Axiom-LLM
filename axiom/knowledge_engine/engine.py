import os
import re
from typing import Dict, Any, List

from axiom.parser_engine.parser import ParserEngine
from axiom.chunk_engine.chunker import ChunkEngine
from axiom.embedding_engine.embedder import EmbeddingEngine
from axiom.vector_engine.db import VectorEngine
from axiom.knowledge_graph.graph import KnowledgeGraph

class KnowledgeEngine:
    """
    KnowledgeEngine: Orchestrates the Axiom Knowledge Platform.
    Pipelines ingestion and executes hybrid Vector-Graph context query searches.
    """
    CONCEPT_KEYWORDS = {
        "Layer": [r"\blayer\b", r"\bcognitive\b", r"\bperception\b", r"\bcapture\b", r"\bnormalization\b"],
        "Protocol": [r"\bmqtt\b", r"\bkafka\b", r"\bgrpc\b", r"\bhttp\b", r"\btls\b"],
        "Service": [r"\bapi\b", r"\bfastapi\b", r"\bbackend\b", r"\bfrontend\b", r"\bweb\b"],
        "Database": [r"\bsqlite\b", r"\bpostgresql\b", r"\bvector\b", r"\bdatabase\b", r"\bqdrant\b"]
    }

    def __init__(self):
        self.parser = ParserEngine()
        self.chunker = ChunkEngine()
        self.embedder = EmbeddingEngine()
        self.vector_db = VectorEngine()
        self.graph_db = KnowledgeGraph()

    def ingest_document(self, filepath: str, project_id: int) -> Dict[str, Any]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        # 1. Parse document text
        text = self.parser.parse(filepath)
        
        # 2. Chunk text semantically
        chunks = self.chunker.split(text)
        
        # 3. Process each chunk
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{os.path.basename(filepath)}_c{idx}"
            
            # Generate embedding
            vector = self.embedder.embed(chunk.text)
            
            # Add to Vector Engine
            payload = {
                "file_name": os.path.basename(filepath),
                "text": chunk.text,
                "heading": chunk.metadata.get("heading", "General")
            }
            self.vector_db.insert(chunk_id, vector, payload, project_id)
            
            # 4. Extract Concepts and Relations for Knowledge Graph
            self._extract_graph_data(chunk.text)

        return {
            "status": "SUCCESS",
            "file_name": os.path.basename(filepath),
            "chunks_count": len(chunks)
        }

    def search_knowledge(self, query: str, project_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        # Compute query vector
        query_vector = self.embedder.embed(query)
        
        # Search vector DB
        vector_results = self.vector_db.search(query_vector, project_id, limit=limit)
        
        # Enhance results with Knowledge Graph relationship contexts
        enhanced_results = []
        for res in vector_results:
            text = res["payload"]["text"]
            
            # Find concepts mentioned in chunk and pull relationships
            relations_found = []
            for concept_type, patterns in self.CONCEPT_KEYWORDS.items():
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in set(matches):
                        # Query database for relationships of this concept
                        relations = self.graph_db.query_relations_from(match.capitalize())
                        for r in relations:
                            relations_found.append(f"{match.capitalize()} ({concept_type}) -> {r['relationship']} -> {r['target']} ({r['type']})")
            
            enhanced_res = {
                "id": res["id"],
                "score": res["score"],
                "text": text,
                "heading": res["payload"]["heading"],
                "source": res["payload"]["file_name"],
                "knowledge_graph_relationships": list(set(relations_found))[:5]  # Limit relation count
            }
            enhanced_results.append(enhanced_res)
            
        return enhanced_results

    def _extract_graph_data(self, text: str):
        """Identifies key technology terms and connects them in the Knowledge Graph."""
        found_concepts = []
        
        # Scan text for standard concepts
        for concept_type, patterns in self.CONCEPT_KEYWORDS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in set(matches):
                    name = match.capitalize()
                    self.graph_db.add_concept(name, concept_type)
                    found_concepts.append(name)
        
        # Add a sequential relationship between concepts in the same text chunk
        if len(found_concepts) >= 2:
            for i in range(len(found_concepts) - 1):
                self.graph_db.add_relationship(found_concepts[i], found_concepts[i+1], "CO_OCCURS_WITH")
