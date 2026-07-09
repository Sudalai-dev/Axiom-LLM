# API Specification
## Enterprise AI Platform — OCIF

**Document 10 of 20** | **Traces to:** Documents 1–9
**Status:** Draft v1.0 — Pending Approval
**Style:** REST/JSON (OpenAPI 3.1 conventions), internal gRPC contracts noted where applicable

---

## 1. API Design Principles

- All external APIs are versioned: `/api/v1/...`
- All requests require `Authorization: Bearer <JWT>` and resolve `tenant_id` from token claims.
- All responses include `correlation_id` for traceability.
- Errors follow RFC 7807 (Problem Details) format.

---

## 2. Public API — Layer 8 (Experience)

### 2.1 Chat
```
POST /api/v1/chat/messages
Request:
{
  "session_id": "uuid | null",
  "message": "string",
  "attachments": [{"type": "document|image", "uri": "string"}]
}
Response: 200 OK (streamed via SSE if Accept: text/event-stream)
{
  "session_id": "uuid",
  "response": "string",
  "citations": [{"doc_id": "uuid", "title": "string", "excerpt_ref": "string"}],
  "confidence": 0.0-1.0,
  "decision_trace_id": "uuid"
}
```

### 2.2 Feedback
```
POST /api/v1/feedback
Request: { "turn_id": "uuid", "rating": -1|0|1, "correction_text": "string|null" }
Response: 201 Created
```

### 2.3 Dashboards
```
GET /api/v1/dashboard/usage?from=DATE&to=DATE
Response: { "requests": int, "tokens": int, "cost_usd": number, "automation_rate": number }
```

### 2.4 Approvals (HITL)
```
GET /api/v1/approvals?status=pending
Response: [{ "approval_id": "uuid", "event_id": "uuid", "summary": "string", "risk_score": number, "requested_at": "datetime" }]

POST /api/v1/approvals/{approval_id}/decision
Request: { "decision": "approved|rejected", "comments": "string" }
Response: 200 OK
```

---

## 3. Knowledge API — Layer 4

```
POST /api/v1/knowledge/documents
  (multipart upload) → 202 Accepted { "doc_id": "uuid", "ingestion_status": "pending" }

GET /api/v1/knowledge/documents/{doc_id}
  → { "doc_id", "title", "ingestion_status", "chunk_count" }

POST /api/v1/knowledge/search
Request: { "query": "string", "top_k": 8, "filters": {"source_type": "string"} }
Response: {
  "results": [
    {"chunk_id": "uuid", "text": "string", "score": number, "doc_id": "uuid", "citation": "string"}
  ]
}
```

---

## 4. Orchestration API — Layer 5

```
POST /api/v1/tools
Request: {
  "name": "string", "description": "string",
  "input_schema": {}, "output_schema": {},
  "risk_level": "low|medium|high", "requires_approval": boolean,
  "endpoint": "string"
}
Response: 201 Created { "tool_id": "uuid" }

GET /api/v1/tools
Response: [ ToolDefinition, ... ]

POST /api/v1/workflows
Request: { "name": "string", "definition": { /* agent graph JSON */ } }
Response: 201 Created { "workflow_id": "uuid" }

POST /api/v1/workflows/{workflow_id}/execute
Request: { "input": {} }
Response: 202 Accepted { "execution_id": "uuid", "status": "running" }

GET /api/v1/workflows/executions/{execution_id}
Response: { "status": "running|completed|blocked|failed", "trace": [ /* step-by-step */ ] }
```

---

## 5. Decision & Action API — Layer 7 (Internal, restricted)

```
POST /internal/v1/decision/evaluate
Request: {
  "session_id": "uuid",
  "proposed_action": {},
  "cognition_result": { "content": "string", "confidence": number, "model_used": "string" }
}
Response: {
  "decision": "auto_approved|hitl_approved|hitl_rejected|blocked",
  "risk_score": number,
  "policy_checks": [ {"rule": "string", "result": "pass|fail"} ],
  "audit_event_id": "uuid"
}

GET /internal/v1/audit/events?tenant_id=&from=&to=
Response: [ AuditEvent, ... ]   -- read-only, RBAC-restricted to compliance role
```

---

## 6. Cognition API — Layer 6 (Internal LLM Gateway Abstraction)

```
POST /internal/v1/llm/generate
Request: {
  "provider": "openai|claude|gemini|llama|auto",
  "prompt": "string",
  "context": {},
  "max_tokens": int,
  "temperature": number
}
Response: {
  "content": "string",
  "confidence": number,
  "reasoning_trace": "string",
  "provider_used": "string",
  "tokens_used": { "input": int, "output": int }
}
```
`provider: "auto"` invokes the Model Provider Abstraction's routing policy (cost/performance/availability-based selection per tenant configuration).

---

## 7. Admin/Configuration API

```
POST /api/v1/admin/policies
Request: { "name": "string", "rule_definition": {}, "risk_threshold": number }
Response: 201 Created { "policy_id": "uuid" }

POST /api/v1/admin/tenants
Request: { "name": "string", "industry": "string", "isolation_mode": "shared|dedicated" }
Response: 201 Created { "tenant_id": "uuid" }
```

---

## 8. Error Format (RFC 7807)

```json
{
  "type": "https://ocif-platform.dev/errors/policy-violation",
  "title": "Policy Violation",
  "status": 422,
  "detail": "Action blocked by policy rule 'no-unapproved-financial-transactions'",
  "correlation_id": "uuid"
}
```

---

## 9. Rate Limiting

| Tier | Limit |
|---|---|
| Standard | 60 requests/min per tenant |
| Enterprise | 600 requests/min per tenant (configurable) |
| Internal service-to-service | Not rate-limited; governed by circuit breakers instead |

---

## 10. Traceability

All endpoints implement functional requirements FR-101…FR-806 (Document 4 — SRS) and expose the service boundaries defined in the HLD (Document 5) and LLD (Document 6).

---
*End of API Specification*
