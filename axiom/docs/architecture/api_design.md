# API Design & REST Endpoints: Axiom Platform

## 1. Authentication Endpoints

### 1.1 User Login
*   **Method**: `POST`
*   **Path**: `/api/v1/auth/login`
*   **Request Payload**:
    ```json
    {
      "username": "developer_name",
      "password": "secure_password"
    }
    ```
*   **Response Payload**:
    ```json
    {
      "access_token": "jwt_token_string",
      "token_type": "bearer",
      "expires_in": 3600
    }
    ```

---

## 2. Ingestion & Search Endpoints

### 2.1 Document Upload
*   **Method**: `POST`
*   **Path**: `/api/v1/upload`
*   **Headers**: `Authorization: Bearer <token>`
*   **Request (Multipart Form)**:
    *   `file`: Binary file data
    *   `project_id`: Integer
*   **Response**:
    ```json
    {
      "status": "SUCCESS",
      "file_id": 105,
      "file_name": "architecture.pdf",
      "pages_parsed": 12,
      "chunks_created": 48
    }
    ```

### 2.2 Semantic Search
*   **Method**: `POST`
*   **Path**: `/api/v1/search`
*   **Request Payload**:
    ```json
    {
      "query": "Kafka normalizer schema",
      "project_id": 1,
      "limit": 5
    }
    ```
*   **Response**:
    ```json
    [
      {
        "chunk_id": "uuid-1",
        "file_name": "architecture.md",
        "content": "The normalization layer standardizes all inputs...",
        "score": 0.89
      }
    ]
    ```

---

## 3. Cognitive Engine Endpoints

### 3.1 Cognitive Chat
*   **Method**: `POST`
*   **Path**: `/api/v1/chat`
*   **Request Payload**:
    ```json
    {
      "query": "Explain how the Capture Layer ingests MQTT data",
      "session_id": "session-uuid",
      "stream": false
    }
    ```
*   **Response**:
    ```json
    {
      "session_id": "session-uuid",
      "intent": "ArchitectureReview",
      "response_markdown": "## Axiom Cognitive Engine Output...",
      "artifacts": [
        {
          "type": "mermaid",
          "content": "graph TD..."
        }
      ]
    }
    ```

### 3.2 Diagram Generation
*   **Method**: `POST`
*   **Path**: `/api/v1/diagram`
*   **Request Payload**:
    ```json
    {
      "context": "Produce a mermaid diagram showing database nodes USES relations.",
      "project_id": 1
    }
    ```
*   **Response**:
    ```json
    {
      "diagram_type": "mermaid",
      "code": "graph TD\nService -->|uses| DB",
      "status": "VERIFIED"
    }
    ```
