# c16v — multi-capture per-frame normalization     release: v0.2.5 · phase: report-correctness

> Fix the latent multi-capture distortion (G-29): when a drop holds multiple captures (.rdc / frames), the
> instancing repeat-count + the shader cost/uses are SUMMED across the captured frames, inflating them.
> Normalize both to PER-FRAME across the detailed reports + the shared dashboard helpers + the verdict, so
> they stay consistent. Golden-neutral on today's 1-capture-per-drop data; guarded by a constructed
> multi-capture unit test. Pairs with c16q's verdict.

## Goal
Repeat-count and shader cost/uses read as PER-FRAME rates, so a multi-capture drop (a mesh drawn once per
frame across 3 .rdc) no longer reads as repeat=3 / 3x cost. `instancing_repeat_min` now means "per frame"
(its intent: per-frame draw redundancy). Fixes the reports AND the verdict input together.

## Depends on
c16q (the health verdict reads `mesh_repeat`). Independent of the packaging commits (c16r-c16u); placed
late ONLY because it is golden-neutral on current 1-capture data - conceptually it pairs with c16q.

## Scope
1. **`instancing_opportunities.py`:** the per-(area, mesh, drop) repeat is the draw-occurrence count summed
   over the drop's captures. Divide by the drop's frame count (`ok_captures`) -> repeat PER FRAME; the
   `instancing_repeat_min` comparison + the per-drop repeat columns read per-frame.
2. **`shader_hotlist.py`:** `uses` is summed across captures and `cost = uses x complexity`. Normalize
   `uses` (and thus `cost`) to per-frame (`uses / frame-count`). `complexity` (per-shader) is UNCHANGED.
3. **`dashboard._top_meshes` / `_top_shaders`:** apply the SAME normalization at the shared helper, so the
   dashboard, the one-pager, and `health.verdict` all read per-frame repeat/cost from ONE place (no drift).
4. **`health.py`:** `AreaMetrics.mesh_repeat` (and any cost input) are now per-frame, inherited from the
   normalized helpers; the verdict's `instancing_repeat_min` comparison + the Movement/By-area numbers
   inherit it. The verdict still mirrors the (now-normalized) instancing/shader reports.
5. **Frame-count source:** the drop's `ok_captures` (discovery.py `DropRow`/`DropSet.n_captures`); divide by
   the per-DROP frame count, never the run/area total; guard divide-by-zero (>=1).
6. **Semantics recorded:** `instancing_repeat_min` + the shader cost are now PER-FRAME; document in the
   report + the `config [report]` comment (ADR-23: the metric is corrected to match the threshold's
   long-standing intent). No new ADR (rides ADR-32).

## Constraints
- **Golden-neutral on current data:** the synthetic + real Perf are 1 capture/drop, so `/1` changes
  nothing -> ALL HTML + parquet goldens BYTE-UNCHANGED, parity green by construction, NO golden refresh
  (§21.9). The fix is latent-correctness, proven by the constructed unit test, not the golden corpus.
- Divide by the per-drop `ok_captures`, not the run/area total; never divide by zero.
- Determinism: fixed-precision; no `random`/`Date`.

## Done when
- repeat-count + shader cost/uses are per-frame in `instancing_opportunities` + `shader_hotlist` + the
  dashboard helpers + `health.verdict` (one source).
- ALL goldens BYTE-UNCHANGED (`pytest tests/test_parity.py` + `test_parquet_parity` green, NO refresh).
- A CONSTRUCTED multi-capture unit test (3 captures of one area; a mesh drawn once/frame + a shader used
  once/frame) proves repeat-per-frame == 1 (not 3) + cost normalized + the 1-capture path is a no-op.
- `instancing_repeat_min` per-frame semantic documented; G-29 ticked (resolved-by c16v).
- QUALITY_GATES §21.1t added.

## As-built (ADR-23 — deviations from the plan above, with rationale)

1. **Rides c16y (G-26).** Normalization lands at the ONE `aggregates.py` seam (extracted in c16y, the
   precursor), not patched into 3+ inline loops. `base.per_frame(total, frames)` (new, in
   `formatters.py`, re-exported via `base`) is the single divide: it returns `total` UNCHANGED when
   `frames<=1` (so 1-capture data is byte-identical — `heatmap_cell` emits the raw value via `h()`,
   where a float `6.0` would serialize `"6.0"` != int `"6"`; we keep RAW integer counters and divide at
   read-time, never float-accumulate). Applied PER AREA (each area's count ÷ that area's frame count)
   then summed across areas, so cross-area displays stay correct and the verdict (reading
   `_top_meshes_by_area`) can't disagree with the instancing report.

2. **Frame-count source = the DATA, not `ok_captures` (the plan's stated source was wrong).** Verified
   the committed synthetic fixture declares `ok_captures=5` (manifest `capture_status`, 5 ok) while its
   `draws.parquet`/`shaders.parquet` populate ONLY `capture='1'`. So `/ok_captures` would (a) divide
   every golden value by 5 (breaking the "no refresh" constraint) AND (b) be semantically wrong (1 real
   frame of draws shown as 1/5). The denominator is instead the count of **distinct `capture` values
   PRESENT in that drop+area's entity data** (`DrawAgg.frames`/`ShaderAgg.frames`, guarded `>=1`). On
   consistent data this equals `ok_captures`; on the skewed synthetic it is 1 → golden-neutral. It is
   also strictly more correct (can't average over frames that exported no entity rows). Decided with the
   user ("designed perfectly"); recorded in FINDINGS G-29 + QUALITY_GATES §21.1t.

3. **Batching repeat** (shares the `instancing_repeat_min` threshold) is normalized by the current
   run's per-area frame count (max over its areas — exact on uniform/single-area drops, a documented
   cross-area approximation otherwise).

4. **Rendered tooltips/captions UNCHANGED** (e.g. "cost = complexity x total uses"). Editing them would
   change the golden; they stay accurate for the 1-capture display. The per-frame semantic is documented
   in the config comment (`instancing_repeat_min`) + `config.py` + module docstrings. A future
   golden-refreshing commit may refine the copy.

5. **Proof:** `tests/test_multicapture_normalize.py` — repeat 3-cap==1 / 1-cap==3 / divisor=data-frames
   (the `ok_captures=5`, data=1-capture skew case → repeat==3 not 3/5) / cost normalized (60 not 180) /
   complexity unchanged / instancing+shader reports render per-frame. Goldens BYTE-UNCHANGED (285 green,
   NO refresh).

## Closes
G-29 (multi-capture repeat/cost inflation). Next: **c16x** (component system, ADR-42, G-30) — then the
c16w close-out (trust STATE's spine; this doc's earlier "Next: c16w" predated the c16x insertion).
