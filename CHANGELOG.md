# Changelog

Changes to this project are documented here, newest first.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/altpsyche/bobframes/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/altpsyche/bobframes/releases/tag/v0.1.0
