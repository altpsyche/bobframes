# c13 — replay-schema drift detector (CI)     release: v0.1 · phase: CLI + pkg

## Goal
Guard H-6: `replay/replay_main.py` duplicates schema column tuples from `schemas.py` (qrenderdoc
import is unreliable). A CI test fails the build the moment a `schemas.py` edit isn't mirrored — so
the duplication is safe to keep.

## Depends on
[c12](c12_replay_importlib.md). (Independent of c12 logically; sequenced here.)

## Files
- `tests/replay_drift.py` — NEW. Plus a small `_extract_col_tuples(tree, suffix, skip)` helper that
  parses top-level `<NAME>_COLS = (...)` assignments via `ast`, resolving `ID_COLS + (...)`
  concatenations into the full literal tuple.

## Changes
Implement the **corrected** test ([ADR-5](../../DECISIONS.md), full code in
[QUALITY_GATES §21.3](../../reference/QUALITY_GATES.md)):
- Match the **`_COLS` suffix** (the original `_COLS_` *prefix* matched zero → vacuous pass).
- Skip the shared `ID_COLS` base (not a table).
- Map var→stem with an explicit alias map for abbreviated names: `RT_COLS`→`render_targets`,
  `RT_TIMELINE_COLS`→`rt_event_timeline`, `STATE_CHANGE_COLS`→`state_change_events`,
  `COUNTERS_COLS`→`counters_per_event`; identity-lowercase otherwise.
- **Assert ≥ 21 tables found** so a future rename can't silently re-disable the guard.

## Done when
- `pytest tests/replay_drift.py` green against current code (finds ~21 tables, all in sync).
- **Negative check:** temporarily reorder/edit one replay `*_COLS` tuple → test FAILS with the exact
  column diff; revert.
- Wired into CI ([c17](c17_ci_workflow.md)).

## Rollback
Delete `tests/replay_drift.py`.

## Closes
H-6 (guarded, not removed — duplication stays by design). Supports D-2.

> Cheaper alternative on the table ([ADR-5](../../DECISIONS.md)): rename the replay vars to match
> schema stems exactly (`RENDER_TARGETS_COLS`, …) so the alias map disappears. If taken, do it here
> and drop `_REPLAY_STEM`.
