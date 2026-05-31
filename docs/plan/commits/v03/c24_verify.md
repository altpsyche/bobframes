# c24 — `verify` verb (integrity check)     release: v0.3 · phase: CI/automation

## Goal
A read-only integrity check over an existing `_data/` tree: catch schema drift, corrupted cache, and
count mismatches before they reach a report or a regression gate.

## Depends on
[c20](c20_json_output.md) (`--json` report). Uses the c16 cache SHA256 sidecar (R-13) and
`schemas.expected_columns`.

## Seam extended
`schemas.expected_columns` / `SCHEMA_VERSION`, `manifest.read_manifest`, `catalog` row counts,
`reports/cache` SHA256 (R-13, from c16). Reuses the c24 checks as the substrate `diff` (c25) builds on.

## Files
- `bobframes/verify.py` — NEW: walks `_data/`, asserts (a) manifest `schema_version` ==
  `schemas.SCHEMA_VERSION`; (b) every parquet's columns == `expected_columns(stem)`; (c) cache SHA256
  matches (R-13); (d) per-capture row counts agree with the catalog.
- `cli.py` — NEW `verify` verb (positional `<root>`); exit 1 on any failure; `--json` report
  (`{checks: [...], ok, failures}`).

## Changes
Read-only — never mutates `_data/`. Aggregates all failures (does not stop at the first) for a useful
CI report.

## Done when
- `bobframes verify <root>` passes (exit 0) on a clean synthetic, fails (exit 1) on a deliberately
  corrupted one (wrong column, bad cache SHA, stale schema_version).
- `--json` lists each check + verdict carrying `json_schema_version`.
- **Golden parity green** — no render path touched.

## Closes
G-4. Surfaces D-2 (schema-mismatch reporting) at the `_data/` level.
