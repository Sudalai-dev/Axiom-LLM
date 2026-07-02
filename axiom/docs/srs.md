# Software Requirements Specification (SRS): Axiom Platform

## 1. System Scope & Objective
The Axiom Platform is a local, self-hosted Engineering AI Operating System. Its primary objective is to enable developers, architects, and DevOps engineers to parse documentation, query codebase structures, generate validated scripts, and orchestrate systems without transmitting data outside the organization's infrastructure.

---

## 2. Functional Requirements

### 2.1 Backend API & Infrastructure (Phase 2)
*   **FR-1.1: Authentication & RBAC**: The system must enforce JSON Web Token (JWT) authentication and Role-Based Access Control (RBAC) supporting Administrator, Developer, and Viewer roles.
*   **FR-1.2: Project Management**: Users must be able to create, read, update, and delete (CRUD) projects to isolate codebase contexts.
*   **FR-1.3: REST Endpoints**: The backend must expose REST endpoints including:
    *   `POST /chat`: Routes requests through the 8-layer cognitive pipeline.
    *   `POST /upload`: Ingests documentation and codebase files.
    *   `POST /projects`: Manages project context groups.
    *   `POST /search`: Queries vector and graph indexes.

### 2.2 Data Ingestion & Parsing (Phases 4-7)
*   **FR-2.1: Multiformat Parsing**: The system must parse PDF, Word, Excel, PowerPoint, Markdown, JSON, and YAML files locally.
*   **FR-2.2: Concept Chunking**: The custom chunk engine must parse headings, paragraphs, and tables, attaching structural metadata before indexing.
*   **FR-2.3: Vector Indexing**: The system must embed chunks using local models and support similarity searches, updates, and indexing.

### 2.3 Cognitive & Knowledge Engine (Phases 8-11)
*   **FR-3.1: Knowledge Graph Mapping**: The system must extract entities (Layer, Protocol, Sensor, Service) and map relationships (connects_to, uses) into a Graph DB.
*   **FR-3.2: 8-Layer Execution**: All user queries must pass sequentially through the 8 layers: Perception, Capture, Normalization, Enrichment, Synthesis, Cognition, Prescription, Experience.

### 2.4 Agents & Sandboxed Execution (Phases 13-15)
*   **FR-4.1: Autonomous Agents**: The system must orchestrate specialized agents (Architecture, Backend, IoT, DevOps) to solve multi-step planning tasks.
*   **FR-4.2: Closed-Loop Sandbox**: Prescribed code must be validated, compiled, and run inside an isolated runtime container (e.g. Docker), returning execution telemetry to the Perception layer for auto-correction.

---

## 3. Non-Functional Requirements

### 3.1 Security & Privacy
*   **NFR-1.1: Strict Data Isolation**: No data, prompts, or telemetry may leave the local deployment boundary.
*   **NFR-1.2: Encryption-at-Rest/Transit**: Stored database files, vector records, and memory configurations must be encrypted using AES-256.

### 3.2 Performance & Scalability
*   **NFR-2.1: Inference Throughput**: Local LLM inference must exceed 30 tokens/sec on target hardware (minimum RTX 3090/4090).
*   **NFR-2.2: Ingestion Latency**: The parser and chunk engine must index text documents at a rate of less than 1.5 seconds per page.
