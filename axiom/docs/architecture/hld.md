# High-Level Design (HLD): Axiom Platform

## 1. System Topology
The Axiom system is composed of several decoupled services running entirely within a local containerized infrastructure.

```
       +---------------------------------------------+
       |             React User Interface            |
       +----------------------|----------------------+
                              | HTTP / WebSockets
       +----------------------v----------------------+
       |                FastAPI Backend              |
       +---|------------------|------------------|---+
           |                  |                  |
   +-------v-------+  +-------v-------+  +-------v-------+
   | Memory Engine |  |  Cognitive    |  | Ingestion     |
   | (PostgreSQL)  |  |  Pipeline     |  | Parser Engine |
   +---------------+  +-------|-------+  +-------|-------+
                              |                  |
                      +-------v-------+  +-------v-------+
                      | Local LLM     |  | Vector &      |
                      | Server (vLLM) |  | Graph DB      |
                      +---------------+  +---------------+
```

---

## 2. Core Architectural Components

### 2.1 Backend / API Gateway
*   **Technology**: Python FastAPI.
*   **Role**: Handles authentication, user management, and routes HTTP requests to specific engines.
*   **Database**: PostgreSQL for relational schemas (Users, Projects, Session memory).

### 2.2 Cognitive Engine (8-Layer Processor)
*   **Role**: Orchestrates input processing. It takes the query through parsing, context retrieval, term normalization, rule enrichment, context synthesis, LLM inference, artifact extraction, and visual response preparation.

### 2.3 Knowledge Engine
*   **Role**: Maintains the system context.
*   **Vector DB**: Qdrant/Chroma for semantic indexing.
*   **Graph DB**: Neo4j/SQLite for structured relationship mappings.

### 2.4 Execution Sandbox
*   **Role**: Spawns isolated Docker containers to run tests, validate schemas, and run code prescribed by the Cognitive Engine.

---

## 3. Data Processing Flows

### 3.1 Document Ingestion Flow
1.  **Upload**: The user uploads a file through `POST /upload`.
2.  **Parsing**: The file type is detected, and text, tables, and metadata are extracted by the custom Parser Engine.
3.  **Chunking**: Chunks are split on headings and paragraph structures, assigning document metadata to each chunk.
4.  **Embedding & Indexing**: The Embedding Engine generates dense vectors, inserting them into the Vector Database while concepts are populated into the Graph Database.

### 3.2 Closed-Loop Execution Flow
1.  **Request**: User query passes to the Cognitive Pipeline.
2.  **Prescription**: Code block artifacts are generated.
3.  **Sandbox Validation**: Code is run inside the Execution Sandbox.
4.  **Auto-Correction**: If a test or execution fails, error output is routed back to the Perception layer to regenerate a corrected code block.
