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
- [ ] **HTML — remove:**
  - login "Free plan: 5 chats/day, renews every 24h" note (`~1742`). Keep the
    `login-switch-link` / `toggleAuthMode` register toggle above it.
  - plan-pill button `#plan-pill` and its wrapping `status-bar-group` (`~1783`).
  - sidebar gear→account button `⚙ onclick="openAccountModal()"` (`~1833`).
    Keep the adjacent `↗ handleLogout()` button.
  - account/billing modal `#account-modal-overlay` (`~2072`).
  - paywall modal `#paywall-modal-overlay` (`~2104`).
- [ ] **JS — remove functions:** `loadBillingStatus`, `updatePlanPill`,
      `fmtRenews`, `openAccountModal`, `closeAccountModal`, `doUpgrade`,
      `loadKeys`, `addKey`, `deleteKey`, `showPaywall`, `closePaywall`, and the
      `state.billing` field.
- [ ] **JS — remove call sites:** the `loadBillingStatus()` call inside
      `applyAuthSuccess`; the `402` branch in `sendMessage` (collapse to the plain
      error path); any remaining `updatePlanPill()` / `loadBillingStatus()` calls.
- [ ] **Keep** login + register — real accounts survive; only the freemium framing goes.

**Acceptance:** grep for each removed symbol → zero hits; login → no network call
to `/billing` or `/keys`; no `ReferenceError` in console.

### Phase FE-2 — Fix backend-connection issues

**Goal:** make the client robust to host/config, missing fields, and refresh.

- [ ] **`API_BASE`** (`~2420`): replace the brittle `location.port === '3000'`
      heuristic with a single resolution order: `window.AXIOM_API_BASE` →
      `localStorage.getItem('axiom_api_base')` → same-origin `/api/v1`. One
      documented place to point at a non-default host.
- [ ] **`loadDashboard`** (`~3733`): defensive metric access (`data.requests ?? 0`,
      guard `cost_usd` before `toFixed`); fix the meaningless `requests/100*100`
      progress bar; render per-card so one missing field can't blank the panel;
      replace hardcoded placeholder deltas ("↑ Active", "within budget", "100%")
      with real values or neutral labels.
- [ ] **Token persistence:** store `state.token` in `sessionStorage`; restore on
      load so refresh doesn't force re-login; still cleared on logout.
- [ ] **JWT decode** (`~2514`): keep try/catch but surface a real error toast on
      decode failure instead of silently downgrading role to `end_user`.
- [ ] **`renderMermaidIn`** (`~3579`): fix the dead cleanup (`'d'+id` ≠ mermaid's
      real id); on render failure leave the raw mermaid source in a `<pre>`
      (honest fallback) rather than discarding it.
- [ ] **`renderBlueprintDiagrams`** (`~3402`): render an explicit empty-state when
      `project_diagrams` is absent instead of a silent no-op.
- [ ] **`handleLogout`** (`~2703`): rewrite the fragile chat-reset ternary.

**Acceptance:** works from any host without code edits; dashboard renders with a
partial payload; refresh keeps the session; a bad token shows a toast.

### Phase FE-3 — Consistency

**Goal:** one convention for errors / empty / loading; kill duplicate renderers.

- [ ] Shared `showError(context, err)` — toasts transient failures and renders a
      consistent inline `.empty-state` for panel loads. (Dashboard / knowledge /
      approvals currently use 3 different error markups: `~3797, ~3848, ~3913`.)
- [ ] Extract one empty-state + skeleton helper (hand-rolled 3× at
      `~3720, ~3804, ~3870`).
- [ ] Consolidate markdown/escape into one renderer (`escapeHtml` `~3568` vs
      `formatContent` `~3617`; `renderMarkdown` vs `formatContent`).
- [ ] Disable async action buttons while in-flight (`downloadDocument`,
      `downloadExport` are currently double-fireable).

**Acceptance:** all three panels show identical error/empty styling; no
double-download; a single markdown path.

### Phase FE-4 — Enhancements (quality / accessibility)

- [ ] `#domain-modal-overlay`: add `role="dialog"` + `aria-modal="true"`,
      Escape-to-close, and focus trap/restore.
- [ ] `aria-live="polite"` on the toast container.
- [ ] Graceful degradation across the presentation flow (executive summary → 8
      diagram grid → octagon map → collapsed full report): a missing field renders
      a labeled empty section, never a silent blank.
- [ ] Visible notice if `window.mermaid` / `window.marked` fail to load (offline
      CDN) rather than silent degradation.

**Acceptance:** modal is keyboard-operable; offline CDN shows a notice; no blank
sections on partial data.

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

### Phase 1 — Comprehension (understand the actual project)
- **Goal:** extract the request's concrete entities/assets (nouns: actors, data
  objects, external systems, constraints), not just an industry slug.
- **Where:** `ocif/engines/project_understanding.py` — enrich
  `ProjectUnderstandingFrame` with confidence-weighted domains + a real entity
  list; feed the existing `ecosystem/` ontology to tag entities.
- **Acceptance:** two different requests in the same industry produce materially
  different entity sets; entities are surfaced in the frame for downstream use.

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

### Phase 4 — Educate (grow the knowledge)
- **Goal:** expand the rules engine (only ~6 rules today) and the ontology through
  a **human-gated** review queue so quality stays controlled.
- **Where:** `ecosystem/` rules + ontology stores; governance/HITL queue.
- **Acceptance:** an admin can propose/approve a rule; approved rules immediately
  affect synthesis; nothing auto-commits without approval.

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
