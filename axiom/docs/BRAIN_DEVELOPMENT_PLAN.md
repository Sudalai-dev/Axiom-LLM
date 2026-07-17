# AXIOM Brain Development Plan

> Status: Phase 0 (teardown) + frontend rework executed. Phases 1–7 (the
> analytical brain) are the deferred roadmap below.

## Context

AXIOM is pivoting away from external agents. OpenCode (and the cloud LLM
providers) proved unreliable and, more importantly, unnecessary: the deterministic
`SolutionSynthesizer` already produces a complete solution + 8 diagrams with no
LLM. The direction is to make **AXIOM its own brain** — a self-contained,
deterministic, analytical engine grounded in the durable `ecosystem/` knowledge
platform (standards-with-sections, a deterministic rules engine, ontology,
failure modes, ranking, learning store).

The current deterministic path is a *template-filler*, not a brain: the whole
document is copied from **one of 19 frozen `IndustryPattern`s** keyed by a single
industry slug, several sections are identical across all industries, and the
knowledge platform is fed only into the (now-removed) LLM prompt. Turning that
into a real brain is the multi-phase roadmap below.

---

## Phase 0 — Teardown (DONE)

Remove OpenCode, billing, and the free-limit quota; make the deterministic brain
the sole path.

- **Deleted:** OpenCode provider, all cloud providers + model router + inference
  adapter, `ocif/diagram_brain.py` (validation relocated into
  `ocif/project_diagrams.py`), `core/entitlement.py`, `billing/`, billing/keys
  routes, and the freemium tests.
- **Unhooked LLM** from the reasoning engine, experience engine, and project-
  understanding classifier (rule-based only now).
- **Removed** the freemium gate/paywall/subscription/BYO-keys; **kept** real
  hashed-password auth, per-tenant rate limiting, and real usage metering +
  dashboard.

## Phase 0b — Frontend rework (DONE)

Removed the freemium UI (plan pill, account/billing + paywall modals, keys, 402
handling) with no dangling references; fixed backend-connection fragilities
(configurable `API_BASE`, defensive dashboard rendering, session-persisted token,
honest mermaid-failure fallback); unified error/empty/loading UX; added modal
accessibility.

---

## LATER — AXIOM's Own Brain (deferred roadmap)

Each is a separate future session:

1. **Comprehension** — extract the project's concrete entities/assets; richer
   `ProjectUnderstandingFrame` (confidence-weighted domains, real nouns) instead
   of flattening to `_INDUSTRY_DEFAULTS`.
2. **Analysis** — compose synthesis from the `ecosystem/` platform (standards +
   sections, rules engine, ontology, failure modes) blended with project
   entities, breaking the single-`IndustryPattern` bottleneck.
3. **Devise** — make the currently-static sections (security / deployment /
   monitoring / testing / risk / roadmap) derive from fired rules + standards.
4. **Educate** — grow the rules engine (only 6 rules today) + ontology via the
   human-gated `pending_knowledge` queue.
5. **Diagrams** — ER / sequence / class builders use the extracted entities so
   diagrams are per-project, not per-industry.
6. **Learning loop** — recalled prior solutions influence design (today it's
   cosmetic).
7. **Self-check** — Validation rejects generic-template output for concrete
   requests.

## Notes

- Monetization was removed for now; the provider-agnostic quota/billing code can
  be reintroduced later to gate the brain if a paid tier returns.
- "Brain" here means deterministic + knowledge-grounded, not a trained ML model.
