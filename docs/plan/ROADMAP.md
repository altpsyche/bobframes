# BobFrames — roadmap (v0.2 → v0.6+)

> The "where we are going" doc. Carved from [V02_PLANNING_PROMPT.md](V02_PLANNING_PROMPT.md) and the
> strategic decisions taken in the 2026-05-31 planning session. **Living** (unlike the frozen
> ARCHITECTURE/DECISIONS). The route lives in [MIGRATION.md](MIGRATION.md); per-commit detail in
> `commits/vXX/`; progress in [STATE.md](STATE.md). This file states the *why* and the *grading bar*.

## Vision

**The best RenderDoc data + reporting tool for a wide audience** — graphics engineers, tech artists,
perf leads/producers, and CI/automation — across three breadth axes (graphics API, engine, platform).
v0.1.0 shipped Windows-only / OpenGL-only / Unreal-tuned. v0.2+ widens each axis behind the
golden-parity gate, and fills the cheap high-leverage audience gaps first.

"Best" is **measured, not asserted** — every phase is graded against the acceptance signals below.

## Measurable success (acceptance signals)

| Persona | "Best" means | Acceptance signal (gradable) | Lands |
|---|---|---|---|
| **Breadth** | ≥2 graphics APIs, ≥2 engines, ≥1 non-Windows OS | GL **and** Vulkan goldens both green; UE **and** generic presets both green; `bobframes check` resolves tools on Linux/macOS | v0.4 / v0.5 / v0.6 |
| **Engineers** | isolated stages, integrity verify, queryable Parquet, schema introspection, shader-source links | `parse`/`replay`/`verify`/`schema` verbs green; `query` works under the `[query]` extra; shader links resolve in reports | v0.3 / v0.4 |
| **Artists** | mesh/material workflow, overdraw heatmap, per-material trend, texture usage | overdraw-heatmap + mesh/material + texture-usage reports render + lint-clean + golden | v0.4 |
| **Leads** | configurable regression gating, historical multi-drop dashboard, custom KPIs | `report trend --gate` returns exit 1 from config-driven thresholds; multi-drop historical dashboard renders | v0.3 / v0.6 |
| **CI/automation** | `--json` everywhere, exit-code gating, `--dry-run`, `export`, `diff`, isolated stages | every verb emits versioned JSON under `--json`; gating exit codes; `--dry-run` no-ops cleanly | v0.3 |
| **Adoptability** | install + first report vs a public sample in <5 min; documented extension points | published sample asset + a per-persona quickstart; a plugin/extension guide | v0.4 / v0.6 |

## Phasing

Each entry: **theme · commits · FINDINGS/HARDCODE closed · success criteria served · deps.** Every
commit stays behind the golden HTML parity gate ([QUALITY_GATES](reference/QUALITY_GATES.md); byte
parity pinned to the canonical cell py3.12+pa21, [ADR-11](DECISIONS.md)).

### v0.2 — De-hardcoding foundation (M)
- **Commits:** c04–c10, c16 (already spec'd in `commits/v02/`).
- **Closes:** D-1 · H-1..H-23, H-30 · Q-3 · R-13 · Q-9.
- **Serves:** the foundation map — c05 → data-driven API columns + report auto-discovery; c06 →
  cross-platform tool location; c07 → configurable thresholds/timeouts/regex; c09 → engine breadth.
- **Schema:** no `SCHEMA_VERSION` bump. Output byte-identical.
- **Deps:** v0.1 shipped. **Unblocks everything below.**

### v0.2.5 — report packaging + exec one-pager (S) — shareability + a non-technical read
- **Commits:** c16q `health.py` verdict + `summary.py` one-pager -> c16r `head_assets` seam -> c16s
  `package` verb + shareable bundle -> c16t shared-assets default -> c16u `--redact` -> c16v multi-capture
  per-frame normalization -> c16w close-out.
- **Closes:** G-24 (no exec one-pager / health verdict). Opens G-25/G-26/G-27 (per-area verdict +
  `[gating]` config; `aggregates.py`; dashboard-hero verdict convergence) + H-40 (shader `*1.25` band).
- **Serves:** the **leads/producers** "is my frame healthy" one-screen read, and the **adoptability**
  "hand a colleague a shareable artifact" gap. Seeds the **CI** verdict contract (`health.Verdict`) that
  c20 `--json` + c21 `report --gate` consume.
- **Schema:** none. Default `render` output byte-identical (ADR-37); the one-pager adds a golden page +
  an intentional index/dashboard nav refresh; `package` is a non-mutating transform with its own gate.
- **Deps:** v0.2 (ReportCfg thresholds, run model, the chrome primitives). **Unblocks** the c20/c21
  verdict consumers. See [v025_packaging_and_onepager_proposal.md](v025_packaging_and_onepager_proposal.md),
  ADR-39/40/41.

### v0.2.9 — `bobframes ui` panel polish (S) — adoptability follow-up to v0.2.8
- **Commits:** v029_0..13, each a review finding its own commit. MED: cancel a running job,
  write-starter-config button, root-path input, honest ingest estimate, `aria-live`, A/B all-pair links.
  LOW: reveal-in-folder, log copy/download, prune job registry, serve list/stop, RUN-col dedup, favicon,
  narrow-width.
- **Serves:** the QA/product persona — removes the panel's first-run dead-ends + unstoppable-job gap.
- **Schema:** none; the panel emits no report HTML — **golden gate byte-unchanged throughout**.
- **Deps / rules:** rides ADR-47 (zero new dep, stdlib http.server, no JS framework/router/build step,
  localhost+token). Every panel-JS change is `node --check`'d + the `browser` populate-smoke re-runs
  (the v028_7/8 gate). Approved plan `~/.claude/plans/plan-a-ui-improvement-track-sharded-sky.md`.

### v0.3 — CI/automation surface (S–M) — the high-leverage next step
- **Commits:** c20 `--json` + `json_schema_version` → c21 config-driven regression gating → c22
  isolated `parse`/`replay` → c23 `--dry-run` → c24 `verify` → c25 `diff` → c26 `export`.
- **Closes:** G-9 (c20) · G-1 (c23) · G-2 (c25) · G-4 (c24) · G-5 (c26) · G-10 (c22).
- **Serves:** the CI persona end-to-end; the leads "configurable gating" criterion (c21).
- **Schema:** none. `--json` is additive to stdout — **no HTML-golden impact**.
- **Deps:** v0.2 (c07 config for gating thresholds; c10 `--project-root` for isolated stages).
- **Why first:** widest, cheapest audience; builds the substrate automated quality needs *before* the
  API epic churns schemas.

### v0.4 — Engine breadth + engineer/artist ergonomics (S–M)
- **Commits:** c27 generic + non-UE presets (per-engine fixture+golden) → c28 surface `texture_usage`
  report → c29 overdraw heatmap → c30 `schema` introspection (core) + `query` extra → c31 mesh/material
  report.
- **Closes:** D-6 (c09 unifies; c27 validates) · G-13 (c28) · partial M-1 (registry reuse).
- **Serves:** breadth ≥2 engines (UE + generic); the artist reports; the engineer queryable-Parquet
  + schema-introspection criterion.
- **Schema:** none. New reports add golden fixtures (refresh in-PR).
- **Deps:** v0.3; c09 classifier TOML; c05 `ALL_REPORTS` registry.

### v0.5 — Graphics-API adapter epic (XL)
- **Commits:** c32 `PipelineStateAdapter` refactor (GL adapter = today, parity-clean, no output
  change) → c33 data-driven class columns + extension-table mechanism (GL byte-identical) → c34 Vulkan
  extraction + fixture + golden (GL untouched) → c35 register Vulkan extension tables + `SCHEMA_VERSION`
  3→4 + dual golden refresh.
- **Closes:** H-36 (GL-only pipeline-state reads) · H-37 (`gl*_count` columns).
- **Serves:** breadth ≥2 graphics APIs (GL + Vulkan).
- **Schema:** **`SCHEMA_VERSION` 3→4 at c35** — forces a golden refresh + a bobframes MINOR (pre-1.0).
  New API columns are additive/optional extension tables; **GL output stays byte-identical** through
  c32–c34, with the bump isolated to c35.
- **Deps:** v0.4; unified-core-+-extension schema ([ADR-14](DECISIONS.md)); Vulkan first
  ([ADR-15](DECISIONS.md)).
- **Decision gates already taken:** first API = Vulkan; schema shape = unified core + per-API
  extension tables.

### v0.6+ — Cross-platform + leads + plugins (L)
- **Commits:** c36 Linux/macOS tool locator (extends c06) + non-Windows tree-kill → c37 historical/trend
  dashboard + regression alerts → c38 trusted-local plugin auto-discovery (M-1/M-2) → c39 optional
  Figma token sync.
- **Closes:** H-38 (platform process model) · M-1, M-2 (auto-discovery).
- **Serves:** breadth ≥1 non-Windows OS (c36); the leads historical-dashboard criterion (c37); the
  adoptability extension-points criterion (c38 + the plugin guide).
- **Schema:** none required (plugins may register tables via M-2, additive).
- **Deps:** v0.5; per-OS nightly real-`.rdc` lane; trusted-local plugin model
  ([ADR-19](DECISIONS.md)); cross-platform timing v0.6 ([ADR-18](DECISIONS.md)).

## Reliability / scale (measure-then-optimize, not speculative)

R-10..R-15 land opportunistically in v0.2+. The scale items are deferred until **measured**:
S-1 sequential replay (600s × N — the big one; candidate v0.6 once a real multi-capture wall-clock is
profiled), S-2 single-thread merge, S-3 catalog full scan, S-4 global_entities scan, S-5 derive
read-modify-write. None are pulled forward without a profile justifying them.

## Test strategy for multi-API / multi-engine

Repo stays data-free ([ADR-8](DECISIONS.md)); the synthetic fixture drives CI; real-`.rdc` full ingest
is self-hosted/nightly. **Each new API and each new engine needs its own synthetic fixture + golden**,
anonymized/down-sampled from a real ingest ([ADR-6](DECISIONS.md)), baked on the canonical cell
([ADR-11](DECISIONS.md), [ADR-22](DECISIONS.md)). The byte-parity gate's scope grows one fixture at a
time; functional gates run the full matrix.

## Open / deferred (recorded, not scheduled)

- **D3D12** — second-after-Vulkan; validates the adapter abstraction ([ADR-15](DECISIONS.md)).
- **Unity / Godot presets** — generic-first ships honest defaults; these land when a real `.rdc` from
  that engine exists to anonymize ([ADR-21](DECISIONS.md)).
- **`bobframes migrate`** — schema-version migration path (G-3) targeted at v1.0; v0.5/c35 documents
  `ingest --force` as the interim.
- **i18n** (H-31), **sandboxed/signed plugins** (beyond [ADR-19](DECISIONS.md)) — out of current scope.
