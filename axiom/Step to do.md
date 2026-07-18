# AXIOM — Steps To Do (Detailed)

Status snapshot: **2026-07-16**. This is the detailed execution tracker for
**all remaining phases** after the Phase 0 backend teardown (OpenCode / billing /
free-limit removal), which is **done and verified**. Each phase lists its goal,
concrete files/symbols, acceptance criteria, and rationale so any session can
pick it up cold. Companion design doc: `docs/BRAIN_DEVELOPMENT_PLAN.md`.

Legend: `[x]` done · `[ ]` to do · line refs are approximate (they drift as edits land).

---

## ✅ DONE — Phase 0: Backend Teardown

**Goal:** strip OpenCode / all LLM providers / billing / free-limit quota; make the
deterministic `SolutionSynthesizer` the sole, always-on brain with the knowledge
platform injected by default. Keep real auth, the rate limiter, and real
usage-metering/dashboard.

**Deleted:** `inference/` (entire package incl. all providers + `model_router`),
`ocif/inference_adapter.py`, `ocif/diagram_brain.py`, `core/entitlement.py`,
`billing/`, `api/routes/billing.py`, `api/routes/keys.py`, and tests
`test_opencode_provider.py` / `test_entitlement.py` / `test_freemium_api.py`.

**Modified:** `ocif/engines/engineering_intelligence.py` (dropped the
`inference.complete` overlay + merge; synthesizer output is final),
`ocif/engines/{experience,project_understanding}.py` (deterministic only),
`ocif/project_diagrams.py` (always deterministic; absorbed `validate_mermaid`),
`ocif/kernel.py` + `api/routes/{chat,solution,deps}.py` (removed
`provider_override` / `gate_agent_request` / `record_agent_usage`; kept
`enforce_rate_limit` + `record_usage` metering), `core/config.py`
(removed `LLMProviderConfig` + entitlement; kept `BootstrapConfig.admin_password`,
JWT, rate-limit), `storage/models.py` (removed `Subscription` / `UserApiKey`;
kept `UsageMetric`), `core/models/base.py` (removed `LLMProvider` enum),
`core/security.py` (removed Fernet secret enc/dec; kept PBKDF2 + JWT + RBAC),
`api/routes/{auth,seed,__init__}.py`, `frames.py` (removed `llm_diagrams`),
`setup.cfg` (dropped `inference*` / `billing*`).

**Verified:** `pytest` → **317 passed** (excluding the pre-existing
PyMuPDF/`fitz` test that only fails on this Windows/Py3.13 box; passes in CI);
suite time 210s → 17s (no LLM/HTTP); `/solution` returns a full document + 8
diagrams with **zero outbound network**; `/billing` and `/keys` return 404.

---

## 🚧 IN PROGRESS — Frontend Rework (`frontend/index.html`, single-file SPA ~3900 lines)

The frontend calls 6 endpoints Phase 0 deleted (`/billing/status`,
`/billing/checkout`, `/keys`×3) plus freemium register framing, so it must be
cleaned in lockstep or login triggers 404s. **FE-1 is the safety-critical part**
(removes the dead endpoint calls); FE-2→FE-4 are quality.

### Phase FE-1 — Remove freemium UI (no danglers). Keep login + register.

**Goal:** delete every freemium surface so nothing references a deleted endpoint
or an undefined symbol.

- [x] Remove freemium CSS block (`.plan-pill`, `.axm-modal*`, `.axm-plan*`,
      `.axm-key*`, `.axm-paywall-msg`).
- [x] **HTML removed:** login free-plan note, `#plan-pill`, sidebar gear→account
      button, `#account-modal-overlay`, `#paywall-modal-overlay`.
- [x] **JS removed:** `loadBillingStatus`, `updatePlanPill`, `fmtRenews`,
      `openAccountModal`, `closeAccountModal`, `doUpgrade`, `loadKeys`, `addKey`,
      `deleteKey`, `showPaywall`, `closePaywall`, `state.billing`.
- [x] **Call sites removed:** `loadBillingStatus()` in `applyAuthSuccess`; the
      `402` branch in `sendMessage` collapsed to the plain error path.
- [x] **Kept** login + register.

**Acceptance:** ✅ grep for every freemium symbol → zero hits; no `/billing` or
`/keys` references remain. **Shipped in commit `95166b7`.**

### Phase FE-2 — Fix backend-connection issues ✅ DONE

**Goal:** make the client robust to host/config, missing fields, and refresh.

- [x] **`API_BASE`**: resolution order `window.AXIOM_API_BASE` →
      `localStorage['axiom_api_base']` → dev `:3000`→`:8000` → same-origin `/api/v1`.
- [x] **`loadDashboard`**: all metrics coerced with `?? 0` + `Number(...)` (no throw
      on partial payload); removed the meaningless `requests/100*100` bar; deltas are
      now neutral/honest; the two unbacked cards relabeled ("Governance: Active",
      "Platform Health: Healthy") with muted captions; error path escapes the message.
- [x] **Token persistence:** `state.token` restored from `sessionStorage` on load;
      `applyAuthSuccess` persists it; `restoreSession()` re-shows the shell silently on
      refresh; `handleLogout` clears it.
- [x] **JWT decode:** decode failure now shows an error toast and defaults role to
      `end_user` (no longer silent).
- [x] **`renderMermaidIn`:** removed the dead `'d'+id` cleanup; on failure the raw
      `<pre>` stays visible (`.mermaid-error`) and any stray body node is pruned.
- [x] **`renderBlueprintDiagrams`:** explicit empty-state when no diagrams.
- [x] **`handleLogout`:** rewrote the fragile ternary; clears chat pane + token.

**Acceptance:** ✅ `node --check` on the extracted inline script passes; all helper
references resolve; dashboard fields match `dashboard.py`. Live browser verify still
pending (needs `start.bat`).

### Phase FE-3 — Consistency ✅ DONE

**Goal:** one convention for errors / empty / loading; kill duplicate renderers.

- [x] Shared helpers `emptyState(icon, text)` (inline panel states) + `showError(context, err)`
      (transient action toasts). Dashboard / approvals / knowledge / blueprint-diagrams
      now all render empty + error states through them — one markup.
- [x] Shared `skeletonBlock(styles)` primitive; the 3 skeleton builders
      (dashboard / approvals / knowledge) now use it.
- [x] Consolidated the escape path: `formatContent` now calls `escapeHtml` instead
      of re-implementing it. (`renderMarkdown` → `formatContent` stays as the
      intentional marked-with-offline-fallback tier.)
- [x] `downloadDocument` / `downloadExport` guarded by an in-flight `Set` keyed by
      target → no double-download; errors routed through `showError`.

**Acceptance:** ✅ all panels share one empty/error markup; downloads are
single-fire; one escape path.

### Phase FE-4 — Enhancements (quality / accessibility) ✅ DONE

- [x] `#domain-modal-overlay`: `role="dialog"` + `aria-modal="true"` +
      `aria-labelledby`; Escape-to-close, Tab focus trap, focus-in on open, and
      focus restore on close; close button `aria-label`.
- [x] `role="status"` + `aria-live="polite"` on the toast container.
- [x] Graceful degradation: domain drill-down with no diagrams/artifacts shows a
      labeled empty-state; dashboard + blueprint diagrams already guard partial data.
- [x] CDN-fail banner: a visible `role="alert"` notice if `marked` / `mermaid`
      failed to load, instead of silent raw-text degradation.

**Acceptance:** ✅ modal keyboard-operable (Esc/Tab/focus); offline CDN shows a
notice; no silent blank sections. `node --check` passes.

### Frontend — Definition of Done (verify)
- [ ] `start.bat` → login → send an engineering request → 8 diagrams render.
- [ ] Dashboard loads, no console errors, **no** `/billing` or `/keys` in Network tab.
- [ ] Refresh keeps the session; no paywall/plan UI anywhere.

---

## 🔮 LATER — AXIOM's Own Brain (deferred roadmap)

**Root problem to solve:** today the whole `SolutionDocument` is copied from one
of 19 frozen `IndustryPattern`s (`ocif/engines/industry_patterns.py`) chosen by a
single industry slug (`select_pattern`) — so many sections are identical across
requests ("same answer for everything"). The rich `ecosystem/` knowledge platform
(standards-with-sections, a rules engine with only ~6 rules, an ontology, failure
modes) was only ever fed to the now-removed LLM prompt. These phases route that
knowledge into the deterministic synthesizer so output becomes **per-project**,
not per-industry. Each phase is its own session.

### Phase 1 — Comprehension (understand the actual project) ✅ DONE
- **Goal:** extract the request's concrete entities/assets (nouns), not just tech keywords.
- **Built:** `ContextEngine._extract_domain_nouns()` harvests concrete domain nouns
  (patient, cafeteria, loomweaver…) from the request — deterministic, stopword-filtered,
  dependency-free — and appends them to `frame.entities` (tech entities still lead). These
  now flow into `rules_for` (richer firing), the executive summary, and the compositor.
- **Acceptance:** ✅ `test_phase1_domain_entities_differentiate` (two same-industry
  requests → Jaccard < 0.5) and `test_phase1_generic_request_stays_generic` (no fake
  entities from filler). 323 tests green.
- **Deferred:** confidence-weighted domains + ontology-tagging of entities (Charter §3
  `unresolved` candidates) — the noun harvest is the high-leverage 80%.

### Phase 2 — Analysis (compose, don't copy)
- **Goal:** build the synthesis from `ecosystem/` standards + sections + fired
  rules + Phase-1 entities instead of lifting a whole `IndustryPattern`.
- **Where:** `ocif/engines/engineering_intelligence.py::SolutionSynthesizer` —
  replace the single-pattern copy with a compositor that assembles sections from
  matched standards and entities; keep `IndustryPattern` only as a fallback seed.
- **Acceptance:** removing/adding an entity changes the architecture/tech-stack
  sections; sections cite which standard/rule produced them.

### Phase 3 — Devise (derive the static sections)
- **Goal:** make security / deployment / monitoring / testing / risk / roadmap
  derive from fired rules + standards rather than frozen prose.
- **Where:** the section builders in `SolutionSynthesizer`; `ecosystem/` rules engine.
- **Acceptance:** these sections vary with the request's rules/standards; no two
  unrelated requests share verbatim security/risk text.

### Phase 4 — Educate (grow the knowledge) ✅ DONE
- **Goal:** expand the rules engine through a **human-gated** review queue.
- **Built:** `EngineeringRulesEngine.propose()` submits a rule to the pending queue;
  `evaluate()` now reads seed rules **+ approved** ENGINEERING_RULE objects from the
  repository (deduped), so an approved rule fires on the next request with no restart.
  Route `POST /api/v1/platform/rules/propose`; approval via the existing
  `POST /platform/pending/{id}/decision`.
- **Acceptance:** ✅ `tests/test_brain_genericity.py::test_phase4_human_gated_rule_growth`
  — proposed rule does NOT fire until approved, then fires immediately and reaches the
  composed architecture. Nothing auto-commits (Charter §1.3).
- **Deferred:** ontology growth via the same queue (rules first; ontology is analogous).

### Phase 5 — Diagrams (per-project, not per-industry)
- **Goal:** ER / sequence / class diagram builders consume Phase-1 entities.
- **Where:** `ocif/project_diagrams.py` builders + `ocif/solution_mapping.py`.
- **Acceptance:** ER diagram nodes are the request's real entities; two requests
  yield structurally different diagrams; empty entities → honest empty-state.

### Phase 6 — Learning loop (make recall matter)
- **Goal:** recalled prior solutions (durable `memory/learning_store.py`) actually
  influence the new design, not just decorate `final_recommendations`.
- **Where:** `MemoryEngine` recall → weight into the Phase-2 compositor.
- **Acceptance:** a second similar request measurably reuses/adapts the first's
  validated design; feedback notes shift subsequent output.

### Phase 7 — Self-check (reject generic output)
- **Goal:** Validation engine rejects generic-template output for concrete
  requests and forces a re-compose.
- **Where:** `ocif/engines/validation.py` — add a genericity/coverage check
  against the extracted entities.
- **Acceptance:** a concrete request that yields template-identical output is
  flagged and regenerated; a genuinely generic request still passes.

---

## 📜 Operating Charter alignment (from `docs/AXIOM_OPERATING_CHARTER.md`)

The Master Charter is the same roadmap as the phases above, made rigorous. Phases
1–7 map 1:1 to Charter §3–§9. The Charter adds these **cross-cutting** items to
build alongside the phases (all deterministic — none needs an LLM):

- [ ] **Provenance (Charter §1.4/§5):** every `SolutionDocument` section carries
      `provenance: [standard_id | rule_id | entity_id | fallback-seed]`. Sections that
      fall back to the frozen `IndustryPattern` are flagged `fallback-seed`.
- [ ] **`knowledge_version` stamp (Charter §1.2):** stamp the ecosystem knowledge
      snapshot id on every document so `output = f(request, knowledge_version)` and
      old outputs stay reproducible.
- [ ] **Honest empty-states (Charter §1.1):** where approved knowledge is missing,
      render "Not applicable — insufficient approved knowledge for X", never invented
      content. (Extends the existing no-fabrication invariant to the new compositor.)
- [ ] **Gap-check + web acquisition (Charter §4):** measure approved coverage for the
      request's entities × domains; on a gap, `fetch` candidate sources, extract
      *structured* candidates (standard/rule/ontology/dataset) with full provenance,
      and **propose to the review queue only** (never auto-commit). Without an LLM this
      is a simple extractor + admin review; a local Qwen can enrich it later.
- [ ] **Clarification Protocol (Charter §7):** on low entity-extraction confidence, ask
      ≤3 targeted questions mapped to specific sections; else proceed and flag affected
      sections `assumption-based`.
- [ ] **Self-check terminal states (Charter §9):** `accepted` /
      `accepted-with-warning` / `blocked` (honest failure, never a fabricated fill).

**Reframe recorded:** "make the prompt an LLM" is not literally possible (a prompt is
not a trained model). The Charter is implemented as the **deterministic engine's
behaviour**; the only parts that would benefit from a *local* model (open dialogue,
rich web extraction) are optional overlays, deferred, and never on the critical path.

---

## Notes / invariants to respect
- **Monetization removed for now.** The provider-agnostic quota/billing code can
  return later to gate the brain if a paid tier comes back — don't design the brain
  in a way that blocks re-adding it.
- **Auth (login/register) and per-tenant rate limiting stay** — they are not
  "billing / free-limit".
- **No fabrication invariant** (see `CLAUDE.md`): document/diagram builders only
  re-arrange already-validated `SolutionDocument` fields; empty input → "Not
  applicable." sections + zero diagrams, never invented content. Brain phases must
  preserve this.
- **The two octagons stay separate:** engine-trace SVG (admin-only) vs the public
  solution-domain visualization — never conflate them.
