# System Architecture
## Enterprise AI Platform — OCIF

**Document 8 of 20** | **Traces to:** Documents 1–7
**Status:** Draft v1.0 — Pending Approval

---

## 1. Purpose

This document consolidates the full system architecture — combining the HLD (Document 5), LLD (Document 6), and OCIF Detailed Specification (Document 7) — into a single architectural reference with complete diagrams, covering component, deployment, network, and data-flow views.

---

## 2. Architecture Views

### 2.1 Component View

```mermaid
flowchart TB
    subgraph Client Layer
        WEB[Web App - Next.js]
        MOBILE[Mobile - Future]
        API_CLIENT[External API Clients]
    end

    subgraph Edge
        CDN[CloudFront CDN]
        WAF[AWS WAF]
        ALB[Application Load Balancer]
    end

    subgraph L2["L2 - Gateway/Capture"]
        GW[API Gateway]
        AUTH[Auth Service]
        SESS[Session Service]
    end

    subgraph L3["L3 - Context Intelligence"]
        INTENT[Intent Service]
        NER[Entity Extraction]
        MEM[Memory Service]
        PROFILE[Profile Service]
    end

    subgraph L4["L4 - Knowledge Enrichment"]
        INGEST[Ingestion Service]
        RETRIEVE[Retrieval Service]
        KG[Knowledge Graph Service]
    end

    subgraph L5["L5 - Orchestration"]
        PROMPT[Prompt Builder]
        AGENTS[Agent Orchestrator]
        TOOLS[Tool Registry]
    end

    subgraph L6["L6 - Cognition"]
        LLMGW[LLM Gateway/Abstraction]
        EXPLAIN[Explainability Service]
    end

    subgraph L7["L7 - Decision and Action META CORE"]
        POLICY[Policy Engine]
        HALLU[Hallucination Detector]
        HITL[HITL Queue]
        EXEC[Action Executor]
        AUDIT[Audit Logger]
    end

    subgraph L8["L8 - Experience"]
        CHATUI[Chat/Copilot UI]
        DASH[Dashboards]
        NOTIFY[Notification Service]
        PUBAPI[Public API]
    end

    WEB & MOBILE & API_CLIENT --> CDN --> WAF --> ALB --> GW
    GW --> AUTH --> SESS
    GW --> INTENT
    INTENT --> NER --> MEM --> PROFILE
    PROFILE --> INGEST
    INGEST --> RETRIEVE --> KG
    KG --> PROMPT
    PROMPT --> AGENTS --> TOOLS
    TOOLS --> LLMGW --> EXPLAIN
    EXPLAIN --> POLICY
    POLICY --> HALLU --> HITL --> EXEC --> AUDIT
    AUDIT --> CHATUI & DASH & NOTIFY & PUBAPI
```

### 2.2 Network Architecture

```mermaid
flowchart TB
    subgraph VPC["AWS VPC"]
        subgraph Public["Public Subnets"]
            ALB2[ALB]
            NAT[NAT Gateway]
        end
        subgraph Private_App["Private Subnets - App Tier"]
            EKS2[EKS Node Groups per Namespace]
        end
        subgraph Private_Data["Private Subnets - Data Tier"]
            RDS2[(RDS PostgreSQL Multi-AZ)]
            REDIS2[(ElastiCache Redis)]
            MSK2[(MSK Kafka)]
        end
    end
    Internet((Internet)) --> ALB2 --> EKS2
    EKS2 --> NAT --> Internet
    EKS2 --> RDS2
    EKS2 --> REDIS2
    EKS2 --> MSK2
    EKS2 -->|HTTPS egress, allow-listed| PineconeExt[Pinecone - External]
    EKS2 -->|HTTPS egress, allow-listed| LLMExt[LLM Providers - External]
```

### 2.3 Data Flow View

Data flows strictly follow the OCIF layer contract sequence defined in Document 7, Section 11 — no layer-skipping is permitted at the network or service-mesh level (enforced via Kubernetes NetworkPolicies restricting east-west traffic to adjacent layers plus the shared data tier).

---

## 3. Service Mesh & Communication Patterns

| Pattern | Usage |
|---|---|
| Synchronous REST/gRPC | Request/response paths within a single user request (L2→L3→L4→L5→L6→L7→L8) |
| Asynchronous Kafka Events | Logging, audit propagation, feedback loops, ingestion pipeline processing |
| Service Mesh (Istio) | mTLS between services, traffic policy, retries/circuit breaking |

---

## 4. Multi-Tenancy Architecture

- **Tenant Isolation Model:** Shared infrastructure, logically isolated data (row-level security in PostgreSQL via `tenant_id`; Pinecone namespace-per-tenant).
- **Regulated Tenant Option:** Dedicated namespace/cluster deployment for tenants requiring physical isolation (e.g., healthcare, government) — configurable at onboarding.

```mermaid
flowchart LR
    T1[Tenant A Request] --> GW3[Shared API Gateway]
    T2[Tenant B Request] --> GW3
    GW3 --> RLS[Row-Level Security Enforcement]
    RLS --> PG[(Shared PostgreSQL, tenant_id partitioned)]
    RLS --> PC[(Pinecone, namespace per tenant)]
```

---

## 5. High Availability & Disaster Recovery

| Aspect | Design |
|---|---|
| Compute | Multi-AZ EKS node groups, pod anti-affinity across AZs |
| Database | RDS PostgreSQL Multi-AZ with automated failover |
| Cache | ElastiCache Redis with replica failover |
| Messaging | MSK Kafka with 3x replication across AZs |
| Backup | Automated daily RDS snapshots, point-in-time recovery, cross-region backup replication |
| DR Target | RPO ≤ 15 min, RTO ≤ 1 hour (per NFR-12) |

---

## 6. Observability Architecture

```mermaid
flowchart LR
    SVC[All Services] -->|structured logs| LOGS[CloudWatch/OpenSearch]
    SVC -->|traces| OTEL[OpenTelemetry Collector] --> TRACE[Distributed Tracing Backend]
    SVC -->|metrics| PROM[Prometheus] --> GRAF[Grafana Dashboards]
    LOGS & TRACE & PROM --> ALERT[Alertmanager / PagerDuty]
```

Every request carries a `correlation_id` from L2 through L8, enabling full trace reconstruction for both debugging and Layer 7 audit purposes.

---

## 7. Traceability

This document is the architectural reference implementation of the OCIF layer contracts (Document 7) and the requirements in the SRS (Document 4). Database schema detail follows in Document 9; API contracts in Document 10 *(renumbered — see Section 8 note)*.

> **Numbering note:** Per the requested document order, Database Design is Document 9 and API Specification is Document 10 in this set.

---
*End of System Architecture*
