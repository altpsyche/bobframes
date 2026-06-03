# c16q — health verdict module + exec one-pager     release: v0.2.5 · phase: one-pager

> The exec/non-technical read. Adds `bobframes/health.py` (the verdict as a presentation-independent
> contract that c20/c21 will consume) and `reports/summary.py` (a print-first one-pager that renders it),
> made discoverable from the dashboard + root. ADR-39. The first v0.2.5 commit.

## Goal
A one-page build-health read for perf leads / producers, composed from existing primitives, leading with
a deterministic OK/AT-RISK/ALARM/UNKNOWN verdict that lives below presentation so `--json` (c20) and
`report --gate` (c21) consume the SAME evaluator.

## Depends on
v0.2.0 shipped (c16p). Reuses `dashboard.py` current-run helpers, `chrome` primitives (summary_bar,
callout, kpi_strip, section_card, provenance_strip), `discovery.RunContext` (ADR-35), config `ReportCfg`.

## Scope
1. **`bobframes/health.py`** (peer of the future jsonout/export, NOT under `reports/`):
   `State(OK/AT_RISK/ALARM/UNKNOWN)`, `Trigger`, `AreaMetrics` (one area's inputs: overdraw/shader/mesh +
   avg draws/frame + avg gpu/frame), `HealthMetrics(per_area: dict[str,AreaMetrics], has_baseline)`,
   `Verdict(state, triggers, worst_area, area_verdicts: dict[str,State])`, `area_verdict(am, cfg) -> Verdict`,
   and `verdict(metrics, cfg) -> Verdict`. **PER-AREA, then roll up:** `area_verdict` evaluates one area
   (first-match, from `ReportCfg` ONLY, no new threshold): ALARM if `overdraw_pct >= overdraw_reject_alarm_pct`
   or `gpu_regression_pct >= gpu_regression_pct`; AT_RISK if `overdraw_pct >= overdraw_reject_warn_pct` or
   `shader_cplx >= shader_complexity_high` or `mesh_repeat >= instancing_repeat_min`; else OK. `verdict`
   computes every area then `state = max(area_verdicts)`, `worst_area` = the worst-scoring area, and
   exposes `area_verdicts` (so the one-pager + c20 JSON can render "N of M areas needs attention").
   **Data-aware:** a `None` input (no baseline, missing parquet) is `present=False` -> contributes UNKNOWN,
   never OK (no false-green, ADR-23). Maxima (worst overdraw/shader) use `n=999`, not the display top-N.
   Also a **`trend(current, baseline) -> Trend(direction, improvements, regressions)`** peer of `verdict`:
   `Direction` enum (IMPROVING / MIXED / REGRESSING / UNKNOWN; lower-is-better on draws/gpu/overdraw/shader;
   net of the headline deltas; UNKNOWN with no baseline) + ranked `Change(metric, area, delta_pct, kind)`
   items (`kind` in improved/regressed/resolved/new). This is what answers "is there a regression" for c20
   `--json` + c21 `report --gate` - presentation-independent, alongside the verdict.
2. **`reports/summary.py`** (stem `summary`): `build(root, *, drops, ab, run_label, run_date) -> str` via
   `base.output_path(root,'summary',ab,run=rc)`. Build per-area `AreaMetrics` by reusing `dashboard._top_*`
   (`n=999` for true maxima) keyed on area + per-area frame counts from the run's drops (avg = area total /
   area captures); assemble `HealthMetrics`, call `health.verdict()`, render:
   - **Verdict** `summary_bar(headline=label[state], tone=...)` + a scope line "N of M areas needs attention
     - <worst_area>" (from `area_verdicts`) + a **Direction tag** (IMPROVING/MIXED/REGRESSING, from
     `health.trend.direction`) so health (where we are) and trajectory (which way) read together; restating
     `callout`.
   - **Headline KPIs = AVERAGES (mean per frame), not totals:** `avg draws/frame` (sum draws / sum frames in
     the run) `avg gpu/frame` `worst overdraw` (MAX, names its area) `worst shader` (MAX, names its area).
     Each shows a **colored vs-prior delta** (green=better/lower, red=worse; no arrow glyphs - sign + color)
     + a **micro `delta.sparkline_svg`** so the multi-run direction (reducing vs rising) is visible at a
     glance. A small grey total line gives scale ("7 areas - 4,417 total" / "12.4 ms total"). Maxima/worst
     stay max; only draws + gpu are averaged.
   - **Movement since <baseline>** card (baseline-gated; the tech-lead glance) from `health.trend`: two
     short lists - **Improvements** (green) and **Regressions** (red), top ~3 named changes each (metric or
     area + delta, e.g. "Police station gpu -15%", "Commercial overdraw 2.1x->3.2x") + a roll-up count line
     ("N issues resolved / N newly un-instanced", from a current-vs-baseline item-set compare). Keeps a
     `delta.sparkline_svg` of the run-over-run arc.
   - **By area** `section_card` (a bare `table.data`, sorted worst-first, ALL areas): area | avg draws/frame
     (+ colored vs-prior %) | avg gpu/frame (+ colored vs-prior %) | overdraw | per-area status
     (`area_verdicts[area]`). caption + `scope="col"`. The vs-prior deltas answer "which areas are
     reducing / regressing" per area.
   - Provenance footer. Human labels (`Healthy`/`Needs attention`/`Action needed`/UNKNOWN) are a presentation
     dict here, NOT in health.py.
   - **Multi-run behavior (run model ADR-35 - NOT cumulative):** summary renders for ONE CURRENT run; it
     NEVER sums runs (the G-19 flaw). **1 run:** no baseline -> deltas + the what-changed card hidden, the
     gpu-regression input is UNKNOWN (no false-green). **2 runs:** current=newest, baseline=older; deltas +
     what-changed shown; 2-point sparkline. **3+ runs:** current=newest, baseline=the immediately-prior run
     (selectable via the c16f run picker); verdict + deltas are current-vs-that-baseline (never vs the sum or
     vs the oldest); an N-point trend sparkline shows the arc; the full N-run matrix stays in `trend_table`.
     Each older run also gets its own `_reports/run/<key>/summary.html` (per-run truth). Because the page
     uses current + delta + sparkline (NOT a column-per-run), it scales past 2 runs cleanly - G-20 does not
     bite it.
3. **Registration:** add `summary` to `reports/__init__.all_reports()` (append last) + `cli._REPORTS`.
   Orchestrator needs no edit (loops `all_reports()`; the older-run pre-render loop only excludes
   `trend_table`, so `summary` renders per older run automatically).
4. **Discoverability (the orphan fix):** a `summary` chip in `dashboard._NAV`; a promoted `summary` link in
   the root-index dashboard `<section>` (`html/template.render_root`), EXCLUDED from the auto-listed report
   grid (mirror the `INDEX_HTML` exclusion); extend `chrome.header` `current_page` to know `summary`.
5. **Tests:** `tests/test_health.py` (`area_verdict` + the global rollup deterministic; rollup
   `state == max(area_verdicts)` and `worst_area` is the worst area; UNKNOWN on a no-baseline/missing-parquet
   fixture - no false-green; rule recomputable from `ReportCfg`; `State` enum stable). `tests/test_summary.py`
   (structure: verdict bar + "N of M areas" scope line + a Direction tag + 4 kpi-chips each with a vs-prior
   delta + sparkline + `id="movement"` card with Improvements + Regressions lists and a resolved/new count +
   `id="by_area"` table with one row per area + per-area vs-prior deltas + per-area status + device-strip;
   the `avg draws/frame` and `avg gpu/frame` values reconcile against the dashboard current-run totals
   divided by the run's frame count; the small total line matches the dashboard totals;
   `lint.lint_file(summary.html)` clean) + `trend` determinism (Direction + improvements/regressions stable;
   UNKNOWN with no baseline).

## Constraints
- Verdict logic lives ONLY in `health.py`; presentation only renders it (the c20/c21 contract).
- Plain-language copy must pass the build-time banlist (`write_report` raises). Safe set in ADR-39 / proposal
  (+ the direction/movement labels `Movement`, `Improvements`, `Regressions`, `Direction`,
  `improving`/`mixed`/`regressing`, `resolved`, `newly un-instanced` - all banlist-clean).
- `health.trend` (direction + improvements/regressions) lives in `health.py`; presentation only renders it
  (so c20 `--json` + c21 `report --gate` answer "is there a regression" from the same evaluator).
- `dashboard.py` output stays byte-unchanged except the one `_NAV` summary chip (intentional). The
  `aggregates.py` extraction is NOT done here (deferred, G-26).
- Determinism: no `random`/`Date`; `n=999` not the display top-N for maxima.

## Done when
- `bobframes report summary <synthetic>` renders + lint-clean; `pytest tests/test_health.py
  tests/test_summary.py` green.
- `make_golden` diff is exactly {new `_reports/summary.html`, new `_reports/run/<k>/summary.html`,
  intentional `index.html` + `dashboard.html` nav}; all other goldens byte-unchanged; `test_parquet_parity`
  green with NO digest refresh (§21.9, presentation only).
- Verdict is UNKNOWN (not OK) on a no-baseline/missing-parquet fixture; global state == max of the per-area
  verdicts; the scope line reads "N of M areas..." with the worst area named.
- Headline KPIs are AVERAGES (avg draws/frame, avg gpu/frame) that reconcile with the dashboard
  totals/frame-count, each with a colored vs-prior delta + sparkline; the By-area table lists every area,
  worst-first, with per-area vs-prior deltas + status.
- The Direction tag + the Movement card (Improvements / Regressions + a resolved/new count) render from
  `health.trend`, baseline-gated; `trend.direction` is the "is there a regression" signal c20/c21 reuse.
- Browser check: the page prints cleanly as ONE manageable page (chrome hidden, inline-SVG charts print)
  with the FULL By-area list (not cram-to-one-A4-screen, no per-area collapse); verdict reachable from the
  dashboard nav + crumb.
- Multi-capture: `avg draws/frame` + `avg gpu/frame` are `sum-over-captures / capture-count`
  (capture-count-independent); the total line shows the frame count; the verdict's mesh-repeat (+ shader
  cost) inputs are normalized PER-FRAME in c16v (G-29) across the reports + the verdict together
  (golden-neutral on the current 1-capture/drop data).
- ADR-39 appended; QUALITY_GATES §21.1q added; FINDINGS G-24..G-27 + HARDCODE H-40 rows added.

## Closes
G-24 (no exec one-pager). Next: c16r (the `head_assets` seam).

## Status - DONE (2026-06-04)
Built on `plan/v0.2.5`; shipped the Scope above. As-built deltas recorded (ADR-23):
- **Golden delta = 5 files, not 4.** The `_NAV` "build health" chip lands on BOTH dashboard instances
  (top-level `_reports/index.html` AND the per-run `_reports/run/<k>/index.html` - the same
  `dashboard.build`), so the reviewed delta is {`summary.html`, `run/<k>/summary.html`, root
  `index.html`, both dashboards}. QUALITY_GATES §21.1q updated to the 5-file count.
- **Per-area shader/mesh fork** (user-confirmed): area-keyed `dashboard._top_shaders_by_area` /
  `_top_meshes_by_area` + a `_top_areas_gpu` 5th element (avg gpu/frame) + a `_run_totals` factor-out
  of `_global_kpis` - all byte-neutral for `dashboard.build`. No `aggregates.py` (G-26 deferred).
- **Verdict semantics** (user-confirmed): `State` ordered `OK<UNKNOWN<AT_RISK<ALARM` (a real ALARM is
  never masked by a missing-data area; UNKNOWN still beats OK = no false-green); `area_verdict` is
  ABSOLUTE-FIRST (a missing gpu-regression - None on every 1-run build - does NOT block OK; it shows
  as `Direction=UNKNOWN`; missing absolute data still -> UNKNOWN); `trend.direction` nets the 4
  headline metrics (draws/gpu/overdraw/shader).
- 191 -> 229 green (test_health 22 + test_summary 13); browser print = ONE page; lint clean.
- **CSS shipped brute-forced - recorded as debt (G-30, ADR-42).** The one-pager styling is a
  page-scoped inline `<style>` (keyed on `body[data-page-kind="summary"]`) + bespoke markup helpers
  (`_kpi`, `_trendline`, status badge, Movement layout) that re-implement card/kpi patterns instead of
  reusing components. A typo'd `var(--sp-5)` (no such token - the scale is 1/2/3/4/6/8/12) silently
  zeroed the chip padding before review caught it: the untyped-inline-CSS failure mode. Acceptable for
  ONE page, does NOT scale. The proper fix is the **component system (c16x, ADR-42)**, now in v0.2.5
  scope; until it lands, `summary.py` owns its scoped `<style>`.
