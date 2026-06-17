# v0.2.7-1 -- regression unification (per-frame) + config thresholds + ADR-46     release: v0.2.7 · phase: aggregation-consistency

> The P0 of the burndown. Resolves D-13 (D-A1): "GPU regression" was computed two contradictory ways
> -- `trend_table` on a rise in raw cross-capture TOTAL GPU (capture-count-SENSITIVE), `summary`/
> `health` on a rise in avg GPU PER FRAME (capture-count-INDEPENDENT) -- so runs of differing capture
> counts disagreed, producing wrong action items (the reason the real corpus was hand-trimmed to a
> uniform 5 captures/run). Also H-41: the per-KPI regression thresholds were baked in `trend_table.KPIS`
> while the hero count read config, so `.bobframes.toml` only moved one path. Drafts **ADR-46** (the
> canonical aggregation policy). GOLDEN-AFFECTING (trend_table.html only).

## Goal
Make the trend table read every KPI PER FRAME (so its regression is capture-count-independent and on
the SAME basis the health verdict uses) and source every regression threshold from `ReportCfg` (so
`.bobframes.toml` moves BOTH the heatmap alarm cells and the hero regression count). The tool no longer
needs uniform capture counts.

## Scope
- **bobframes/reports/trend_table.py**
  - `KPIS` 5-tuple -> 4-tuple (drop the per-KPI regression literal); labels gain "/ frame"
    (`gpu / frame (s)`, `draws / frame`, `vbo bytes / frame`, ...). NEW `_REGRESSION_PCT_ATTR` map +
    `_threshold_for(kpi, rcfg)` source each threshold from config (gpu reuses `gpu_regression_pct`).
  - `_aggregate_frame_totals` -> returns `(sums, {area: frame_count})` (distinct captures summed = the
    per-frame denominator, matching the rows that fed the sum = the health `avg_gpu_per_frame` basis).
  - `build`: keep `per_drop_ft_raw` (raw sums, for the labeled total hero) + `per_drop_frames`; build
    `per_drop_ft` per-frame via `base.per_frame(v, frames)` (no-op when frames<=1 -> single-capture
    byte-identical). Matrices, deltas, regression count, biggest-regression ALL read `per_drop_ft`
    (per-frame). Hero leads `gpu / frame (s)` (pooled micro = total/total-frames, the summary-headline
    basis) + a labeled `total gpu (s) over captures`; `gpu / frame delta (s)`; regression count + the
    biggest-regression tone use `_threshold_for` per KPI. Every `KPIS` unpack site updated (5->4 reshape;
    `_single_drop_matrix`, the TOC loop, the matrix-render loop, the hero + biggest-regression loops).
  - NEW `_fmt_value(kpi, v)`: per-frame means render as floats (gpu 4dp, draws/switches 1dp, byte rates
    rounded to int); replaces the old int/float `_INT_KPIS` switch.
- **bobframes/config.py** -- `ReportCfg` gains `draws_regression_pct` (10), `vbo_regression_pct` (15),
  `ibo_regression_pct` (15), `program_switches_regression_pct` (20); wired in `from_dict`. Defaults
  reproduce the old KPIS literals.
- **bobframes/_default_config.toml** -- document the four new `[report]` keys.
- **docs/plan/DECISIONS.md** -- append **ADR-46** (the canonical aggregation policy + naming convention).
- **Tests:** NEW `tests/test_trend_regression_basis.py` (3): per-frame regression ignores capture count
  (7-vs-5 at equal per-frame cost -> 0 regressions, was a false +40%); a real per-frame rise flags; a
  `.bobframes.toml gpu_regression_pct=50` suppresses it (H-41 config moves it). `test_config` defaults
  extended (+4 keys). `test_report_polish` single-drop label updated `latest gpu (s)` -> `gpu / frame (s)`.

## Constraints
- Per-frame via `base.per_frame` ONLY (never a bare `/`) -> single-capture data byte-identical.
- Config defaults == old literals (asserted) -> default render changes only by the per-frame basis, not
  by a threshold shift.
- Data path FROZEN: `golden_parquet` + `_pagedata` BYTE-UNCHANGED (NO `make_parquet_golden`).

## Done when
- A 7-vs-5-capture run at equal per-frame cost -> trend regression count 0 (was +40% false). ✔
- Trend GPU regression is per-frame, same basis as `health` (both per-frame %change vs `gpu_regression_pct`). ✔
- `.bobframes.toml gpu_regression_pct=50` moves the trend regression count. ✔
- `KPIS` literals removed; config defaults reproduce 10/10/15/15/20. ✔
- Golden refresh confined to `trend_table.html`; full `-m "not browser"` green. ✔

## As-built (DONE 2026-06-17)
- All scope landed as written. `trend_table` now per-frames every KPI at the `per_drop_ft` seam; the
  hero leads `gpu / frame (s)` (synthetic: 0.0355 = 0.177 / 5 frames) + a labeled total; thresholds are
  config-sourced via `_threshold_for`.
- PROVEN: NEW `test_trend_regression_basis` (3) green -- the 7-vs-5 equal-per-frame tree reports **0**
  regressions (pre-fix: a false flag from raw totals); a 0.10->0.13 per-frame rise flags under the
  default 10%; `gpu_regression_pct=50` in `.bobframes.toml` suppresses it (H-41 proven). `test_config`
  defaults +4 keys. `test_report_polish` single-drop label updated.
- GOLDEN: HTML-only, refresh confined to `trend_table.html` (render golden + 3 package twins);
  `golden_parquet` + `_pagedata` BYTE-UNCHANGED (NO `make_parquet_golden`). Baked on the canonical
  `.venv` (py3.12/pyarrow21, ADR-11): `make_golden` + `make_package_golden`.
- Suite: **358 passed**, 1 deselected (browser), up from 355 (+3). ADR-46 appended. FINDINGS D-13 +
  HARDCODE H-41 ticked. Browser visual pass on the trend page recommended before the PR (label/number
  change only; not run unattended).

## Next
v0.2.7-2 (cross-report GPU consistency + Mean labels; D-14 + D-16 + Q-10). GOLDEN-AFFECTING.
