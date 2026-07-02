# Database Design: Axiom Platform

## 1. Relational Database Schema (SQL)
The relational schema manages system access, user profiles, workspaces, session configurations, and operational logs.

```
+------------+        +---------------+        +--------------+
|   users    |1      *|   projects    |1      *|   sessions   |
|------------|--------|---------------|--------|--------------|
| id (PK)    |        | id (PK)       |        | id (PK)      |
| username   |        | name          |        | project_id(FK|
| role_id(FK)|        | owner_id (FK) |        | user_id (FK) |
+------------+        +---------------+        +--------------+
                                                      |1
                                                      |
                                                      |*
                                               +--------------+
                                               |   messages   |
                                               |--------------|
                                               | id (PK)      |
                                               | session_id(FK|
                                               | role         |
                                               | content      |
                                               +--------------+
```

### 1.1 Users & Authentication
*   `users` table:
    *   `id`: INTEGER (PK)
    *   `username`: VARCHAR(255) (UNIQUE)
    *   `hashed_password`: VARCHAR(255)
    *   `role_id`: INTEGER (FK to `roles.id`)
*   `roles` table:
    *   `id`: INTEGER (PK)
    *   `name`: VARCHAR(50) (e.g. 'Admin', 'Developer', 'Viewer')

### 1.2 Workspaces & Sessions
*   `projects` table:
    *   `id`: INTEGER (PK)
    *   `name`: VARCHAR(255)
    *   `owner_id`: INTEGER (FK to `users.id`)
*   `sessions` table:
    *   `id`: UUID (PK)
    *   `project_id`: INTEGER (FK to `projects.id`)
    *   `user_id`: INTEGER (FK to `users.id`)
    *   `created_at`: TIMESTAMP

### 1.3 Audit & Memory Logs
*   `audit_logs` table:
    *   `id`: BIGINT (PK)
    *   `user_id`: INTEGER
    *   `action`: VARCHAR(255)
    *   `timestamp`: TIMESTAMP
*   `memory_store` table:
    *   `id`: INTEGER (PK)
    *   `project_id`: INTEGER (FK)
    *   `user_id`: INTEGER (FK)
    *   `memory_key`: VARCHAR(255)
    *   `memory_data`: JSONB

---

## 2. Vector DB Schema
Vector store metadata format details:
*   **Collection Name**: `axiom_docs_collection`
*   **Payload Schema**:
    ```json
    {
      "id": "uuid",
      "vector": [0.12, 0.44, -0.09, "..."],
      "payload": {
        "document_id": "integer",
        "project_id": "integer",
        "file_name": "string",
        "chunk_index": "integer",
        "text": "string",
        "file_type": "string"
      }
    }
    ```

---

## 3. Graph Database Schema (Concepts & Relationships)
Used by the Knowledge Engine to represent relationships:
*   **Node Labels**:
    *   `(:Layer {name, depth})`
    *   `(:Protocol {name, type})`
    *   `(:Service {name, port})`
    *   `(:Database {name, engine})`
*   **Relationships**:
    *   `(:Service)-[:USES]->(:Database)`
    *   `(:Layer)-[:DEPENDS_ON]->(:Layer)`
    *   `(:Service)-[:COMMUNICATES_VIA {protocol}]->(:Service)`
