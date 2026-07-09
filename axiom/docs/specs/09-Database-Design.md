# Database Design
## Enterprise AI Platform — OCIF

**Document 9 of 20** | **Traces to:** Documents 1–8
**Status:** Draft v1.0 — Pending Approval

---

## 1. Purpose

Defines the persistence architecture across PostgreSQL (system of record), Pinecone (vector store), and Redis (cache/session/memory), including schema definitions, tenancy strategy, and indexing approach.

---

## 2. Database Strategy Overview

| Store | Purpose | Layer(s) Served |
|---|---|---|
| PostgreSQL | Transactional data, audit logs, tool registry, policy config, user profiles | L2, L3, L4 (metadata), L5, L7, L8 |
| Pinecone | Vector embeddings for semantic search | L4 |
| Redis | Session state, short-term conversational memory, rate-limit counters, cache | L2, L3 |
| S3 | Raw document/object storage | L1, L4 |
| Kafka (log, not a DB but referenced) | Event backbone, audit replay source | L2, L7 |

---

## 3. Multi-Tenancy Model

Every table includes `tenant_id UUID NOT NULL` with **Row-Level Security (RLS)** policies enforced at the database level, in addition to application-level enforcement — defense-in-depth per Security Design (Document 13).

```sql
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON conversations
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

---

## 4. Core PostgreSQL Schema

### 4.1 Identity & Tenancy
```sql
CREATE TABLE tenants (
    tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    isolation_mode VARCHAR(20) DEFAULT 'shared',  -- shared | dedicated
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    external_idp_subject VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50) NOT NULL,
    department VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, external_idp_subject)
);
```

### 4.2 Conversation & Context (Layer 3)
```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    channel VARCHAR(50),
    started_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE conversation_turns (
    turn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(session_id),
    tenant_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(100),
    entities JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_turns_session ON conversation_turns(session_id, created_at);

CREATE TABLE long_term_memory (
    fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(user_id),
    fact TEXT NOT NULL,
    source_session_id UUID REFERENCES sessions(session_id),
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 4.3 Knowledge Metadata (Layer 4)
```sql
CREATE TABLE documents (
    doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    title VARCHAR(500),
    source_type VARCHAR(50),        -- upload | api | database | web
    storage_uri VARCHAR(1000),      -- S3 path
    ingestion_status VARCHAR(30) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE document_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL REFERENCES documents(doc_id),
    tenant_id UUID NOT NULL,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    pinecone_vector_id VARCHAR(255) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_chunks_tsv ON document_chunks USING GIN(tsv);
CREATE INDEX idx_chunks_doc ON document_chunks(doc_id);
```

### 4.4 Orchestration & Tools (Layer 5)
```sql
CREATE TABLE tools (
    tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(tenant_id),  -- NULL = global tool
    name VARCHAR(255) NOT NULL,
    description TEXT,
    input_schema JSONB NOT NULL,
    output_schema JSONB NOT NULL,
    risk_level VARCHAR(20) NOT NULL DEFAULT 'low',
    requires_approval BOOLEAN DEFAULT false,
    endpoint VARCHAR(1000) NOT NULL,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE agent_workflows (
    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    name VARCHAR(255),
    definition JSONB NOT NULL,      -- serialized agent graph
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 4.5 Decision & Action / Audit (Layer 7 — Immutable)
```sql
CREATE TABLE policies (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    name VARCHAR(255),
    rule_definition JSONB NOT NULL,  -- rules-as-code
    risk_threshold NUMERIC(4,3) DEFAULT 0.700,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    session_id UUID,
    actor VARCHAR(20) NOT NULL,       -- agent | human | system
    input_snapshot JSONB,
    retrieved_sources JSONB,
    model_used VARCHAR(100),
    policy_checks JSONB,
    risk_score NUMERIC(4,3),
    decision VARCHAR(30) NOT NULL,    -- auto_approved | hitl_approved | hitl_rejected | blocked
    action_taken JSONB,
    prev_event_hash CHAR(64),
    event_hash CHAR(64) NOT NULL,     -- SHA-256 chain for tamper-evidence
    created_at TIMESTAMPTZ DEFAULT now()
);
-- Append-only enforcement: no UPDATE/DELETE grants on this table for any application role.
CREATE INDEX idx_audit_tenant_time ON audit_events(tenant_id, created_at);

CREATE TABLE hitl_approvals (
    approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES audit_events(event_id),
    tenant_id UUID NOT NULL,
    assigned_to UUID REFERENCES users(user_id),
    status VARCHAR(20) DEFAULT 'pending', -- pending | approved | rejected
    resolved_at TIMESTAMPTZ,
    comments TEXT
);
```

### 4.6 Experience & Feedback (Layer 8)
```sql
CREATE TABLE feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    turn_id UUID REFERENCES conversation_turns(turn_id),
    rating SMALLINT,        -- -1, 0, +1
    correction_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE usage_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    metric_date DATE NOT NULL,
    token_count BIGINT DEFAULT 0,
    request_count BIGINT DEFAULT 0,
    automation_count BIGINT DEFAULT 0,
    cost_usd NUMERIC(12,4) DEFAULT 0,
    UNIQUE(tenant_id, metric_date)
);
```

---

## 5. Vector Database Design (Pinecone)

| Attribute | Design |
|---|---|
| Namespace Strategy | One namespace per `tenant_id` |
| Vector Dimension | Provider-dependent (e.g., 1536 for text-embedding-3-large); stored as tenant config |
| Metadata Payload | `{doc_id, chunk_id, tenant_id, section, source_type, created_at}` |
| Upsert Pattern | Batch upsert during ingestion pipeline; idempotent via `chunk_id` as vector ID |
| Query Pattern | Top-K similarity search (K configurable, default 8) filtered by namespace + metadata |

---

## 6. Redis Design

| Key Pattern | Purpose | TTL |
|---|---|---|
| `session:{session_id}` | Session state | 30 min sliding |
| `memory:{session_id}:turns` | Short-term conversation buffer | 30 min sliding |
| `ratelimit:{tenant_id}:{window}` | Token-bucket rate limiting | 1 min |
| `cache:retrieval:{hash(query)}` | RAG retrieval cache | 5 min |

---

## 7. Data Retention & Archival

| Data | Retention | Policy |
|---|---|---|
| `audit_events` | 7 years (configurable per tenant/regulation) | Cold storage archival to S3 Glacier after 1 year |
| `conversation_turns` | 90 days hot, then archived or purged per tenant policy | Configurable per compliance pack (Document 13) |
| `usage_metrics` | Indefinite (aggregate only) | — |

---

## 8. Indexing & Performance Notes

- All `tenant_id` columns are indexed as the leading column in composite indexes to support RLS-filtered query plans.
- `audit_events` partitioned by month (declarative partitioning) to sustain append-only write throughput at scale.
- `document_chunks.tsv` GIN index supports hybrid search's BM25 component (Document 10 — API Specification; Document 11 — RAG Design).

---

## 9. Traceability

Schema entities map directly to LLD data models (Document 6, Sections 3.2, 5.3, 6.4) and satisfy NFR-06 (Auditability) and NFR-08 (Multi-Tenancy) from the SRS.

---
*End of Database Design*
