# c16e — multi-run model: per-run truth (kill the cumulative-union flaw)     release: v0.2 · phase: De-hardcoding

## Goal
Make every report tell the truth about a **single chosen run** (default: the newest), instead of
silently **unioning data across all runs**. The real Perf ingest (2 runs x 7 areas) exposed the flaw:
work that was *fixed/removed in the newer run still shows up* because the reports aggregate every
discovered drop into one cumulative figure. Examples observed:
- **dashboard KPIs**: "total draws 11,424" is run1 + run2 **summed** (and avg/frame divides by all 14
  frames across both runs) - it is not any real run's draw count.
- **instancing_opportunities**: a mesh repeated 9x in run1 but **removed in run2** is still listed as a
  live instancing candidate (it survives in `per_mesh` from run1's draws).
- **draws_by_class** donut / **shader_hotlist** / **pass_gpu** / **overdraw**: same shape - the primary
  item set + headline numbers are the union of all runs, so resolved items linger.

This is a **data-model** fix, not cosmetics. The multi-run *comparison* already exists and stays
(`trend_table` cross-run matrix + A/B pair mode); c16e fixes the **single-state reports + dashboard**
so "current state" means one run, and prior runs are *baselines for delta*, never merged into the
current figure. (The run-switching / comparison **UX** is the sibling commit [c16f](c16f_multirun_ux.md).)

## Depends on
The report family ([c16](c16_report_quality.md)/[c16b](c16b_report_viz.md)/[c16c](c16c_report_restructure.md)/[c16d](c16d_report_aesthetics.md)),
the existing A/B + trend machinery (`reports/ab.py`, `reports/discovery.py` `discover_drops` /
`ok_capture_set` / `resolve_drop_set`, `chrome.ab_picker`). Surfaced by the Perf real-ingest (R-17/D-12 session).

## The run model (to be frozen as ADR-35)
- A report is rendered **for one CURRENT run** (a `(drop_date, drop_label)`), default = newest per area.
- The CURRENT run's contents are the **reported truth**: the candidate/item set (meshes, shaders,
  passes, RTs, draw-class counts) and every headline KPI are computed from the CURRENT run **only**.
- Prior runs are **baselines for delta/trend context** - shown as comparison columns / deltas / the
  `trend_table` matrix, **never summed into a "current" number**.
- An item present in a baseline but **absent in the current run is NOT a live candidate**. It is either
  dropped from the candidate list or surfaced in a clearly-separated, positively-framed **"resolved
  since <baseline>"** section (a win: the team removed it) - never mixed into the live list.
- `trend_table` is unchanged in intent (it IS the across-run view) but must stay consistent with the
  model: it compares per-run snapshots, it does not define "current".

## Scope
1. **Anchor reports to the current run.** Add a single resolver (e.g. `base.current_run(root, drops)` /
   `reports/discovery.py`) returning the current `(date,label)` (newest, or an override for c16f).
   Route the single-state reports' **primary aggregation** through it:
   - `dashboard._global_kpis` + the per-card aggregations (`_top_areas_gpu`, `_per_area_draws`,
     `_top_meshes`, `_top_passes`, `_top_shaders`, `_worst_overdraw`): compute from the **current run**,
     not summed across all drops. (Per-area avg draws/frame from c16's fix stays - just scoped to the run.)
   - `instancing_opportunities`: the `per_mesh` candidate set = meshes drawn **in the current run**;
     keep per-drop repeat columns as trend context for those meshes.
   - `draws_by_class`: donut + headline reflect the current run; the per-(area,drop) table stays as the
     breakdown.
   - `shader_hotlist`, `pass_gpu`, `overdraw`: primary ranked set + KPIs from the current run; historical
     columns kept as context.
2. **"Resolved since baseline" (optional, recommended).** Where it is cheap + meaningful (instancing
   meshes, shader hotlist), add a small collapsed section listing items present in the baseline but gone
   in the current run, framed as fixed/removed - clearly separated from live candidates.
3. **Current-run header.** Every report header states **which run it is for** (date + label) and how many
   total runs exist ("run 2 of 2: 2026-06-01 r110788"), so the anchor is visible. (Switching = c16f.)
4. **Keep A/B + trend_table** working: A/B already restricts to a pair (`ab is not None`); the default
   (no ab) now means "current run" rather than "union of all". `trend_table` stays the cross-run matrix.

## Constraints (do not regress)
- **Determinism / parity (ADR-6/32/33)**: still byte-deterministic; refresh the HTML golden (the
  synthetic has 2 drops, so the change is *visible* in the golden - e.g. the donut/KPIs drop to one
  run's numbers). Review page-by-page. `test_parquet_parity` stays GREEN, **no** `digests.json` refresh
  (presentation/aggregation only; extraction untouched, §21.9).
- **trend_table single-drop** path stays green (D-12 fix); **dashboard 5-KPI strip + per-area avg card**
  (this session) stay - just scoped to the current run.
- Lint ASCII-only; route data-derived text through `safe_chrome_text`; keep c16c a11y + c16d visual lang.
- The synthetic fixture should keep >=2 drops so the per-run-vs-cumulative distinction is actually
  exercised by the golden + a new test.

## Changes
Output-changing -> **refresh the golden** + review. Add tests: `current_run` resolver picks newest;
a report's headline/candidate set equals the current run's (NOT the cumulative sum) on the 2-drop
synthetic; a mesh present only in the older drop is excluded from instancing's live candidates (or in
the "resolved" section), not listed as live. Extend `test_report_structure`.

## Done when
- Dashboard + single-state reports report **one run's** numbers/items (default newest); no headline is a
  cross-run sum. Verified on the synthetic (2-drop) golden AND by eye on the real Perf data
  (instancing no longer lists run1-only meshes as live; draws-by-class donut = current run).
- Items removed in the current run do not appear as live candidates (dropped or in a "resolved" section).
- Every report header names its current run + the run count.
- `trend_table` + A/B unchanged in behavior; `test_parity` green; `test_parquet_parity` unchanged (no
  digests refresh); `bobframes smoke` (render-only, lint clean) exit 0.

## Closes
**G-19 (cumulative-union flaw: reports must report per-run truth, not the union of all runs)**. Append
**ADR-35 (the run model)**. Add **QUALITY_GATES §21.1j**. Sibling: [c16f](c16f_multirun_ux.md) (the
run-switching + comparison UX on top of this model).
