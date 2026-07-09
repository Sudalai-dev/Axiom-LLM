# Design Specification: Axiom Knowledge Engine

## 1. Purpose
The **Axiom Knowledge Engine** acts as the central ingestion orchestrator and semantic correlation core for the Axiom AI Operating System. Its purpose is to ingest heterogeneous unstructured data, coordinate its structural parsing, segment it into semantic chunks, generate embeddings, index these embeddings in the vector database, and parse conceptual relations to construct a queryable Knowledge Graph.

---

## 2. Responsibilities
*   **Ingestion Orchestration**: Sequentially pipeline documents through parsing, chunking, embedding, and vector insertion.
*   **Concept & Relationship Extraction**: Identify key technical domains (e.g. Layers, Protocols, Services, Components, APIs) and write their dependencies to the Graph DB.
*   **Hybrid Query Resolution**: Combine dense vector search with graph-based relation search to return highly correlated context packages.

---

## 3. Inputs & Outputs
*   **Ingestion Input**: Raw file paths or uploaded byte streams (PDF, Markdown, YAML, etc.).
*   **Ingestion Output**: Status JSON indicating count of parsed pages, created chunks, embedded vectors, and relationship triples.
*   **Query Input**: Raw search string, project ID, and constraints.
*   **Query Output**: List of context matches containing text, metadata, and linked graph nodes.

---

## 4. Dependencies & Interfaces

### 4.1 System Dependencies
```
+-------------------------------------------------------------+
|                       Knowledge Engine                      |
+--|---------------|---------------|---------------|-------|--+
   |               |               |               |       |
+--v---+        +--v---+        +--v---+        +--v---+ +-v--+
|Parser|        |Chunk |        |Embed |        |Vector| |Graph|
|Engine|        |Engine|        |Engine|        |Engine| | DB  |
+------+        +------+        +------+        +------+ +----+
```

### 4.2 API Interfaces (Internal Python API)
*   `class KnowledgeEngine`:
    *   `def ingest_document(self, filepath: str, project_id: int) -> Dict[str, Any]`
    *   `def search_knowledge(self, query: str, project_id: int, limit: int = 5) -> List[Dict[str, Any]]`

---

## 5. Database Models (SQLite Relational & Graph Triples)
A local SQLite database houses relational tracking, while a separate triple store table represents the local Knowledge Graph relationships.

### SQL Relational Tracking
*   `knowledge_sources` table:
    *   `id`: INTEGER (PK)
    *   `project_id`: INTEGER (FK)
    *   `file_name`: VARCHAR
    *   `file_type`: VARCHAR
    *   `created_at`: TIMESTAMP
*   `knowledge_concepts` table (Graph Nodes):
    *   `id`: INTEGER (PK)
    *   `name`: VARCHAR (e.g., "NormalizationLayer", "MQTT")
    *   `type`: VARCHAR (e.g., "Layer", "Protocol", "Service")
*   `knowledge_relations` table (Graph Edges):
    *   `id`: INTEGER (PK)
    *   `source_concept_id`: INTEGER (FK)
    *   `target_concept_id`: INTEGER (FK)
    *   `relationship_type`: VARCHAR (e.g., "USES", "DEPENDS_ON")

---

## 6. Algorithms & Pseudocode
```python
def ingest_document(filepath, project_id):
    # 1. Parse document text
    raw_text = parser_engine.parse(filepath)
    
    # 2. Slice text into semantic blocks
    chunks = chunk_engine.split(raw_text)
    
    # 3. Generate vectors and insert into Vector Database
    for chunk in chunks:
        vector = embedding_engine.generate(chunk.text)
        vector_engine.insert(vector, chunk.metadata, project_id)
        
        # 4. Extract concepts and relationships
        concepts = concept_extractor.extract(chunk.text)
        for concept in concepts:
            db.save_concept(concept)
        relations = relationship_extractor.extract(chunk.text, concepts)
        for rel in relations:
            db.save_relationship(rel)
            
    return {"status": "INGESTED", "chunks": len(chunks)}
```

---

## 7. Performance & Complexity Analysis

### 7.1 Ingestion Complexity
*   **Parsing / Chunking**: $O(N)$ where $N$ is text length. Slicing loops linearly.
*   **Embedding Generation**: $O(M \cdot d)$ where $M$ is chunk count and $d$ is embedding dimensions. This is GPU-bound or CPU-latency-dependent.
*   **Vector Search & Indexing (HNSW)**: Search scales at $O(\log K)$ where $K$ is indexed vector count.
*   **Graph Traversal**: Relationships search scales at $O(E)$ where $E$ is count of matching edges.

### 7.2 Caching Strategy
*   Frequently queried concepts and vectors are cached in an in-memory dictionary. Cache hits bypass SQLite disk lookups, reducing query latencies to $<1\text{ms}$.

---

## 8. Logging, Metrics & Error Handling
*   **Logging**: Logs file parsing failures, vector DB timeouts, and database rollback actions.
*   **Metrics**: Measures page parsing speed (ms), embedding generation times (tokens/sec), and recall accuracy.
*   **Error Handling**: Catches parsing failures (corrupt binary file), database locks, and out-of-memory states, returning clean REST failure responses.

---

## 9. Future Improvements
*   Implement native PDF optical character recognition (OCR) parsing.
*   Add multi-GPU parallelization for dense embedding generation queues.
