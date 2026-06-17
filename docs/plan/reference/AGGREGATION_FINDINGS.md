# Reporting — averaging / aggregation consistency findings

> Found while ingesting the real **RDC mainline** Perf corpus (2026-06-16): 4 runs ×
> 7 areas × 5 captures. Question that triggered the audit: *"how is the average computed —
> mean between all areas, or mean of all areas?"* Answer: the reports use **four different
> aggregation bases** (pooled mean, per-area mean, median, raw total) and several are labeled
> as plain "avg", so the same underlying metric reads differently across reports.
>
> Same conventions as `FINDINGS.md`: symbol-anchored `Where` (no line numbers — they drift),
> proposed IDs (assign real ones on intake). Severity: **P0** correctness / wrong action items,
> **P1** silent divergence, **P2** clarity.

## The four bases in play (reference)

| Basis | Formula | Used by |
|---|---|---|
| pooled (frame-weighted) mean | `Σ_areas total / Σ_areas frames` | summary + dashboard **headline** KPIs |
| per-area mean | `area_total / area_frames` | summary "By area" table, dashboard per-area card |
| median | `median(values)` | draws_by_class prepass/opaque ratio, mesh "typical" vert count |
| raw total (no division) | `Σ values` | trend_table hero + regression, pass_gpu, draws_by_class "total draws" |

## Findings

| ID (proposed) | Where | Finding | Fix | sev |
|---|---|---|---|---|
| D-A1 | `reports/trend_table.build` (`KPIS` regression on `total_gpu_duration_s`) **vs** `reports/summary._collect_metrics` + `health.verdict`/`trend` (per-area `avg_gpu_per_frame` from `dashboard._top_areas_gpu`) | **"GPU regression" is computed two contradictory ways.** Trend flags an area on a ≥10% rise in **total GPU summed over captures** (capture-count-SENSITIVE); summary/health flags on a ≥10% rise in **avg GPU per frame** (capture-count-INDEPENDENT). With runs of differing capture counts the two reports disagree on whether an area regressed: a run with 7 captures vs a prior 5 at identical per-frame cost shows **+40% in the trend table (false regression)** and **0% in summary (correct)**. This directly produces wrong regression action items. (The real corpus was hand-trimmed to a uniform 5 captures/run to dodge it — the tool should not require that.) | Pick ONE canonical regression basis. Recommend per-frame everywhere: normalize trend `KPIS` by the per-(drop,area) frame count before the delta. At minimum, make trend consume the same per-frame metric `health` does. | P0 |
| H-A2 | `reports/trend_table.KPIS` (threshold literal `10.0` in the tuple) **vs** `reports/summary.build` (`rcfg.gpu_regression_pct`) | **Regression threshold is hardcoded in trend, config-driven in summary.** `KPIS = [('total_gpu_duration_s', …, 10.0), ('n_draws', …, 10.0)]` bakes 10% into the module; summary/health read `report.gpu_regression_pct` (default 10.0). Tuning `gpu_regression_pct` in `.bobframes.toml` silently fails to move the trend-table heatmap — the two reports flag at different thresholds. | Source the trend thresholds from `report` config (same key as health, or a sibling key); drop the literals. | P1 |
| D-A3 | `reports/summary.build` headline (`dashboard._run_totals`: `total/n_frames`) **vs** the "By area" table (`avg_gpu_per_frame` per area) | **Headline pooled mean wears the same label as the per-area column it sits above, but is not the average of it.** Headline `avg gpu/frame` = `Σ_areas gpu / Σ_areas frames` (frame-weighted pooled mean). It equals the unweighted mean of the per-area "avg gpu/frame" column ONLY when every area has the same frame count. A single capture that replays but emits no `frame_totals` row makes the headline silently diverge from the average of the column below it. Readers reasonably assume the headline IS the column average. | State the basis in the KPI note ("pooled across N frames"), and/or add a regression test asserting the headline↔area-column relationship; decide pooled-vs-macro as explicit policy. | P1 |
| D-A4 | `dashboard._run_totals` / `dashboard._top_areas_gpu` (denominator = `frame_totals.parquet` num_rows) **vs** `aggregates.DrawAgg.frames` / `aggregates.ShaderAgg.frames` (denominator = distinct `capture` values in draws/shaders parquet) | **Two different frame-count denominators feed "per frame" numbers.** GPU & draws per-frame divide by row count of `frame_totals`; instancing/shader/mesh per-frame rates divide by distinct captures present in the entity parquet. They agree only if every replayed capture produced BOTH a `frame_totals` row AND entity rows. `aggregates.py`'s own docstring flags the "capture replayed ok but exported no entity rows" case — exactly when the two denominators differ. So cross-report per-frame values can be normalized by different N without any warning. | One source of truth for per-(drop,area) `frame_count`; both the frame-totals layer and the aggregates layer consume it (or assert equality at build time). | P1 |
| Q-A5 | `reports/pass_gpu._aggregate` (`bucket['gpu'] += gpu` over captures), `pass_gpu._cur_gpu`, heaviest-pass callout text | **pass_gpu shows cross-capture TOTAL GPU while summary/dashboard show per-frame mean GPU** — same underlying metric, different magnitude and basis, no shared anchor for a reader cross-referencing the two. Also the callout says "GPU on the **costliest capture**" but `_cur_gpu` returns the per-pass value **summed over all ok captures**, so the wording is wrong. | Per-frame-normalize pass_gpu to match the headline basis (or relabel explicitly as "total over N captures"); fix the callout wording to match what's computed. | P2 |
| Q-A6 | `reports/draws_by_class._hero_kpis` (`median_ratio`, "prepass/opaque (med)") and `dashboard._top_meshes_by_area` / `instancing_opportunities` (`statistics.median(num_indices)`, "typical") | **Medians presented inside an otherwise "avg" framing, and the ratio median is unweighted across areas (macro) while the headlines are pooled (micro).** Statistically defensible (median resists skew), but the mixed basis is undisclosed: a user reading "avg" KPIs next to a silently-median "typical"/"ratio" can't tell they're different estimators on different populations. | Label the estimator + population on each ("median across areas", "median verts"); make pooled-vs-macro an explicit, consistent policy. | P2 |
| Q-A7 | `reports/draws_by_class._hero_kpis` ("total draws" = `Σ over captures`) | **"total draws" hero is a raw cross-capture count (capture-count-sensitive)** while summary's draws KPI is per-frame. Comparing the same area's draw load across runs of differing capture counts via this number misleads. | Offer a per-frame draw count alongside (or instead of) the raw total, consistent with summary; or note the basis. | P2 |
| Q-A8 | `reports/overdraw` (`_worst_overdraw`: `1 − Σpassed/Σsamples`) + summary "worst overdraw" (MAX over areas) | **Informational:** overdraw reject% is a pooled micro-average over pixel samples (correct), and the summary headline is a MAX selection (correctly labeled "worst"). No bug — recorded so the basis is documented alongside the others and not "fixed" into a mean by mistake. | None (document basis). | P2 |

## Suggested intake order

1. **D-A1 + H-A2** together — they're the regression-correctness pair and the reason runs had to be hand-trimmed to equal capture counts. Fixing them lets the tool handle uneven capture counts safely.
2. **D-A4** — the dual frame-count denominator; subtle, bites silently.
3. **D-A3, Q-A5..A7** — labeling/basis consistency; mostly disclosure + per-frame normalization.

All are golden-affecting (they change emitted numbers), so each needs an explicit golden refresh per ADR-23 rather than a silent gate narrowing.

## Resolution (intaken + burned down in v0.2.7, 2026-06-17)

Intaken into the burndown catalogs with real IDs and resolved across `commits/v027/`. Policy frozen as
**ADR-46** (one per-frame canonical basis; estimator+population named on every label; "Mean" not "avg").

| audit ID | real ID | commit | status |
|---|---|---|---|
| D-A1 | D-13 (FINDINGS) | v027_1 | ☑ per-frame trend regression, agrees with health |
| H-A2 | H-41 (HARDCODE) | v027_1 | ☑ thresholds from `ReportCfg`, `.bobframes.toml` moves both paths |
| D-A4 | D-15 (FINDINGS) | v027_0 | ☑ `aggregates.frame_counts` single owner + divergence WARN (centralize+warn+document; equality doesn't hold by design) |
| D-A3 | D-14 (FINDINGS) | v027_2 | ☑ "pooled mean ..." headline + note; "mean ... (per area)" column + disclosure caption |
| (new) D-A9 | D-16 (FINDINGS) | v027_2 | ☑ dashboard card leads per-frame + labeled total; cross-report consistency test |
| Q-A5 | Q-10 (FINDINGS) | v027_2 | ☑ pass_gpu per-frame hero + labeled total; callout wording fixed |
| Q-A6 | Q-11 (FINDINGS) | v027_3 | ☑ `statistics.median` + "median ..." labels (draws_by_class/dashboard/instancing) |
| Q-A7 | Q-12 (FINDINGS) | v027_3 | ☑ "mean draws / frame" + labeled total ("all drops" sub-claim was false -- already current-run scoped) |
| Q-A8 | Q-13 (FINDINGS) | v027_4 | ☑ recorded as correct-as-designed (pooled micro reject% + MAX "worst"); NOT changed |

Gates: see QUALITY_GATES §21.1w.
