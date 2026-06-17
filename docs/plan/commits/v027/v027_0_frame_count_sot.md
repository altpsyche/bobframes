# v0.2.7-0 -- frame-count single source of truth + divergence warning     release: v0.2.7 · phase: aggregation-consistency

> The FOUNDATION commit of the v0.2.7 "confusing averages" burndown (audit:
> `docs/plan/reference/AGGREGATION_FINDINGS.md`; approved plan:
> `~/.claude/plans/check-aggregation-findings-read-it-elegant-kite.md`). Resolves D-15 (D-A4): the
> reports normalize "per frame" by TWO different denominators -- per-frame GPU/draws divide by the
> `frame_totals` frame count, per-frame mesh/shader rates divide by the distinct-entity-capture count
> (c16v) -- and the divergence was silent. No new ADR (ADR-46 is drafted in v027_1).

## Goal
Make `aggregates.py` the ONE owner of every per-(drop, area) frame count, and emit a build-time
WARNING (not a hard assert) naming any (drop, area) where the GPU/draws frame count diverges from the
entity-capture count -- so cross-report per-frame normalization uses different N **visibly**, not
silently. **Golden-neutral**: no emitted number or byte changes; the warning is `log()`/stderr only.

## Data-grounded correction (why NOT "one denominator")
Inspected the parquet (2026-06-17). The committed synthetic has `frame_totals` = **5 distinct
captures** but `draws`/`shaders` = **1** (the deliberate c16v skew: `ok_captures=5`, entity data
capture-1-only). So GPU-per-frame already divides by 5 while entity rates divide by 1 -- **two
denominators by design**, and c16v's ADR-23 as-built says the entity-capture count is the *correct*
divisor for entity rates (you cannot average a mesh over frames that exported no draws). Forcing a
single denominator would either x5 the GPU numbers or /5 the entity numbers -- both WRONG and a c16v
regression. In the **real** corpus (uniform 5 captures, all exporting both) the two AGREE (5 = 5), so
the user's felt confusion is the LABELS (v027_2), not the denominator. Hence D-15 is resolved by
**centralize + warn + document**, the audit's "assert equality at build time" option softened to a
warn because equality legitimately does not hold (it would crash on the fixture).

## Scope
- **bobframes/aggregates.py** -- NEW `frame_counts(root, drops) -> {(drop_key, area): {frames,
  draw_frames, shader_frames}}` (the single owner): `frames` = distinct captures in `frame_totals`
  (the GPU/draws denominator, read live per drop_dir via NEW `_frame_total_captures`, mirroring the
  dashboard readers; falls back to `num_rows` if a frame_totals has no `capture` column);
  `draw_frames`/`shader_frames` = `len(DrawAgg.captures)` / `len(ShaderAgg.captures)` (the c16v
  entity-rate denominators). NEW `frame_count_divergences(root, drops) -> [(dk, area, frames,
  draw_frames, shader_frames)]` for every (drop, area) where an entity count that EXISTS (>0) differs
  from `frames`, sorted. Raw counts (no `>=1` guard) so divergence is detectable; the per-frame no-op
  guard stays in `DrawAgg.frames`/`ShaderAgg.frames` (UNCHANGED -- entity-rate divisor untouched).
- **bobframes/reports/orchestrator.py** -- after the per-drop cache build, call
  `frame_count_divergences` and `log()` a named WARNING per divergence (the catalog is built by the
  CLI/`run.py` before `render_all_reports`, so `discover_drops` resolves). Matches the existing
  theme-undefined-token warn pattern (line 38). HTML unchanged.
- **bobframes/tests/test_aggregates.py** -- NEW `_frame_totals` writer + `_write_tree` gains an
  optional `frame_totals=`; NEW `fc_tree` fixture (two areas: AreaSkew frame_totals 1-5 / draws-shaders
  capture-1 only; AreaEven all-3 everywhere) + 3 tests: `frame_counts` is the single owner with the
  right counts; divergence flags ONLY the skewed area; `DrawAgg.frames` (entity divisor) stays 1 for
  the skewed area (c16v invariant held).

## Constraints
- Golden-NEUTRAL: no number/byte change; warning is `log()`/stderr (golden gate compares HTML).
- The entity-rate divisor (`DrawAgg.frames`/`ShaderAgg.frames`) MUST NOT change (c16v / ADR-23).
- Determinism: divergence list sorted; no time/random.

## Done when
- `aggregates.frame_counts` owns all three per-(drop, area) counts; `frame_count_divergences` flags
  exactly the skewed (drop, area).
- The render emits a named warning on a divergent tree (verified on the synthetic: 2 divergences,
  rc 0); GPU and entity rates keep their (different, correct) divisors.
- Synthetic golden BYTE-UNCHANGED (`test_parity` + `test_parquet_parity` green, NO refresh).
- Full `-m "not browser"` suite green.

## As-built (DONE 2026-06-17)
- `aggregates.frame_counts` / `frame_count_divergences` / `_frame_total_captures` added exactly as
  scoped; `DrawAgg.frames`/`ShaderAgg.frames` untouched. Orchestrator warns via `log()` after the
  cache build.
- PROVEN: on a synthetic render the divergence detector returns
  `[('2026-05-27_r110565','District 01',5,1,1), ('2026-05-28_r110600','District 01',5,1,1)]`; the
  render returns rc 0 (warning is non-fatal, stderr/log only). `test_parity` + `test_parquet_parity`
  BYTE-UNCHANGED (NO golden refresh). `test_aggregates` 3 -> 6 (the 3 new D-15 tests green). Full
  suite: **355 passed**, 1 deselected (browser), up from 352 (+3).
- Golden-NEUTRAL confirmed (no `make_golden`). No new ADR. FINDINGS D-15 ticked (D-13/14/16 + Q-10..13
  + H-41 opened with resolved-by stubs); the "two populations, both correct" rationale recorded in the
  D-15 row + this doc (ADR-23 documented scoping; ADR-46 will formalize the policy in v027_1).

## Next
v0.2.7-1 (regression unification + config thresholds, D-13 + H-41; drafts ADR-46). GOLDEN-AFFECTING.
