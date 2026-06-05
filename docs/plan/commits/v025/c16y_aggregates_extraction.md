# c16y — single-source aggregation (`aggregates.py`)     release: v0.2.5 · phase: report-correctness

> Extract the per-(drop, area, entity) mesh-repeat + shader-cost atoms (and the per-(drop, area) frame
> count) into ONE presentation-independent module so c16v's per-frame normalization lands in a single
> place and the reports + the verdict can never disagree. ZERO-output refactor (G-26). Precedes c16v.

## Goal
Kill the 3-way drift: "count mesh repeats / sum shader cost" was implemented independently in
`dashboard._top_meshes`/`_top_meshes_by_area`, `instancing_opportunities`, `shader_hotlist`, and
`_top_shaders`/`_top_shaders_by_area`, kept in sync only by convention + a reconciliation test (the
`dashboard.py:230` comment admitted the risk). G-26 was deferred "to the 3rd consumer"; c16v's
normalization is that 3rd reason — do the extraction FIRST so the divide happens once.

## Depends on
c16q (the verdict reads the dashboard helpers). Precursor to c16v (the per-frame fix rides this seam).

## Scope
1. **NEW `bobframes/aggregates.py`** — pure data layer (no HTML/labels), a peer of `health.py`. Reads
   the `draws_summary`/`shader_summary` per-drop caches (`reports.cache.load_cached`) with a live
   per-drop parquet fallback, mirroring the readers it replaces EXACTLY (same filter, same cache, same
   row order → byte-identical counts, same `Counter.most_common` tie / first-seen `setdefault`).
   - `draw_aggregates(root, drops) -> DrawAgg`: `count` per `(drop_key, area, mesh_hash)` (valid rows:
     mesh_hash truthy, num_indices>0, program_id!=0) + `num_indices`/`draw_class`/`pass_norm` metadata
     + `captures` per `(drop_key, area)`; `frames(dk, area)` = distinct captures present, `>=1`.
   - `shader_aggregates(root, drops, *, stage) -> ShaderAgg`: `uses` (Σ used_by_draw_count), `cost_sum`
     (Σ cplx*uses), `cplx` (max), `stype` per `(drop_key, area, stable_key)` + `frames`. Both cost
     atoms are exposed because the two consumers use DIFFERENT cost formulas (dashboard `_top_shaders`
     = `cost_sum`; `shader_hotlist` = `cplx * Σuses`) — both must stay byte-identical.
2. **Rewire consumers** to derive their counts from the atoms:
   - `dashboard._top_meshes` (collapse across areas), `_top_meshes_by_area` (per area),
     `_top_shaders` (collapse), `_top_shaders_by_area` (per area).
   - `instancing_opportunities`: keep the rich per-mesh metadata loop (pass_paths, rep_row, batching,
     areas/captures sets) but source `repeat_by_drop` from the atoms (remove the inline `+=1`).
   - `shader_hotlist`: keep the per-shader metadata loop (branches/loops/rep/flags + complexity max) but
     source `uses_by_drop` from the atoms (remove the inline `+=`). Counter `+= 0` preserves the
     "presence not uses>0" scope.
   `_top_areas_gpu`/`_run_totals`/`_worst_overdraw` (frame_totals-based, already correct) untouched.

## Constraints
- **Byte-identical output** — same numbers, same ordering, same HTML/parquet. `test_parity` +
  `test_parquet_parity` green, NO golden refresh. (The golden synthetic is single-area/single-capture,
  so collapse/order subtleties are trivial there; the design is correct for multi-area too.)
- The dashboard helpers gain a live-scan fallback on cache-miss (folds C3's fallback-unify); golden-safe
  because the cache always exists in the render/test path.

## Done when
- `bobframes/aggregates.py` is the single source of the repeat/cost atoms + frame count; the 6 call
  sites consume it.
- ALL goldens BYTE-UNCHANGED (`pytest tests/test_parity.py` + `test_parquet_parity`, NO refresh).
- `tests/test_aggregates.py` pins the atoms on a constructed multi-capture tree.
- G-26 ticked (resolved-by c16y); QUALITY_GATES §21.1t records the extraction.

## Closes
G-26 (3-way aggregation drift). Next: c16v (per-frame normalization rides this seam).
