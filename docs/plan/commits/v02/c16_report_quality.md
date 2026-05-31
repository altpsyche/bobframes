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
- **Manifest schema-version guard (D-7) — implements the frozen DECISIONS versioning contract that is
  currently UNBUILT.** `render` / `catalog` / `ab` must read the manifest and **refuse to operate when
  `manifest.schema_version != schemas.SCHEMA_VERSION`** → exit 1 with a message pointing at
  `bobframes ingest --force`. A shared `manifest.assert_compatible(out_dir)` helper (reuses
  `manifest.read_manifest`); the verbs call it before touching Parquet. Safe to land in v0.2 because
  `SCHEMA_VERSION` does not change until c35 — no stale manifests exist yet, but the guard must be in
  place **before** the c35 bump so [c24](../v03/c24_verify.md) (verify) and
  [c35](../v05/c35_schema_widening.md) (migration story) can rely on it.

## Changes
Additive. Where output changes (empty states, footer provenance), **refresh the golden snapshot in
the same PR** and review the diff. The schema-version guard does not change output for a current-version
manifest (the only kind that exists in v0.2) — so it is parity-neutral until exercised by a stale
manifest in a test.

## Done when
- Empty-state messages render for a sparse synthetic drop.
- Corrupted cache parquet rebuilds with a warning instead of returning empty (R-13).
- Dashboard footer shows GPU/driver/CPU/OS + tool versions (deterministic via the c02 stubs).
- **`render`/`catalog`/`ab` exit 1 with the `ingest --force` hint on a synthetic manifest whose
  `schema_version` is bumped out of range; exit 0 on a matching one** (D-7) — a unit test forces the
  mismatch.
- Golden refreshed + reviewed; parity green against the new golden.

## Closes
R-13 · Q-9 · **D-4, D-7 (manifest schema-version guard)** · surfaces G-6/G-7. Report-polish items from
[QUALITY_GATES §21.5](../../reference/QUALITY_GATES.md). Foundation for c24/c35.
