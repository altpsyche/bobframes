# v0.2.7-3 -- median + total-basis disclosure (draws_by_class / dashboard / instancing)     release: v0.2.7 · phase: aggregation-consistency

> Resolves Q-11 (medians presented inside an "avg" framing with an off-by-one estimator) and Q-12
> ("total draws" hero is a raw cross-capture count with no per-frame anchor). Rides ADR-46.
> GOLDEN-AFFECTING.

## Goal
Name every median estimator precisely (and compute it correctly), and pair "total draws" with a
per-frame mean -- so draws_by_class reads on the same per-frame basis as the rest of the reports.

## Scope
- **bobframes/reports/draws_by_class.py**
  - Q-11: `_compute_kpis` ratio uses `statistics.median(ratios)` (was `sorted(ratios)[len(ratios)//2]`
    -- the UPPER-middle, a latent off-by-one on an even number of areas). Label
    `prepass/opaque (med)` -> `median prepass / opaque (across areas)`.
  - Q-12: lead KPI `mean draws / frame` (= total draws / the current run's captured frames, via
    `aggregates.frame_counts`, through `base.per_frame`) + a labeled `total draws over captures`
    (was a lone `total draws`). `_compute_kpis` gains a `total_frames` param; `build` computes
    `cur_frames`. NOTE: the audit's "sums over ALL drops" sub-claim was checked and is FALSE --
    `_compute_kpis` is already called with `cur_counts` (current run); recorded honestly (ADR-23).
- **bobframes/reports/dashboard.py** -- the instancing card column `indices typ` -> `median verts`
  (the value is already `statistics.median(num_indices)`).
- **bobframes/reports/instancing_opportunities.py** -- column `indices typical` -> `median indices`;
  the chart desc + the wasted-indices title reworded `typical` -> `median` (the value is
  `statistics.median(num_indices)`).
- **Tests** -- NEW `tests/test_draws_by_class_kpis.py` (pure unit): the ratio is the true median
  (even-n: ratios {1.0, 3.0} -> 2.00, not the upper-middle 3.00); "total draws over captures" is paired
  with "mean draws / frame" (6 draws / 2 frames -> 3; single-capture no-op -> 6).

## Done when
- The prepass/opaque ratio KPI is `statistics.median`; even-n test proves it (was upper-middle). ✔
- All median labels name the estimator ("median ..."); no "typical"/"(med)" in rendered labels. ✔
- "total draws" leads with a per-frame mean + a labeled total. ✔
- Golden refresh confined to draws_by_class / index(dashboard) / instancing_opportunities (+ per-run
  twins); `golden_parquet`/`_pagedata` BYTE-UNCHANGED; full `-m "not browser"` green. ✔

## As-built (DONE 2026-06-17)
- All scope landed. `statistics.median` + the "median ..." labels across draws_by_class, the dashboard
  instancing card, and the instancing report; draws_by_class hero leads `mean draws / frame` (synthetic
  single-capture path: per_frame no-op, so the mean equals the total -- byte-stable shape, new label).
- GOLDEN: HTML-only; refresh confined to `draws_by_class.html`, `_reports/index.html`,
  `instancing_opportunities.html` (+ per-run twins); `golden_parquet` + `_pagedata` BYTE-UNCHANGED
  (NO `make_parquet_golden`). Baked on the canonical `.venv`.
- Tests: NEW `test_draws_by_class_kpis` (2) green. Suite **361 passed**, 1 deselected. FINDINGS Q-11 +
  Q-12 ticked (Q-12 text corrected re: the false all-drops claim). Browser visual pass recommended
  before the PR.

## Next
v0.2.7-4 (record Q-13 overdraw correct-as-designed + close out: QUALITY_GATES naming/parity gates,
AGGREGATION_FINDINGS resolved-by ticks, STATE; no production code).
