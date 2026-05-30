# c16 — report-quality polish     release: v0.2 · phase: De-hardcoding

## Goal
Report polish that needs the de-hardcoding hooks. Data extraction stays identical; this is presentation
+ resilience + provenance surfacing. Quality changes are **opt-in / additive** so parity holds until
the golden is intentionally refreshed.

## Depends on
[c09](c09_classifier.md) (last de-hardcoding step) — sequence near the end of v0.2.

## Files
- Each report emitter — empty-state message (no draws → friendly message, not a blank table).
- `reports/cache.py` — missing-column tolerance: graceful degradation + warning, not an index error;
  add SHA256 sidecar, invalidate cache on mismatch (R-13).
- `delta.py` — verify sparkline null-gap rendering on synthetic entries with nulls; add to golden.
- `reports/_dashboard.py` → rename `dashboard.py` (Q-9; safe now, no churn cost).
- Dashboard footer — surface the `tool_versions` + `host_info` recorded at ingest in c03 (G-6/G-7).

## Changes
Additive. Where output changes (empty states, footer provenance), **refresh the golden snapshot in
the same PR** and review the diff.

## Done when
- Empty-state messages render for a sparse synthetic drop.
- Corrupted cache parquet rebuilds with a warning instead of returning empty (R-13).
- Dashboard footer shows GPU/driver/CPU/OS + tool versions (deterministic via the c02 stubs).
- Golden refreshed + reviewed; parity green against the new golden.

## Closes
R-13 · Q-9 · surfaces G-6/G-7. Report-polish items from
[QUALITY_GATES §21.5](../../reference/QUALITY_GATES.md).
