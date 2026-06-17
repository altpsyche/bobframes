# v0.2.7-2 -- cross-report GPU consistency + "Mean" labels (summary / dashboard / pass_gpu)     release: v0.2.7 · phase: aggregation-consistency

> The VISIBLE win -- directly answers the user's complaint ("the averages are very confusing") and the
> directive to name the estimator precisely ("Mean", not "avg"). Resolves D-14 (headline pooled mean
> wears the same label as the per-area column), D-16 (the same area's GPU read 0.0356 on summary but
> 0.178 on the dashboard card, no bridge), and Q-10 (pass_gpu showed a cross-capture TOTAL where the
> rest show a per-frame mean + a wrong "costliest capture" callout). Rides ADR-46. GOLDEN-AFFECTING.

## Goal
For any area, the per-frame GPU number reads the SAME across summary, dashboard, and (via v027_1) trend;
every label names its estimator + population precisely ("pooled mean" / "mean ... (per area)" /
"total ... over captures"), never "avg"; raw totals are always labeled as totals.

## Scope
- **bobframes/reports/summary.py (D-14)** -- headline KPIs relabeled `pooled mean draws / frame` /
  `pooled mean gpu / frame`, notes disclose `pooled across N frames - ... total`. By-area columns ->
  `mean draws / frame (per area)` / `mean gpu / frame (per area)` with `title=` spelling out
  "area X / area captured frames". By-area `caption` discloses the relationship ("each area's own
  per-frame mean; the headline pools all captured frames").
- **bobframes/reports/dashboard.py (D-16)** -- `_global_kpis` hero relabeled: leads `pooled mean
  gpu / frame (s)` + `total gpu (s) over captures`, `pooled mean draws / frame` +
  `total draws over captures`. The "trend table" CARD now LEADS with the per-frame mean (`_top_areas_gpu[4]`,
  matching summary) in both the bar chart (`gpu / frame per area`) and the table (`mean gpu / frame`),
  with the raw total beside it as the labeled bridge (`total gpu (s)`); `mean draws / frame`; caption +
  sub reworded.
- **bobframes/reports/pass_gpu.py (Q-10)** -- hero leads `gpu / frame (s)` (pooled = total GPU / the
  run's captured frames, via `aggregates.frame_counts`) + `total gpu (s) over captures`. The
  heaviest-pass callout "GPU on the costliest capture" (wrong -- `_cur_gpu` sums over all ok captures)
  -> "GPU summed over the run's captures". The per-drop comparison row labeled `drops (total / drop)`.
- **Tests** -- `test_summary` (headline labels, By-area caption/columns, reconcile) + `test_report_structure`
  (dashboard KPI order/pairing, mini hover title) + `test_run_model` (total-draws label) updated to the
  new labels; NEW `test_report_structure.test_cross_report_per_frame_gpu_consistent` (D-16: the top
  area's per-frame GPU string appears IDENTICALLY on dashboard + summary).

## Done when
- A given area's per-frame GPU is byte-identical across summary + dashboard (new test). ✔
- No "avg"/"average" in the touched reports' rendered labels; estimators named. ✔
- pass_gpu hero per-framed + paired total; callout wording fixed. ✔
- Golden refresh confined to summary/index(dashboard)/pass_gpu (+ per-run twins) + the v027_1 trend;
  `golden_parquet`/`_pagedata` BYTE-UNCHANGED; full `-m "not browser"` green. ✔

## As-built (DONE 2026-06-17)
- All scope landed. Synthetic: dashboard card + summary By-area now BOTH read `0.0355` per-frame for
  District 01 (was 0.0356 vs 0.178); the raw total rides alongside as `total gpu (s)`.
- **Deviation (ADR-23 documented):** the plan listed a separate one-line "basis legend" element on each
  report. Dropped as redundant -- every label now names estimator + population (ADR-46), and the
  summary By-area caption states the pooled-vs-per-area relationship explicitly, so a separate legend
  would only repeat the labels while adding golden surface. Disclosure is via the labels + that caption.
- GOLDEN: HTML-only; refresh confined to summary.html, _reports/index.html (dashboard), pass_gpu.html
  (+ the per-run 2026-05-27 twins) + the v027_1 trend_table.html; `golden_parquet` + `_pagedata`
  BYTE-UNCHANGED (NO `make_parquet_golden`). Baked on the canonical `.venv` (`make_golden` +
  `make_package_golden`).
- Tests: 6 structural asserts updated to the new labels; NEW cross-report consistency test green. Suite
  **358 passed**, 1 deselected. FINDINGS D-14 + D-16 + Q-10 ticked. Browser visual pass recommended
  before the PR (label/number change; not run unattended).

## Next
v0.2.7-3 (median + total-basis disclosure; Q-11 `statistics.median` + "Median ..." labels, Q-12
"total draws" current-run scope + per-frame lead). GOLDEN-AFFECTING.
