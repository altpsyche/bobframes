# Changelog

Changes to this project are documented here, newest first.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.8] - 2026-06-24

A guided local-web control panel (`bobframes ui`) for QA and product teammates who are not comfortable
in a terminal. Zero new runtime dependency (stdlib `http.server` only) and no report-output change --
the panel drives the existing verbs and emits no report HTML, so the rendered HTML and parquet digests
stay byte-identical on the same captures. No schema change (still schema 3). `_version` 0.2.7 -> 0.2.8.

### Added
- `bobframes ui`: a zero-dependency local-web control panel that drives the whole pipeline from a
  browser (ADR-47). It detects the RenderDoc tools and discovers capture drops, runs ingest /
  re-generate / package / A-B as subprocesses with live per-capture progress streamed over Server-Sent
  Events, opens or serves the rendered report, applies accent theming to a re-render, and can scaffold a
  convention-correct capture folder. Server-rendered HTML + vanilla JS -- no framework, no build step,
  no client router (the hard governance line in ADR-47). Binds `127.0.0.1` only and gates every
  `/api/*` call with a per-session token. Install with `pipx install bobframes`, then run `bobframes ui`.

### Changed
- The static preview server body moved from `cli._cmd_serve` into a reusable `serve.make_server` /
  `serve.serve_forever` so the panel's background serve and the `bobframes serve` verb share it; the
  `serve` verb's behavior is unchanged.
- The control panel's JS and CSS are now served as static files (`bobframes/ui/assets/panel.{js,css}`,
  at `GET /panel.js` / `GET /panel.css`) instead of being embedded in a Python string -- so the client
  is a real file that `node --check`/lint can validate (no build step; still no framework or router).

### Tests / CI
- Added an automated guard that the panel JS parses and runs: a `node --check` gate (a pytest test +
  an unconditional CI step) and an opt-in `browser`-marked headless smoke that drives the live panel in
  Chrome and asserts it populates -- closing the gap that let a broken `<script>` ship undetected.

## [0.2.7] - 2026-06-24

An aggregation-consistency pass plus four report/sharing correctness fixes. Every KPI now names its
estimator and rate KPIs read on one per-frame basis, so the same metric agrees across the summary,
dashboard, and trend. No schema change (still schema 3); parquet digests stay byte-identical on the
same captures. `_version` 0.2.6 -> 0.2.7.

### Changed
- One canonical aggregation policy (ADR-46): every rendered KPI label names its estimator precisely --
  `Pooled mean`, `Mean (per area)`, `Median`, `Total` -- and never a bare "avg". Rate KPIs (GPU, draws)
  read per-frame on a single basis, so the same area's GPU now reads identically across the summary,
  dashboard, and trend (previously e.g. `0.0356`/frame on the summary vs a raw `0.178` total on the
  dashboard with no bridge). A naming gate (`test_no_vague_estimator_labels`) fails the build on any
  vague estimator word. (D-13..D-16, Q-10..Q-13)
- Regression detection unified on the per-frame basis with config-driven thresholds: `trend_table`
  reads every KPI per frame, so a regression flag is capture-count-independent and agrees with the
  build-health verdict (a 7-vs-5-capture run no longer reports a false +40%); the per-KPI thresholds
  (`draws`/`vbo`/`ibo`/`program_switches`) move from code literals to the `[report]` config, with
  defaults that reproduce the prior values. (H-41)
- `draws_by_class` ratios use `statistics.median` (was the upper-middle `sorted[n//2]`, an off-by-one
  on even N).
- `aggregates.frame_counts` is the single owner of every per-(drop, area) frame count; when the
  GPU/draws denominator and the entity-rate denominator legitimately differ (a capture that replayed
  but exported partial entity rows), the divergence is logged as a WARNING rather than silently
  normalized away.

### Fixed
- Run-selector dropdown did nothing on every report: the component JS runs in `<head>`, so the custom
  element upgraded before its child `<select>` had parsed; initialization now defers to
  `DOMContentLoaded`. (R-20)
- Exported standalone one-pager carried dead tree-relative navigation -- a run dropdown pointing at
  siblings not in the bundle, a breadcrumb, the dashboard link, and a "viewing an older run" banner.
  The detached summary now strips them; the in-tree summary keeps its working navigation. (R-21)
- Older-run report pages showed cross-drop graphs and tables spanning all runs, including ones newer
  than the page's own run. Cross-drop renderers now scope to run history (up to and including the
  current run) while the run picker keeps the full list. (R-22)

## [0.2.6] - 2026-06-06

A build-health one-pager, a shareable `package` bundle, a server-side component system, and a full visual
redesign. No schema change (still schema 3); parquet digests stay byte-identical to 0.1.0/0.2.0 on the same
captures. Per ADR-43 there is no standalone 0.2.5 -- this release carries the c16q-c16x foundation AND the
redesign, so `_version` jumps `0.2.0 -> 0.2.6`.

### Added
- Build-health one-pager (`bobframes report summary`): a presentation-independent verdict/trend module
  (`health.py` -- ordered OK<UNKNOWN<AT_RISK<ALARM so a real alarm is never masked yet missing data is
  never a false green) feeding a print-first exec summary (verdict bar, averaged KPIs with vs-prior pills +
  sparklines, a baseline-gated movement card, a worst-first by-area table). (ADR-39)
- `bobframes package`: a non-mutating transform of a rendered tree into a shareable `<project>-<date>-report.zip`
  (reproducible bytes) + a standalone self-contained `summary.html`. `--shared-assets` (the default) dedupes
  chrome into `_assets/` linked per page (built at the render seam, not by scraping HTML); `--inline` opts out;
  `--redact` scrubs device/host provenance at the data seam (whole-tree drop-sidecars excluded). (ADR-40/41)
- Server-side component system (`reports/chrome.py`): an escape-by-construction element builder (`el`/`raw`/
  `el_void`/`classes`), a normalized table-component family (`Column`/`data_table`/`static_table` + a virtual
  `table_controls`/`virtual_host`/`virtual_table_section` host), a delta-column factory, and a token-validity
  guard (`undefined_tokens()` -- a typo'd `var(--x)` is a CI failure + a `preview` warning). CSS/JS now live as
  real `reports/assets/*.{css,js}` files. A `bobframes preview` gallery documents every component. (ADR-42)
- User theme override for pip installs: a `.bobframes.toml [theme]` section + `render/preview --accent`/
  `--accent-data` flags re-hue the accent/status/chart colors WITHOUT editing the packaged `design_tokens.toml`
  (deep-merged through the existing config cascade; color-key allowlist; ASCII/injection-guarded). `export-tokens
  --theme-template` emits a paste-ready starter; `--watch` polls `.bobframes.toml`. (ADR-45)
- Dev-only screenshot harness `tools/shoot.py` (headless-Chrome over CDP, light/dark/print; not shipped) + a
  `-m browser` opt-in matrix + a dependency-free oklch->WCAG contrast test, for the redesign's visual gate.

### Changed
- Visual redesign anchored on shadcn/ui + Grafana density (ADR-43/44): a neutral grayscale palette (chroma 0),
  WCAG-AA tertiary text, FLAT border-led surfaces (reverses the ADR-34 depth -- a 1px border + a `--radius`
  6/8/10 token scale replaces the elevation shadows + the hardcoded 2/3/4px radii), `:focus-visible` rings,
  reduced-motion-safe `:active`, container-query responsive, and a print pass. Restrained type tune with hero
  numerals scoped to the summary one-pager; Grafana-dense rows/cards everywhere else; the catalog/drill data
  browser widened (max data-per-screen).
- "Everything is a component": the summary, dashboard minis, the 6 detail reports, and the catalog/drill virtual
  hosts all render through the component family; the remaining hand-written chrome leaves were migrated onto `el`
  (the bespoke-markup long-tail is closed -- only the fixed page scaffold remains, by necessity). `data_table`
  normalizes the previously hand-written report tables (the visual-parity gate is intentionally replaced by a
  structural + data-preservation gate per ADR-43).
- Per-frame normalization for multi-capture runs (instancing repeat + shader cost read per distinct capture,
  no-op for 1-capture data so it stays byte-identical) and a single `aggregates.py` data layer feeding the
  dashboard/reports/verdict so they cannot disagree.
- Run model + sharing surfaced in the root catalog (build-health + dashboard chips, A/B pair lists).

### Fixed
- Single-drop trend-table crash (`'str' object has no attribute 'get'`); `--force` rotation-backup
  double-counting in the catalog + global-entities walkers (canonical-basename reconstruction).
- WCAG-AA contrast on tertiary text; print no longer hugs the paper edge.

## [0.2.0] - 2026-06-03

De-hardcoding + a full report overhaul. No schema change (still schema 3); extraction output is stable
where the pipeline is unchanged, so parquet digests are byte-identical to 0.1.0 on the same captures.

### Added
- Inline-SVG chart toolkit (`reports/charts.py`): a flagship chart per report (pass-GPU treemap,
  draws-by-class donut, shader complexity-vs-cost scatter, overdraw reject-rate bars, instancing
  wasted-index bars, per-KPI trend lines), deterministic and dependency-free (no `random`/`Date`).
- Report design language: hero KPI strip, callouts with config-driven severity, provenance/device
  strip, section cards, sticky section headers, copy buttons on long IDs, vendored Inter subset font
  (offline, base64-inlined), and an auto-tint heatmap on ranked numeric columns.
- Run model: per-run truth (each report names "run N of M"), a run picker, A/B compare, and a trend
  table across runs; older runs are pre-rendered up to a configurable limit.
- One unified `rdc-table` engine (progressive enhancement, two modes): server-baked `static` for reports
  (JS-off / print / Ctrl-F / golden all hold) and windowed `virtual` for the catalog + per-drop drill.
  Shared natural-numeric sort, type-split, heatmap, column groups, search/filter, controllable cell
  truncation with hover-reveal, and full sort/filter a11y (aria-sort + keyboard-operable headers + a
  labelled filter input) across both modes.
- TOML config (`.bobframes.toml`, `[report]`/`[pipeline]` sections), `design_tokens.toml` token system,
  and a state-capable draw classifier driven by table columns.
- Reports cache with a SHA256 sidecar (corrupt/missing/mismatch falls back to a live scan, never
  silent-empty); manifest schema-version guard (`ingest --force` hint on mismatch).

### Changed
- Catalog + drill readability: roomier rows, type-split mono/sans, and the heavy per-table row data moved
  out of the HTML into `_pagedata/*.js` companions (the ~21 MB time-to-interactive fix) loaded via a
  file://-safe `<script defer src>`.
- External tool resolution + clearer pipeline error messages and exit codes; environment variables
  renamed `RDC_*` -> `BOBFRAMES_*` (one-release legacy fallback with a deprecation warning).
- Project paths, the report registry, and the drill-size budget are configurable rather than hardcoded.

## [0.1.0] - 2026-05-31

First standalone release. v1 is Windows-only (the replay stage drives `qrenderdoc`).

### Added
- Single `bobframes` binary with subcommands `ingest`, `render`, `ab`, `report`, `catalog`, `lint`,
  `check`, `serve`, `smoke`, and `version`. Positional `root` (default `.`) across verbs; long-flag
  only; exit codes `0`/`1`/`2`/`3`/`4`. stdlib `logging` at INFO by default, `--verbose` for DEBUG,
  `[HH:MM:SS]` line format (G-8).
- Replay script located via `importlib.resources` (`bobframes.replay.replay_script_path`) so replay
  works from an installed wheel, not just an in-tree checkout.
- Reliability hardening: atomic writes for `_manifest.json`, Parquet+CSV pairs, and `done.marker`
  (`.tmp` + `os.replace`, rollback on failure); process-tree kill (`taskkill /T /F`) when a
  `qrenderdoc` replay times out; per-capture replay-failure isolation
  (`capture_status='replay_failed'` instead of aborting the whole drop); subprocess stderr logged on
  convert-timeout and on every parse; manifest provenance fields `tool_versions` and `host_info`.
- Test gates: golden-snapshot parity, schema regression, determinism, performance, and a replay
  column-drift guard against `schemas.py` (H-6); mocked-subprocess tests for the hardening branches
  the GPU-less runner cannot exercise; a data-driven `smoke` (render-only against a bundled synthetic
  fixture by default); unit tests for stable keys, schemas, and drop discovery.
- GitHub Actions CI across a Windows / Python / pyarrow matrix, with a tag-gated PyPI publish job.

### Changed
- **Stable-key format upgrade:** stable keys now carry a `KEY_VERSION = 1` version byte in the hash
  input. Keys produced before this release are not comparable with `0.1.0` keys; rebuild affected
  data with `bobframes ingest --force`. `KEY_VERSION` bumps on any future key-derivation rule change.
- Timestamps unified to a single UTC `now_iso()` helper (`bobframes.manifest.now_iso`); the
  local-time variant in `reports/cli` was dropped.

### Removed
- The project-embedded `_analysis` package. `python -m _analysis.run` and the other
  `python -m _analysis.*` entry points no longer work; switch to the `bobframes` commands (see the
  migration table in the README). This is a hard rename with no compatibility shim.

[Unreleased]: https://github.com/altpsyche/bobframes/compare/v0.2.8...HEAD
[0.2.8]: https://github.com/altpsyche/bobframes/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/altpsyche/bobframes/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/altpsyche/bobframes/compare/v0.2.0...v0.2.6
[0.2.0]: https://github.com/altpsyche/bobframes/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/altpsyche/bobframes/releases/tag/v0.1.0
