# AXIOM — Working Notes for Claude

This folder (`axiom/`) is the project root as of 2026-07-09's consolidation —
everything (code, tests, docs, data, Docker files, config) lives inside it.
Only `.git/` and `.github/` remain one level up at the true repo root
(GitHub Actions requires workflows there; nothing else). Imports are flat
(`api.gateway`, `core.config`, `ocif.kernel` — no `axiom.` prefix anywhere).
This file is a steady-state reference — read it for standing invariants
before making further changes.

## Standing invariants (do not re-litigate)

- **Cognitive engine execution stays internal; the octagon SHAPE is also a
  public presentation model.** Two separate things share the word "octagon"
  — don't conflate them:
  - `ocif/octagon.py::build_octagon_svg` — engine execution status/timing,
    attached to `CognitiveTrace.octagon_svg`, `developer_mode`-only, gated
    to `platform_admin` (`api/routes/deps.py::is_developer`).
  - `ocif/visualization.py::OctagonalVisualizationEngine` — the finished
    `SolutionDocument` re-mapped onto the same 8 conceptual slots as
    **solution content domains** (Perception=problem/env, Context=
    requirements, Planning=roadmap, Knowledge=tech stack, Memory=
    architecture/data, Reasoning=solution rationale, Validation=risk/test/
    security, Experience=deployment/ops). This is the PRIMARY output —
    returned to every user via `/api/v1/solution` and `/api/v1/chat/messages`
    as `octagonal_model` + `visualizations` + `implementation_roadmap` +
    `generated_documents` + `dashboard` + `documents_catalog` +
    `export_manifest`, never gated. The pipeline (`ocif/blueprint_pipeline.py`
    -> `solution_mapping.py` -> `visualization.py` -> `roadmap.py` ->
    `documents.py` -> `presentation.py`, orchestrated by
    `ocif/renderers/presentation.py::PresentationRenderer`) takes only
    `SolutionDocument` as input everywhere — structurally cannot see
    `CognitiveContext`.
  See persistent memory file `axiom-ocif-internal-only.md` for the full
  directive history.
- **Dashboard-first, not report-first.** `/api/v1/solution` and
  `/api/v1/chat/messages` return a `dashboard` field (short executive
  summary + lightweight octagon-navigation metadata + roadmap overview +
  document/export catalogs) as the primary payload. The full 18-section
  markdown report still exists (`markdown`/`response` fields, unchanged for
  backward compatibility) but is meant to be collapsed/optional in any UI —
  see the frontend's `<details class="full-report-toggle">`.
- **Documents/exports are rendered on demand, not eagerly.** Every response
  carries only catalogs (`documents_catalog`: 15 types incl. OpenAPI;
  `export_manifest`: svg/mermaid/plantuml/json_graph/reactflow/markdown/
  json/html available, pdf/png explicitly marked unavailable with a reason).
  Full content comes from `GET /api/v1/solutions/{id}/documents/{type}` and
  `GET /api/v1/solutions/{id}/export/{fmt}`, backed by `ocif/renderers/
  solution_cache.py` — an ephemeral, bounded, in-process cache keyed by
  `solution_id`, populated every time `PresentationRenderer.render()` runs.
  A solution_id not in the cache (e.g. after a restart) returns 404 with a
  message to re-issue the original request — documents are cheap to
  re-derive, so this is intentional, not a bug to fix.
- **LLM inference happens only inside `ocif/engines/reasoning.py`**
  (`InferenceAdapter`). Every other engine is provider-agnostic. When no live
  provider responds (or only the offline simulator is configured), the
  deterministic `SolutionSynthesizer` in the same file guarantees a complete,
  contract-valid solution — the platform never degrades to a stub output.
- **Learning memory is durable, not in-process.** `memory/learning_store.py`
  is a stdlib-sqlite store (mirrors the pattern in `knowledge/graph.py`)
  holding validated solutions (`learning_records`) and explicit user feedback
  (`feedback_notes`), keyed by `(tenant_id, project)`. `MemoryEngine` recalls
  similar past solutions by intent+entity overlap and feeds them into both the
  LLM prompt and the offline synthesizer's `final_recommendations`. Survives
  process restarts — verified in `tests/test_learning_memory.py`.
- Both octagon SVGs are pure-stdlib string-templated SVG (`ocif/layout.py`
  holds the shared ring-geometry math) and rendered raw client-side — trusted,
  server-generated, no user-controlled interpolation in either.
- No document/diagram is ever fabricated: `DocumentRenderer` templates only
  re-arrange already-validated `SolutionDocument` fields; `SolutionMappingEngine`
  only extracts mermaid blocks already embedded in the blueprint or derives
  diagrams deterministically from already-structured fields (tech stack,
  roadmap phases, risk list, actors) — an empty blueprint produces zero
  diagrams and "Not applicable." document sections, never invented content.

## Repository layout

Flat, `axiom/` is the root: `ocif/` (cognitive core + solution presentation
pipeline), `api/` (gateway + middleware + routes, one file per feature area,
plus `api/routes/documents.py` for on-demand rendering), `inference/` (LLM
providers), `knowledge/` (RAG backbone), `memory/` (conversation + durable
learning store), `governance/` (policy + HITL), `storage/` (SQLAlchemy
models/DB), `core/` (config, security, event bus, engine registry),
`frontend/` (dashboard-first SPA). `docs/specs/` holds the original 20-part
specification set; `docs/architecture/` holds the curated architecture
reference. `tests/`, `data/`, and all config/Docker files are siblings of
`ocif/`/`api/`/etc. No `layerN_*` folders remain anywhere — all legacy
8-layer-pipeline code was deleted, not archived, after confirming the OCIF
kernel fully superseded it.

`.agents/` and `design-system/` (an installed Claude Code skill plugin and
one generated design doc — pre-existing, unrelated to AXIOM) stay at the
true outer repo root, deliberately excluded from this consolidation.

## Known pre-existing issue (not fixed, out of scope so far)

`RequestContextManager.__exit__` (`core/observability.py`) occasionally logs
"was created in a different Context" — a contextvars-across-Starlette-
middleware-boundary issue predating any of this session's work. Cosmetic
(logged as ERROR but requests still succeed); fixing it properly means
restructuring how `RequestContextMiddleware` tears down the context relative
to where `resolve_security_context` sets it up.

Also: `api/routes/chat.py` does not persist conversation turns to the
`ConversationTurn` table (only to in-process/durable OCIF memory), so
`/api/v1/dashboard/usage`'s `requests` metric under-reports. Wiring
`memory/conversation.py::MemoryManager.persist_turn` into the chat route
(with a `Session` row created on first turn) would close this gap.

## Verification performed (most recent pass)

- Directory consolidation: `tests/`, `docs/`, `data/`, `.vscode/`,
  `pyproject.toml`, `setup.cfg`, `requirements.txt`, `Dockerfile`,
  `docker-compose.yml`, `.dockerignore`, `README.md`, `CLAUDE.md`, `.env*`,
  `.gitignore` all moved into `axiom/`; `axiom/__init__.py` deleted.
- Bulk import-prefix rewrite: 251 `from axiom.`/`import axiom.` lines across
  79 files rewritten to drop the prefix; grep-verified zero remaining.
- Fixed the one path-depth bug this move caused: `api/routes/seed.py`'s
  `project_root` traversal (4 levels -> 3, since `docs/` moved from the old
  outer root to being a sibling of `api/` inside `axiom/`).
- `python -m pytest tests -q` (run from inside `axiom/`) → 87/87 passing,
  first try after the full move + rewrite.
- Live `TestClient` e2e: login → chat (dashboard/octagonal_model present) →
  on-demand document render (`hld`) → on-demand export (`svg`) → frontend
  static serving → `/health` — all 200 from the new layout.
- Docker: rebuilt with `axiom/` as the build context (`Dockerfile`'s
  `COPY . .` and `CMD [...,"api.gateway:create_gateway_app",...]`), ran the
  container, hit `/health` and `/api/v1/solution` — confirmed working from
  the new paths, then cleaned up the test image/container.
