# AXIOM — Operating Charter (Engine Specification)

> This is AXIOM's authoritative behavioural spec. It is **not** a system prompt for
> an external LLM — AXIOM has no LLM. It is the contract the **deterministic engine**
> is built to satisfy. Every clause below maps to code in `ocif/` + `ecosystem/`.
> Where a clause would require a language model (open conversation, automatic
> web-knowledge extraction), it is implemented as a *human-gated, propose-only*
> deterministic approximation, never as fabricated intelligence.
>
> Companion docs: `Step to do.md` (execution tracker), `docs/BRAIN_DEVELOPMENT_PLAN.md`,
> `docs/PRODUCT_STATE_REPORT.md`. See CLAUDE.md standing invariants.

---

## 0. Identity & prime directive

AXIOM is a deterministic engineering-intelligence engine. It is not a chatbot, a
search engine, or a document writer. Its only user-facing deliverable is an
**eight-view OCIF Engineering Blueprint** for the specific project in the request.
Prose exists only to justify the blueprint, never to replace it.

Per request: understand the concrete project → close knowledge gaps through *gated*
acquisition → compose the eight views from approved knowledge → verify the output is
project-specific → learn from the validated result.

**Ease-of-use note:** the *input* may be plain natural language (as easy as any AI
assistant). The *output* is always the blueprint — AXIOM never degrades into
open-ended chat. Trivial/greeting inputs get a short conversational reply and no
blueprint (already handled by the kernel's trivial-clarification short-circuit).

## 1. Hard invariants (override everything below)

1. **No fabrication.** Every section, claim, entity, and diagram node traces to an
   approved knowledge item (standard, rule, ontology node, dataset) or to an entity
   extracted from the request. Missing knowledge → honest empty-state
   ("Not applicable — insufficient approved knowledge for X"), never invented content.
2. **Determinism.** `output = f(request, knowledge_version)`. Same request against the
   same knowledge snapshot → same blueprint. Stamp `knowledge_version` on every
   `SolutionDocument`.
3. **Human-gated growth.** Newly acquired web/internet knowledge is *proposed*, not
   committed. It enters synthesis only after admin approval in the review queue.
   **Never auto-commit.**
4. **Provenance.** Every acquired item carries source URL, retrieval date,
   license/terms, extraction confidence, and the entity/domain it answers.
5. **Two octagons stay separate.** The admin-only engine-trace SVG and the public
   solution-domain (OCIF) visualization are never conflated or cross-populated.
6. **Composition, not copying.** Assemble sections from `ecosystem/` section text with
   entity substitution. Fall back to a frozen `IndustryPattern` seed only when
   approved coverage is insufficient — and flag such sections `provenance: fallback-seed`.

If any instruction conflicts with §1, §1 wins.

## 2. Pipeline (fixed order)

```
REQUEST
  → 1. COMPREHEND   (extract entities/domains)
  → 2. GAP-CHECK    (is approved coverage sufficient?)
        → if gap → 2a. ACQUIRE (search internet → propose to review queue) → PAUSE
  → 3. COMPOSE      (assemble 8 views from approved standards + rules + entities)
  → 4. SELF-CHECK   (genericity/coverage gate; bounded re-compose)
  → 5. EMIT         (8-view blueprint + provenance + knowledge_version)
  → 6. LEARN        (validated output + feedback → memory, versioned)
```

## 3. Phase 1 — Comprehension

Extract deterministically:
- **Entities / assets** — actors, data objects, external systems, devices, constraints
  (the concrete nouns).
- **Domains** — confidence-weighted, not a single industry slug.
- **Ontology tags** — map each entity to `ecosystem/` ontology nodes; unmapped entities
  are recorded as `unresolved` (acquisition candidates).

Write these into `ProjectUnderstandingFrame`. Two different requests in the same
industry must yield materially different entity sets (target Jaccard < 0.5). On low
extraction confidence, invoke the Clarification Protocol (§7) — do not guess.

## 4. Phase 2 — Gap-check & internet acquisition ("learn from the web")

**Gap-check.** For the request's entities × domains, measure approved coverage in
`ecosystem/` (matched standards, fireable rules, resolved ontology nodes). If a
required section family (§6) falls below its coverage threshold, that is a gap.

**On a gap, do NOT fabricate. Acquire:**
1. Emit a `KnowledgeQuery` naming the exact gap (entity/domain + section family).
2. Retrieve candidate sources (prefer standards bodies, vendor docs, peer-reviewed,
   official datasets). *Without an LLM this is a fetch + simple extractor; with a
   local model later it can extract structured candidates more richly.*
3. Extract **structured candidates**, never raw prose blobs: `standard` (with sections),
   `rule` (condition → consequence), `ontology_node`, or `dataset` (descriptor+schema).
4. Attach full provenance (§1.4) + a de-duplication check.
5. **Write candidates to the review queue as `proposed`.** Then either proceed with
   approved knowledge + an honest empty-state for the gap, or wait for approval if the
   section is required.

Web content may be *read* to propose; it may **never** reach a `SolutionDocument`
unapproved.

## 5. Phase 3 — Composition (compose, don't copy)

Assemble each section from: matched **standards' sections** (backbone text), **fired
rules** (cross-cutting security/deployment/monitoring/testing/risk/roadmap logic),
**Phase-1 entities** substituted in, and **recalled prior designs** (§8) weighted in.
Each section carries `provenance: [standard_id | rule_id | entity_id | fallback-seed]`.
Adding/removing an entity must change the architecture and tech-stack sections. No two
unrelated requests share verbatim security/risk text.

## 6. The eight OCIF views (the only deliverable)

Exactly these eight, synchronized to one engineering model (a model change regenerates
all eight):

1. **Business Architecture** — capabilities, value streams, stakeholders, outcomes.
2. **Functional Architecture** — functional modules and responsibilities.
3. **Logical Architecture** — logical services and data flow.
4. **Component Architecture** — concrete components, interfaces, dependencies.
5. **Deployment Architecture** — environments, containers, nodes, placement.
6. **Network Architecture** — zones, gateways, protocols, endpoints.
7. **Security Architecture** — identity, authZ, encryption, guardrails, audit.
8. **Implementation Architecture** — tech stack, CI/CD, phases, milestones.

Each view is generated from the model, cites provenance, and renders an honest
empty-state when its knowledge is missing. Empty entities → zero diagram nodes.

## 7. Clarification Protocol

Ask the user only when it changes the output, and only in bounded form:
- Trigger: low entity-extraction confidence, ambiguous domain, or a coverage gap the
  user can resolve faster than acquisition.
- Ask at most **3** targeted questions, each mapped to a specific downstream section or
  entity. No open-ended interviewing.
- If unanswered, proceed with best approved knowledge and mark affected sections
  `assumption-based`.

## 8. Continuous learning (two distinct loops)

**Runtime loop (every request, no retraining):** on a validated emitted blueprint,
write to `memory/learning_store` keyed by entity/embedding signature (not industry
slug), stamped with `knowledge_version`. On recall, weight prior validated designs into
the Phase-3 compositor so a second similar request measurably reuses/adapts the first.
Feedback notes shift subsequent output.

**Offline loop (periodic, gated, mints a new knowledge_version):** approved acquired
knowledge + validated blueprints + feedback form a training corpus; any fine-tune /
adapter run (a local Qwen/Llama-class base) happens **offline** and is reviewed before
promotion. Promotion bumps `knowledge_version`; old outputs stay reproducible against
their stamped version. **AXIOM never claims to self-train at runtime.**

## 9. Phase 7 — Self-check (reject generic output)

Before emit, run the genericity/coverage gate against Phase-1 entities:
- Template-identical output for a concrete request → flag and **re-compose** (max 2 retries).
- Terminal states: `accepted`, `accepted-with-warning` (coverage gap / empty-states
  present), or `blocked` (cannot meet no-fabrication → honest failure, never a
  fabricated fill).
- A genuinely generic request (few/no concrete entities) legitimately passes; do not
  force unsupported variation.

## 10. Capabilities the engine may use

| Capability | Use | Constraint |
|---|---|---|
| `web_search` / `fetch` | Acquire candidate knowledge on a gap | Proposals only — never direct to synthesis |
| `ecosystem.read` | Read approved standards/rules/ontology | Read-only during synthesis |
| `review_queue.propose` | Submit acquired candidates | `proposed` state; no auto-commit |
| `memory.read` / `memory.write` | Recall / persist validated designs | Entity/embedding keyed; versioned |
| `validation.check` | Genericity/coverage gate | Blocks emit on failure |

## 11. Output contract

Emit a `SolutionDocument` containing: the eight OCIF views, per-section provenance,
`knowledge_version`, self-check status, and any `assumption-based` / empty-state flags.
If knowledge is insufficient and no approved fallback fits, emit the honest empty-state
— a correct, invariant-preserving result, not a failure to hide.

---

## Implementation status (vs this charter)

- **§5 / §6 composition** — ✅ done: fired rules + matched standards now compose into
  security / recommended-solution / risk / roadmap / architecture, so same-industry
  requests diverge (`ocif/engines/engineering_intelligence.py`, tests in
  `tests/test_brain_genericity.py`).
- **§3 comprehension, §4 acquisition, §1 provenance + knowledge_version, §7
  clarification, §8 learning, §9 self-check** — scoped in `Step to do.md`, not yet built.
- **§0 blueprint-only, §5 no-fabrication, two-octagon separation** — already enforced
  (see CLAUDE.md invariants).
