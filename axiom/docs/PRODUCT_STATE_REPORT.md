# AXIOM — Product State Report & 10-Day Completion Plan

**Date:** 2026-07-17 · **Branch:** `MD-Backend` (= `Develop-Branch`) · **HEAD:** `95166b7`
**Prepared from:** a full three-track codebase audit (backend/brain, frontend/API, deployment/ops), cross-verified against the running tree.
**Deadline:** 10 working days → target **~2026-07-31**.

---

## 1. Executive Summary

AXIOM is a **sizable, working, well-structured FastAPI monolith** (~17.4K LOC product Python across 10 packages + a 3.7K-line single-file frontend; 327/328 tests green). The Phase 0 teardown (removing OpenCode, all LLM providers, billing, and the freemium quota) is **verifiably complete and clean** — no broken imports, the deterministic `SolutionSynthesizer` is the sole generation path, and it produces a full 18-section solution + 8 diagrams with **zero outbound network calls**.

**The product runs. The problem is *what it produces*.**

There is **one product-defining blocker** and a set of **finishing-work items**:

- 🔴 **BLOCKER — Genericity ("same answer for everything").** Solution architecture is copied from **1 of 19 frozen industry templates**, selected purely by an industry slug from a keyword classifier. 3+ sections are byte-for-byte identical for *every* request regardless of industry. The rich `ecosystem/` knowledge platform and the learning memory are both built, seeded, and injected — but **disconnected from the generated document** (they only populate a dev-only trace / append one sentence). This is the core value failure and the main thing "completion" must fix.
- 🟠 **Finishing work** — frontend robustness (FE-2/3/4), 2 real frontend bugs, 2 known backend bugs, and production hardening (config fail-fast, dependency/dead-code cleanup, migrations decision, secret rotation).

**Feasibility in 10 days:** Yes, for a scoped definition of "complete" — a **Genericity v1** that makes output genuinely request-specific (not the full 7-phase brain), plus finished frontend and a hardened, deployable backend. The full self-learning brain remains a later effort. This report defines that scope and a day-by-day plan.

---

## 2. Current State — What Works Today

| Area | Status | Evidence |
|---|---|---|
| Deterministic generation pipeline | ✅ Working, stable | `ocif/kernel.py:122` → 8 engines → `SolutionSynthesizer` (`engineering_intelligence.py:840`) → `PresentationRenderer` (`renderers/presentation.py:32`) |
| API surface (24 routes) | ✅ Complete, non-stubbed | `api/routes/*` — auth, chat, solution, feedback, dashboard, documents, approvals, admin, knowledge, knowledge_platform, project_intelligence |
| Auth (register + login) | ✅ Real | PBKDF2-SHA256 + per-user salt (`core/security.py:30-67`); hand-rolled HS256 JWT (`:83-148`) |
| RBAC | ✅ Default-deny matrix | `core/security.py:156-198` |
| Rate limiting + usage metering | ✅ Wired on kernel routes | `api/routes/deps.py:62-78`; `UsageMetric` writes via `usage.py:30-63` |
| Multimodal upload → analysis | ✅ Working | `POST /projects/analyze` (`project_intelligence.py:33-114`) |
| Knowledge vector search | ✅ Real | `GET /knowledge/search` (`knowledge.py:18-38`) |
| Frontend freemium removal (FE-1) | ✅ Fully done | grep for all freemium symbols → zero matches |
| CI | ✅ Exists & green | `.github/workflows/ci.yml` (repo root, one level above `axiom/`): push+PR, Py3.12, installs `requirements.txt` (incl. PyMuPDF), import smoke + `pytest` |
| Tests | ✅ 327/328 pass | 1 failure is environmental only: `fitz`/PyMuPDF not installed locally; passes in CI |
| Docker build | ✅ Clean | multi-stage, non-root user, healthcheck, `uvicorn api.gateway:create_gateway_app --factory` |

**Module inventory (product Python, excl. tests):** ocif 6,659 · datasets 2,914 · ecosystem 2,031 · core 2,012 · api 1,755 · knowledge 705 · memory 485 · storage 456 · governance 244 · multimodal 179 → **~17.4K LOC**. Tests: 23 files / 2,935 lines (~17% ratio — healthy).

---

## 3. 🔴 THE BLOCKER — Output Genericity

This is the single most important item. Everything else is finishing work.

### What happens now
1. `project_understanding.classify()` is **rule-based only** (`project_understanding.py:611-623`) — keyword hit-count scoring picks 1 of ~15 industries; fallback confidence hardcoded 0.55.
2. `select_pattern()` (`industry_patterns.py:1238-1248`) keys **only** on that industry slug → returns 1 of **19 frozen `IndustryPattern`s**. Nothing about the request text, entities, scale, or constraints changes the choice or the contents.
3. The synthesizer copies that pattern into the document.

### Quantified impact (of ~20 SolutionDocument fields)
- **~6 core architecture fields are frozen-per-industry** (architecture, tech stack, component design, DB/ER design, API design, workflow) — identical for any two requests in the same industry.
- **3+ fields are globally constant for *every* request:** `deployment_architecture`, `monitoring_strategy`, `testing_strategy`, and roadmap Phases 1/3/4 (`industry_patterns.py:605,622,634,647`) — the `*_extra` hooks are never populated (0 occurrences).
- `security_architecture` identical for 12/19 industries; `risk_assessment` identical for 15/19.
- **Only ~4 fields truly vary with the request:** title, requirements-analysis tables, and entity/persona interpolations in the exec-summary/problem-statement.
- **Concrete example:** "hospital bed management" and "clinical trial portal" produce *identical* architecture, tech stack, ER model, API surface, deployment, monitoring, and testing.

### Why the good material isn't used
The `ecosystem/` knowledge platform (**6 rules**, ~48 ontology nodes, standards registry, failure modes, knowledge packs) **is** constructed, seeded, and injected into the engine (`deps.py:25-34` → `engine_registry.py:167`). But in `_run()` its outputs are written **only to `context.metadata["engineering_intelligence"]`** (dev-trace) — the `synthesize()` call receives just `(frame, plan, knowledge, learning, understanding)`, **not** the packs/standards/rules/diagrams. Their only former consumer was `_build_dynamic_prompt()`, which is now **dead code** (defined, never called). Learning memory is the same story: recall runs, but only appends a sentence and a ±0.05 confidence nudge — it does **not** change any design decision.

**In short:** the knowledge to make output specific already exists and is already loaded; it is simply not routed into the generator. That is what makes a meaningful fix achievable inside 10 days.

---

## 4. Issues Inventory (prioritized)

### P0 — Product-critical
| # | Issue | Location |
|---|---|---|
| P0-1 | Genericity: 1-of-19 frozen template selected by slug (see §3) | `industry_patterns.py:1238`; `engineering_intelligence.py:840` |
| P0-2 | Ecosystem knowledge (rules/standards/packs) orphaned from output | `engineering_intelligence.py:787-835` vs `:840` |
| P0-3 | Globally-constant sections (deployment/monitoring/testing/roadmap) | `industry_patterns.py:605,622,634,647` |

### P1 — Correctness bugs (user-visible)
| # | Issue | Location |
|---|---|---|
| P1-1 | **Approvals data-contract mismatch** — UI reads `risk_score`/`summary`/`requested_at`; API returns `approval_id/event_id/status/assigned_to/resolved_at/comments` → `NaN%`, `undefined`, `—` | `index.html:3587-3592` vs `approvals.py:31-39` |
| P1-2 | **No token persistence** — refresh logs the user out (contradicts the frontend Definition of Done) | `index.html:2410`; no `sessionStorage` |
| P1-3 | `RequestContextManager.__exit__` contextvars reset errors on **every authenticated request** (swallowed, logged as ERROR; leaks logging contextvars) | `core/observability.py:115-120`; token set in `middleware/auth.py:99`, reset in `gateway.py:62-66` |
| P1-4 | `chat.py` never persists `ConversationTurn`/`Session` → dashboard `sessions` under-reports | `chat.py:50-96`; `dashboard.py:35-37` |

### P2 — Production hardening
| # | Issue | Location |
|---|---|---|
| P2-1 | `OCIF_ADMIN_PASSWORD` defaults to `admin123`, **not** fail-fast in prod (JWT secret already is) | `config.py:135,234-236` |
| P2-2 | No Alembic; schema via `create_all` + one ad-hoc SQLite column migration. Comments reference Alembic that doesn't exist | `seed.py:34,44-59`; `config.py:77` |
| P2-3 | DB defaults to SQLite; switches to Postgres only if a password is set; **no PG driver** (`asyncpg`/`psycopg2`) in `requirements.txt` | `config.py:71-73`; `database.py`; `requirements.txt:25` |
| P2-4 | No logout (no revocation) and no refresh endpoint (`jwt_refresh_expiration_seconds` unused); 1h token + no persistence = frequent forced logins | `auth.py`; `config.py:126-127,231` |
| P2-5 | `aud`/`iss` claims set but never verified on decode | `security.py:96-97` vs `:114-148` |
| P2-6 | Plaintext dead `GOOGLE_API_KEY` sitting in `.env:13` (gitignored, not in history) — rotate/remove | `.env:13` |
| P2-7 | Only kernel routes are rate-limited (coupled to auth dep); `/health`, `/`, static, future public routes are not | `gateway.py:136-147`; `deps.py:62-63` |

### P3 — Cleanup (low-risk, high-tidiness)
| # | Issue | Location |
|---|---|---|
| P3-1 | Orphaned deps: `httpx` (no app import) and `cryptography` (comment false; only stdlib used) | `requirements.txt:8,10` |
| P3-2 | Dead exception classes never raised: `PaymentRequiredError`, `LLMProviderError`, `LLMTimeoutError`, `AgentMaxStepsExceededError`, `ToolInvocationError` | `core/exceptions.py:187-413` |
| P3-3 | Dead LLM-era methods: `_build_dynamic_prompt`, `_extract_json`, `_merge`, `_SOLUTION_JSON_INSTRUCTION` | `engineering_intelligence.py:719,880,983,994` |
| P3-4 | Stale LLM references: `docker-compose.yml:14-17` (LLM env), `.env.example:9-24`, `usage.py` unmounted but still written to, stale docstrings in `project_understanding.py`/`ecosystem/rules.py` | multiple |
| P3-5 | `KernelOutput` token/cost fields always 0/"internal-synthesizer" | `kernel.py:74-79` |
| P3-6 | Frontend: FE-2/3/4 quality items (see §5) + admin nav not role-gated in UI (backend enforces) | `index.html` |

---

## 5. Frontend Remaining Work (FE-2 / FE-3 / FE-4)

FE-1 (freemium removal) is done. All of the following are **confirmed still open** (line refs in `Step to do.md`):

- **FE-2 (robustness):** `API_BASE` port===3000 heuristic (`2319`); `loadDashboard` unguarded field access + meaningless progress bar + hardcoded placeholder deltas (`3487-3553`); no token persistence (P1-2); JWT decode silent role-downgrade (`2412-2416`); `renderMermaidIn` dead `'d'+id` cleanup (`3347`); `renderBlueprintDiagrams` silent no-op empty-state (`3160`); fragile `handleLogout` (`2459-2466`).
- **FE-3 (consistency):** 3 different error/empty markups; duplicated `escapeHtml`/`renderMarkdown`/`formatContent`; double-fireable download buttons.
- **FE-4 (a11y/degradation):** `#domain-modal-overlay` no `role/aria-modal/Escape/focus`; toast container no `aria-live`; no CDN-fail notice.
- **Dashboard honesty:** 4 metric cards ("Layer 7 Decisions", "Platform Health", etc.) are not backed by any endpoint (`3532-3548`).

---

## 6. Requirements to Reach "Complete"

"Complete" for this deadline = **a deployable product that produces genuinely request-specific solutions, with a finished, robust UI, hardened config, and clean CI.** Concretely:

**R1 — Request-specific output (Genericity v1).** Two different requests in the same industry must differ materially in architecture, tech stack, security, risk, and roadmap. Achieved by routing the already-loaded ecosystem knowledge (standards + 6 rules + packs) and extracted entities into `synthesize()`, and by deriving the currently-constant sections from fired rules/standards. (This is a scoped subset of the deferred 7-phase brain — not the whole thing.)

**R2 — Correctness bugs fixed:** P1-1..P1-4.

**R3 — Frontend finished:** FE-2, FE-3, FE-4, and the Frontend Definition of Done in `Step to do.md` (login → 8 diagrams → dashboard → refresh keeps session → no dead-endpoint calls).

**R4 — Production hardening:** P2-1 (admin pw fail-fast), P2-3 (DB driver + explicit DB-selection), a migrations decision (Alembic **or** an explicit "SQLite-only for v1" statement), P2-6 (rotate key), and a CORS/allowed-origins review.

**R5 — Cleanup:** P3 items (dead deps/code/env) so the shipped artifact is honest and lean.

**R6 — Verification:** CI green on 3.12 with PyMuPDF; a live end-to-end smoke (register → chat → docs/export → dashboard → refresh) and a Docker-image smoke against `/health` + `/api/v1/solution`.

---

## 7. The 10-Day Plan

Assumes ~10 working days. Sized for 1–2 engineers; with one engineer, defer FE-4 and P3 polish. Days are sequential milestones, not rigid dates.

### Phase A — Foundation & bug-fix (Days 1–2)
- **Day 1:** Fix P1-3 (contextvars reset — move `__exit__`/reset into the same context as `__enter__`, e.g. do both inside the middleware, or use a context-manager that spans the request) and P1-4 (persist `ConversationTurn` + create a `Session` on first turn via `MemoryManager.persist_turn`). Fix P1-1 (align the approvals API response with what the UI renders — add `risk_score`/`summary`/`requested_at` to `approvals.py` **or** adjust the UI; prefer fixing the API to expose the real fields). Land P2-1 (admin-pw fail-fast) and P2-6 (rotate/remove `.env` key).
- **Day 2:** P3 cleanup sweep — drop `httpx`/`cryptography` from requirements, delete dead exception classes + dead LLM methods, scrub LLM env from `docker-compose.yml`/`.env.example`, decide `usage.py` (mount or fold in). Add `asyncpg` to requirements and make DB selection explicit (P2-3). Verify tests still green after each change.

### Phase B — Genericity v1 (Days 3–6) — the core value work
- **Day 3:** Extend `synthesize()`'s signature to accept `packs`, `platform_standards`, `rules_applied`, and extracted entities (already computed at `engineering_intelligence.py:787-803`). Thread them from `_run()` (stop dropping them into dev-trace only). No behavior change yet — just plumbing + tests.
- **Day 4:** Make the **currently-constant sections request-derived** (P0-3): `security_architecture`, `risk_assessment`, `deployment/monitoring/testing`, and roadmap phases now compose from fired rules + matched standards + entities instead of frozen prose. Add ecosystem rules so common request features (auth, PII, real-time, high-scale, payments…) fire distinct constraints.
- **Day 5:** Break the **1-of-19 architecture lock** (P0-1/P0-2): keep `IndustryPattern` as a *seed*, but layer entity-driven and standards-driven content on top so tech stack / components / API / ER reflect the actual request. Make learning recall influence at least one real design section (not just a sentence).
- **Day 6:** Entity-driven **diagrams** (ER/sequence/class use extracted entities → per-project, not per-industry). Add a genericity self-check in Validation that flags template-identical output for concrete requests. **Milestone gate:** two same-industry requests now differ across architecture/security/risk/roadmap/diagrams. Write tests asserting divergence.

### Phase C — Frontend completion (Days 7–8)
- **Day 7:** FE-2 — `API_BASE` override (`window.AXIOM_API_BASE`/localStorage/same-origin); token persistence via `sessionStorage` + restore-on-load (closes P1-2); defensive `loadDashboard` (per-card render, guarded fields, real/neutral deltas, remove fake cards or back them with data); JWT-decode error toast; `renderMermaidIn` honest fallback; `renderBlueprintDiagrams` empty-state; rewrite `handleLogout`.
- **Day 8:** FE-3 (shared `showError`/empty-state/skeleton, one markdown renderer, disable in-flight buttons) + FE-4 (modal `role=dialog`/`aria-modal`/Escape/focus, toast `aria-live`, CDN-fail notice). Role-gate the admin nav in the UI.

### Phase D — Hardening, verification, ship (Days 9–10)
- **Day 9:** Migrations decision — either introduce Alembic with an initial revision, or explicitly document "SQLite create_all for v1" and remove the misleading Alembic comments. CORS/allowed-origins review for the target deploy. Add a logout endpoint (client token clear is fine for v1; note revocation as a known limitation) and verify `aud`/`iss` (P2-5) or explicitly drop the claims.
- **Day 10:** Full verification (R6): CI green on 3.12 w/ PyMuPDF; live e2e smoke; Docker-image smoke (`/health`, `/api/v1/solution`); update `Step to do.md`/`docs/` to reflect what shipped. Tag/PR to `Develop-Branch` → `main`.

### If time is tight (cut order)
1. FE-4 a11y polish → 2. P3-5/P3-6 cosmetics → 3. Alembic (fall back to documented SQLite) → 4. Genericity Day 6 diagrams (keep the section/architecture work, defer per-entity diagrams). **Never cut:** P1 bugs, Genericity Days 3–5, FE-2 token persistence.

---

## 8. Risks & Assumptions

- **Biggest risk: Genericity v1 scope creep.** The full brain is a 7-phase, multi-week effort (`docs/BRAIN_DEVELOPMENT_PLAN.md`). The plan deliberately targets a *composition-from-existing-knowledge* v1, not new ML. If Days 3–6 slip, ship the section-level improvements (Day 4) as the minimum that defeats "identical output."
- **Assumption:** 10 **working** days, ~1–2 engineers. Solo halves throughput — cut per §7.
- **Assumption:** target deploy is single-tenant/SQLite-acceptable for v1, or Postgres with the driver added on Day 2. If multi-tenant Postgres at scale is required, add ~2 days for Alembic + connection hardening.
- **Environmental:** local box is Python 3.13; project targets 3.12 (Docker/CI). Do final verification on 3.12 to avoid drift.
- **No LLM in scope.** If a local model (e.g. Qwen3-14B) is later desired, wire it as an *optional overlay* on top of the deterministic base — do not make it the sole path (preserves the "never degrades to a stub" guarantee).

---

## 9. Definition of Done

- [ ] Two distinct same-industry requests produce materially different architecture, tech stack, security, risk, roadmap, and diagrams (automated test asserts divergence).
- [ ] P1-1..P1-4 fixed; no contextvars ERROR in logs; refresh keeps the session.
- [ ] Frontend FE-2/FE-3/FE-4 done; no dead-endpoint calls; dashboard shows only real/honest metrics.
- [ ] Admin password fail-fast in prod; dead key rotated; orphaned deps/code/env removed.
- [ ] Migrations decision made and documented; PG driver present if Postgres is targeted.
- [ ] CI green on 3.12 with PyMuPDF; live e2e + Docker smoke pass; merged to `main`.

---

*Sources: three-track audit of `MD-Backend@95166b7`, cross-verified against the running tree. Companion docs: `Step to do.md` (task tracker), `docs/BRAIN_DEVELOPMENT_PLAN.md` (full brain roadmap).*
