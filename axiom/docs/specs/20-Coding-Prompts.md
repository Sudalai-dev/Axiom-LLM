# Coding Prompts (Module by Module)
## Enterprise AI Platform — OCIF

**Document 20 of 20** | **Traces to:** Documents 1–19
**Status:** Draft v1.0 — Pending Approval

---

## 1. Purpose

This document provides ready-to-use engineering prompts — for use with an AI coding assistant (e.g., Claude Code) or as sprint-ready tickets for human engineers — to implement each module defined in the LLD (Document 6). Each prompt is self-contained, references the authoritative design documents, and specifies acceptance criteria so that implementation stays consistent with the full architecture.

**How to use this document:** Execute prompts in the order given (they follow dependency order across OCIF layers). Each prompt assumes the previous modules exist. Do not skip the Layer 7 module — per Document 7, Section 12, no action-capable feature may ship without it.

---

## 2. Module 1 — Core Infrastructure Bootstrap

```
Prompt:
Set up the foundational infrastructure for the OCIF Enterprise AI Platform per Document 8
(System Architecture) and Document 18 (Deployment Guide):
- Terraform modules for AWS VPC, EKS cluster, RDS PostgreSQL (Multi-AZ), ElastiCache Redis,
  MSK Kafka, S3 buckets, and KMS keys, per Document 18 Section 3 folder structure.
- Kubernetes namespaces: perception-capture, context-knowledge, orchestration-cognition,
  decision-action, experience — per Document 8 Section 2.1.
- NetworkPolicies restricting east-west traffic to adjacent OCIF layers only, per Document 7
  Section 12 Invariant 1.
- GitHub Actions pipeline skeleton implementing the stages in Document 18 Section 2.1.

Acceptance Criteria:
- `terraform plan` succeeds with no errors across all modules.
- EKS cluster provisions with 5 namespaces and pod anti-affinity across AZs (Document 8 Section 5).
- CI pipeline runs lint/unit/build stages successfully on an empty scaffold commit.
```

---

## 3. Module 2 — Database Schema & Migrations

```
Prompt:
Implement the PostgreSQL schema defined in Document 9 (Database Design), Sections 4.1–4.6,
using a migration tool (e.g., Alembic). Include:
- Row-Level Security policies per Document 9 Section 3 for every tenant-scoped table.
- Append-only enforcement on `audit_events` (revoke UPDATE/DELETE from all application roles).
- Partitioning on `audit_events` by month per Document 9 Section 8.
- Seed script for a demo tenant, demo user, and default policy.

Acceptance Criteria:
- All tables from Document 9 exist with correct constraints, indexes, and RLS policies.
- Attempting UPDATE/DELETE on `audit_events` as the application role fails.
- Migration is reversible (down migration provided) except for the append-only guarantee.
```

---

## 4. Module 3 — Layer 2: API Gateway & Auth Service

```
Prompt:
Implement the API Gateway and Auth Service per Document 5 Section 4, Document 6 Section 2,
and Document 10 Section (external contracts). Requirements:
- FastAPI-based gateway validating OAuth2/JWT per Document 14 Section 3.
- Tenant resolution middleware (tenant_resolver.py per Document 6 Section 2.2).
- Token-bucket rate limiter per Document 10 Section 9 limits.
- Correlation ID injection/propagation on every request (Document 8 Section 6).
- Session Service backed by Redis per Document 9 Section 6 key patterns.

Acceptance Criteria:
- Requests without a valid JWT are rejected with 401 per RFC 7807 (Document 10 Section 8).
- tenant_id is correctly resolved and attached to request context for all downstream calls.
- Rate limits enforced per Document 10 Section 9 (standard vs enterprise tier).
- Unit tests cover auth_middleware.py, tenant_resolver.py, rate_limiter.py per Document 17 Section 3.1.
```

---

## 5. Module 4 — Layer 3: Context Intelligence Service

```
Prompt:
Implement the Context Intelligence Service per Document 6 Section 3 and Document 7 Section 4.
Requirements:
- intent_classifier.py, entity_extractor.py, memory_manager.py, profile_service.py,
  metadata_builder.py as specified in Document 6 Section 3.1.
- ConversationMemory and Turn data models exactly as defined in Document 6 Section 3.2.
- Memory compaction algorithm per Document 6 Section 3.3 (summarize when turns > 20).
- Output must conform to the ContextFrame contract in Document 7 Section 4.

Acceptance Criteria:
- Given a CaptureEvent, service returns a valid ContextFrame with intent, entities, memory,
  profile, and metadata populated.
- Low-confidence intent triggers a clarification flag rather than a silent guess
  (Document 7 Section 4 failure mode).
- Integration test validates the CaptureEvent -> ContextFrame contract boundary
  (Document 17 Section 3.2).
```

---

## 6. Module 5 — Layer 4: Knowledge Enrichment Service (RAG)

```
Prompt:
Implement the Knowledge Enrichment Service per Document 6 Section 4, Document 9 Sections 4.3
and 5, and Document 11 (RAG Design) in full.
Requirements:
- Ingestion pipeline: extraction, semantic chunking (~500 tokens, 15% overlap per Document 11
  Section 3.2), embedding generation, metadata tagging, dual write to Pinecone and Postgres.
- Hybrid search combining Pinecone vector search and Postgres BM25 (tsvector), fused via
  Reciprocal Rank Fusion per Document 11 Section 4.1 formula (k=60).
- No-grounding handling per Document 11 Section 4.3 — must return retrieval_confidence=0 and
  no_grounding_found=true rather than fabricating results.
- Citation attachment per Document 11 Section 5 schema.
- Knowledge Graph Service stub per Document 11 Section 6 (entity/relation query interface).

Acceptance Criteria:
- Uploading a document results in correctly chunked, embedded, and indexed content within
  the defined SLA.
- A query with no matching content returns no_grounding_found=true, never a hallucinated answer.
- Retrieval precision@8 >= 0.85 on the labeled evaluation set (Document 11 Section 9;
  Document 17 Section 3.4).
- Every returned chunk includes a valid, resolvable citation.
```

---

## 7. Module 6 — Layer 5: Orchestration Service (Agent Runtime)

```
Prompt:
Implement the Intelligence Orchestration Layer per Document 6 Section 5, Document 12
(Prompt Engineering Guide), and Document 13 (Agent Design) in full.
Requirements:
- LangGraph-based agent runtime implementing the state machine in Document 13 Section 4.
- Agent types: Planner, Retrieval, Tool-Use, Validation, Coordinator per Document 13 Section 2.
- Tool Registry integration per Document 9 Section 4.4 schema; tool invocation protocol
  strictly per Document 13 Section 5, including the sandboxed invocation interface.
- Prompt construction using the standard and task-specific templates in Document 12
  Sections 3-4, sourced from a versioned template store (Document 12 Section 6).
- CRITICAL INVARIANT: any tool call with side effects must terminate in a ProposalReady
  state consumed by Layer 7 — no direct execution of write/mutate/financial/irreversible
  actions from this layer, per Document 13 Section 5 and Document 7 Section 12.

Acceptance Criteria:
- Given an EnrichedContext, the service produces a valid OrchestrationPlan and ultimately
  a CognitionResult with a complete reasoning_trace (Document 13 Section 9 schema).
- Read-only tool calls execute directly; side-effecting tool calls never execute without
  passing through Layer 7 — verified by an explicit integration test that attempts to bypass
  this and confirms it is impossible.
- Max-step guard (default 15) prevents unbounded agent loops (Document 13 Section 8).
```

---

## 8. Module 7 — Layer 6: Cognition Service (LLM Gateway Abstraction)

```
Prompt:
Implement the Cognition Layer's LLM Gateway per Document 6 Section (Cognition), Document 10
Section 6, and Document 12 Section 8.
Requirements:
- Provider-agnostic abstraction supporting OpenAI, Claude, Gemini, and Llama, selected via
  the `provider` field ("openai"|"claude"|"gemini"|"llama"|"auto") per Document 10 Section 6.
- "auto" mode implements tenant-configurable cost/performance/availability-based routing.
- Automatic fallback to a secondary provider on timeout/error (FR-601, Document 18 Section 7).
- Confidence scoring and reasoning_trace generation per Document 4 FR-603/FR-604.
- Provider-specific formatting adapter applied AFTER the provider-agnostic template resolves,
  per Document 12 Section 8 (never before).

Acceptance Criteria:
- Same provider-agnostic prompt template produces valid, correctly-formatted requests to
  all four supported providers.
- Simulated provider outage triggers fallback within the latency budget (Document 8 Section 7,
  chaos test in Document 17 Section 3.6).
- Every response includes a confidence score and reasoning trace.
```

---

## 9. Module 8 — Layer 7: Decision & Action Service (META CORE)

```
Prompt:
Implement the Decision & Action Layer per Document 6 Section 6, Document 7 Section 8 (in full,
including the design invariants of Document 7 Section 12), Document 9 Section 4.5, and
Document 14 Section 6.
Requirements:
- policy_engine.py: deterministic rules-as-code evaluation (NOT an LLM call) per Document 14
  Section 6 — default-deny posture, fail-closed on any ambiguous/malformed input.
- hallucination_detector.py: confidence threshold + source-grounding cross-check per
  Document 7 Section 8.
- risk_scorer.py: composite risk score per Document 6 Section 6.3 formula, tenant-configurable
  weights and thresholds.
- hitl_queue.py: approval queue management per Document 9 Section 4.5 (hitl_approvals table).
- action_executor.py: sandboxed execution of approved actions only.
- audit_logger.py: append-only, cryptographically hash-chained audit events per Document 9
  Section 4.5 AuditEvent schema (prev_event_hash / event_hash chain).

Acceptance Criteria:
- Every proposed action results in exactly one AuditEvent record, regardless of outcome
  (approved, rejected, blocked).
- Audit hash chain is verifiable end-to-end; any tampering is detectable.
- Malformed or ambiguous policy inputs always result in "blocked", never in silent
  auto-approval (fail-closed test suite from Document 17 Section 3.5).
- No code path exists anywhere in the system that executes a side-effecting action without
  passing through this service first.
```

---

## 10. Module 9 — Layer 8: Experience Layer (Frontend)

```
Prompt:
Implement the Experience Layer frontend per Document 6 Section 7, Document 10 Sections 2 and
7, and Document 15 (UI/UX Design) in full, using React, Next.js, Tailwind CSS, and TypeScript.
Requirements:
- Chat interface with streaming (SSE) responses, confidence badges, citation chips, and
  "View decision trace" panel per Document 15 Sections 4.
- Action Proposal Card component per Document 15 Section 4, role-gated per Document 14
  Section 3.1 RBAC matrix.
- Approval Console per Document 15 Section 5.
- Dashboards per Document 15 Section 6, consuming Document 10 Section 2.3 endpoints.
- Admin Console (Policy Configuration, Tool Registry, User Management) per Document 15
  Sections 7 and Document 10 Section 7.
- Shared design system (Tailwind tokens, component library) per Document 15 Section 9.
- WCAG 2.1 AA accessibility compliance per Document 15 Section 2.

Acceptance Criteria:
- All screens in Document 15 Section 3 information architecture are implemented and navigable.
- Confidence and citations are always visible by default on chat responses (never hidden
  behind an extra click), per Document 15 Section 2 Principle 1.
- High-risk action proposals never render approve/reject controls for unauthorized roles
  (verified against Document 14 Section 3.1 RBAC matrix in component tests).
```

---

## 11. Module 10 — Cross-Cutting: Observability

```
Prompt:
Implement observability across all services per Document 8 Section 6 and Document 18 Section 8.
Requirements:
- Structured JSON logging with correlation_id on every log line.
- OpenTelemetry distributed tracing spanning L1 through L8 for every request.
- Prometheus metrics + Grafana dashboards for latency, error rate, and Layer 7 block rate.
- Alerting thresholds exactly as specified in Document 18 Section 8 table.

Acceptance Criteria:
- A single correlation_id can be used to reconstruct a full request trace across all 8 layers.
- Alerts fire correctly when synthetic tests exceed the warning/critical thresholds in
  Document 18 Section 8.
```

---

## 12. Module 11 — Cross-Cutting: Security Hardening

```
Prompt:
Implement the security controls specified in Document 14 across all services:
- mTLS between services via service mesh (Document 14 Section 3).
- RBAC enforcement matching Document 14 Section 3.1 exactly, at both API and row level.
- Prompt injection mitigations per Document 14 Section 5 (delimited context blocks,
  non-instructable retrieved content).
- Secrets management via AWS Secrets Manager/KMS — verify no secrets exist in code, config,
  or prompts (automated secret-scanning in CI per Document 18 Section 2.1).
- Compliance pack overlays (HIPAA, GDPR, SOC2, PCI-DSS) per Document 14 Section 7, applied
  as tenant configuration, not code forks.

Acceptance Criteria:
- Full RBAC matrix test suite (Document 17 Section 3.5) passes 100%.
- Adversarial prompt-injection test suite (Document 17 Section 3.4) achieves 100% block rate.
- Secret scan finds zero hardcoded credentials in the codebase.
```

---

## 13. Execution Order Summary

| Order | Module | Depends On |
|---|---|---|
| 1 | Core Infrastructure Bootstrap | — |
| 2 | Database Schema & Migrations | Module 1 |
| 3 | L2 API Gateway & Auth | Module 1, 2 |
| 4 | L3 Context Intelligence | Module 3 |
| 5 | L4 Knowledge Enrichment (RAG) | Module 2, 4 |
| 6 | L5 Orchestration (Agents) | Module 5 |
| 7 | L6 Cognition (LLM Gateway) | Module 3 (parallel-capable with 4-5) |
| 8 | L7 Decision & Action (META CORE) | Module 2, 6, 7 — **mandatory before any action-capable release** |
| 9 | L8 Experience (Frontend) | Module 3, 4, 8 |
| 10 | Observability | Parallel, from Module 1 onward |
| 11 | Security Hardening | Parallel, from Module 1 onward; final gate before production (Document 18 Section 2.1) |

---

## 14. Traceability

Every prompt in this document references the specific section of Documents 1–19 that governs its correct implementation, ensuring that AI-assisted or human engineering work remains consistent with the full architecture — fulfilling the project's development principle that "every future document must reference previous documents" (Document 1, Development Principles).

---
*End of Coding Prompts — End of 20-Document OCIF Enterprise AI Platform Documentation Set*
