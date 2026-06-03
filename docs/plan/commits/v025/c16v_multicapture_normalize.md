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

## Closes
G-29 (multi-capture repeat/cost inflation). Next: c16w (v0.2.5 close-out + release).
