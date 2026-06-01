# c16b — report presentation overhaul (inline-SVG charts + restructure)     release: v0.2 · phase: De-hardcoding

## Goal
Take the reports from ~8/10 (after [c16](c16_report_quality.md)'s KPI strips / callouts / heatmaps /
provenance) to **10/10**: every report **leads with a visualization** instead of a wall of monospace
numbers, with the detail table demoted to the exact, accessible backing data. Plus the bold restructure
the chart-first layout enables (column diet, section framing, copy, cross-report nav, fuller a11y).

Splits out of c16 so each golden refresh stays reviewable (precedent: c06a/c06b). This is the
visualization commit; c16 was the additive-polish commit.

## Depends on
[c16](c16_report_quality.md) — uses its `chrome` builders (kpi_strip / callout / device strip / heatmap)
and `config [report]` thresholds. Sequence immediately after c16.

## Files
- **NEW `reports/charts.py`** — the inline-SVG toolkit (ADR-33). Deterministic, dependency-free,
  server-side SVG; fixed-precision coords; no `random`/timestamps; themed from design tokens. Vocabulary:
  `bar_chart` · `stacked_bar`/`pct_stacked_bar` · `donut` · `scatter` (x/y + bubble) · `treemap` ·
  `icicle`/flame · `histogram` · `line_chart` (multi-series across drops). Every chart is `role="img"`
  with `<title>`/`<desc>` + `aria-label`. Re-export the entry points through `reports/base.py`.
- **NEW `[chart]` block in `reports/design_tokens.toml`** — chart palette refs + default sizes (designer
  Track A); `test_design_tokens` updated.
- Each report emitter — add the flagship chart above its table:
  - `pass_gpu` — `icicle`/`treemap` of GPU time over the pass hierarchy + sorted `bar_chart` of top passes.
  - `draws_by_class` — `pct_stacked_bar` per area/drop + a `donut` of class share (colors = `--c-*`).
  - `shader_hotlist` — `scatter` complexity × cost (bubble = src bytes) + complexity `histogram`.
  - `overdraw` — `bar_chart` of reject % per RT with a threshold rule-line (config warn/alarm).
  - `instancing_opportunities` — `bar_chart` of est. wasted indices for the top meshes.
  - `trend_table` — multi-drop `line_chart` per KPI (the lead; table stays below).
  - `dashboard` (`reports/dashboard.py`) — small-multiples: a mini chart per card.
- **Restructure**: shader_hotlist 13 cols → primary set + a collapsible `<details>` "secondary metrics";
  audit the other wide tables. `section_card` framing + `rdc-sticky-h2` across multi-section reports.
  `rdc-copy-button` on copyable IDs (mesh hash / shader id / pass path). Dashboard card **insight
  subtitles** ("why it matters" + top finding + drill) + cross-report nav. Fill-or-hide the instancing
  "material batching" empty section.
- **Accessibility**: `<caption>` + `scope="col"` on `th`; non-color-only status glyphs; the SVG
  `role/title/desc`; re-verify print + reduced-motion.
- **NEW `tests/test_charts.py`** — golden-independent: determinism (same input → same bytes), SVG
  structure, token theming, empty-series → safe `''`. Per-report charts are covered transitively by
  `test_parity`; the column-diet `<details>` presence is asserted.

## Changes
Output-changing → **refresh the golden snapshot in this PR** and review the diff page-by-page (ADR-23).
Data extraction is untouched → `test_parquet_parity` stays green with no `digests.json` refresh (§21.9).

## Done when
- Each report renders its flagship chart (inline SVG) above the detail table; the table remains.
- `charts.py` output is byte-deterministic (rendered twice → identical) and contains no `random`/timestamp;
  `test_charts` green.
- shader_hotlist primary table is the diet set with a collapsible "secondary metrics" `<details>`.
- Golden refreshed + reviewed; `test_parity` green against the new golden; `test_parquet_parity` unchanged.
- `bobframes smoke` (render-only, 9 pages, lint clean) exit 0.

## Closes
**G-15 (report info-design overhaul)** · report-polish items from [QUALITY_GATES §21.1g](../../reference/QUALITY_GATES.md).
Builds on [c16](c16_report_quality.md) (ADR-32) + the chart model (ADR-33).
