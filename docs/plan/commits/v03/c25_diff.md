# c25 — `diff` verb (drop/manifest delta)     release: v0.3 · phase: CI/automation

## Goal
Compare two drops (or manifests) and report what changed — KPI deltas, row-count deltas, schema-version
mismatch, added/removed captures — as text and JSON, for PR/CI review.

## Depends on
[c20](c20_json_output.md) (`--json`). Reuses `reports/trend_table` delta math and `manifest.read_manifest`.

## Seam extended
`reports/trend_table` delta computation (`pct = 100*(cur-prev)/prev`), `manifest.read_manifest`,
`catalog` row counts. No parallel delta engine — the same math the trend report uses.

## Files
- `bobframes/diff.py` — NEW: load two manifests + their catalogs; compute KPI deltas (reusing the
  trend math), row-count deltas per table, capture set add/remove, schema_version mismatch.
- `cli.py` — NEW `diff` verb (`<root> --baseline-label X --compare-label Y [--baseline-date]
  [--compare-date]`, mirroring `ab`'s arg shape); stable text table + `--json` delta object.

## Changes
Deterministic ordering (sort keys) so text + JSON are stable across runs. Reuses `ab`'s
baseline/compare argument convention.

## Done when
- `bobframes diff <root> --baseline-label A --compare-label B` emits a stable text delta between two
  synthetic drops; `--json` emits the same data carrying `json_schema_version`.
- Schema-version mismatch and capture add/remove are reported.
- **Golden parity green.**

## Closes
G-2.
