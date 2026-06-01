# c16b — report presentation overhaul (inline-SVG charts + restructure)     release: v0.2 · phase: De-hardcoding

## Goal
Take the reports from ~8/10 (after [c16](c16_report_quality.md)'s KPI strips / callouts / heatmaps /
provenance) toward **10/10**: every report **leads with a visualization** instead of a wall of monospace
numbers, with the detail table demoted to the exact, accessible backing data.

Splits out of c16 so each golden refresh stays reviewable (precedent: c06a/c06b). This is the
visualization commit; c16 was the additive-polish commit.

**Scope (narrowed in execution, user-chosen):** c16b ships the **chart slice** + the one restructure
item the chart-first layout immediately needs (the shader_hotlist column diet). The heavier
restructure (section framing, sticky-h2 spread, copy buttons, dashboard small-multiples, fuller a11y,
fill-or-hide) is split into **[c16c](c16c_report_restructure.md)** so the golden diff stays reviewable
page-by-page (ADR-23: documented scoping, not narrowing). See "Deferred to c16c" below.

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
- **Column diet (kept in c16b)**: shader_hotlist 13 cols → 7-col primary set
  (shader / complexity / uses / cost proxy / flags / src) + a collapsible `<details class="secondary-
  metrics">` second table (branches / loops / discards / dfdx-dfdy / tex samples / src bytes).
- **Chart a11y (intrinsic to the toolkit)**: every chart is `role="img"` + `<title>`/`<desc>` +
  `aria-label`; static vector (print + reduced-motion safe). All emitted text is ASCII (scrubbed via
  `safe_chrome_text`) so data-derived labels can never trip the page lint.
- **NEW `tests/test_charts.py`** — golden-independent: determinism (same input → same bytes), SVG
  structure (role/title/desc), token theming, empty-series → safe `''`, ASCII guard. Per-report charts
  are covered transitively by `test_parity`; the column-diet `<details>` presence is asserted.
- **NEW `tests/make_golden.py`** — repeatable HTML-golden refresh (render_fresh → normalize ts → LF),
  mirroring `make_preview_golden` / `make_parquet_golden`.

### Deferred to [c16c](c16c_report_restructure.md)
`section_card` framing + `rdc-sticky-h2` spread across multi-section reports; `rdc-copy-button` on
copyable IDs (mesh hash / shader id / pass path); dashboard **small-multiples** (mini chart per card) +
insight subtitles + cross-report nav; fill-or-hide the instancing "material batching" empty section;
fuller a11y (`<caption>` + `scope="col"` on `th`, non-color status glyphs). The chart toolkit's
`icicle`/`stacked_bar` primitives ship in c16b (unit-tested) and are consumed there.

## Changes
Output-changing → **refresh the golden snapshot in this PR** and review the diff page-by-page (ADR-23).
Data extraction is untouched → `test_parquet_parity` stays green with no `digests.json` refresh (§21.9).

## Done when
- Each of the 6 reports renders its flagship chart (inline SVG) above the detail table; the table remains.
- `charts.py` output is byte-deterministic (rendered twice → identical) and contains no `random`/timestamp;
  `test_charts` green.
- shader_hotlist primary table is the 7-col diet set with a collapsible "secondary metrics" `<details>`.
- Golden refreshed + reviewed; `test_parity` green against the new golden; `test_parquet_parity` unchanged.
- `bobframes smoke` (render-only, 9 pages, lint clean) exit 0.
- [c16c](c16c_report_restructure.md) authored; STATE/INDEX rows added; deferred restructure recorded above.

## Closes
**G-15 (report info-design overhaul) — charts half** (the restructure half is [c16c](c16c_report_restructure.md)) ·
[QUALITY_GATES §21.1g](../../reference/QUALITY_GATES.md). Builds on [c16](c16_report_quality.md) (ADR-32) +
the chart model (ADR-33).
