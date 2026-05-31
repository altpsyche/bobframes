# c26 — `export` verb     release: v0.3 · phase: CI/automation

## Goal
Export a drop's tables for sharing/downstream tooling. The CSV pairs are already written at
parquetize; this verb bundles them (plus JSON / a zip) without re-running extraction.

## Depends on
[c20](c20_json_output.md) (`--json` file list). Reuses the existing parquet/CSV pairs and `discovery`.

## Seam extended
The parquetize CSV-pair sidecars (already on disk), `discovery.find_drops`, `paths.*` (c04 constants).
No new serialization of extraction — reads what's committed.

## Files
- `bobframes/export.py` — NEW: select a drop, copy/zip its tables to an output dir; `--format`
  `csv|json|zip`; CSV is the existing pairs, JSON is per-table records, zip bundles either.
- `cli.py` — NEW `export` verb (`<root> --area --label --format --out`); `--json` lists exported paths.

## Changes
Export reads committed `_data/`; never re-extracts. JSON export uses the schema dtypes
(`schemas.infer_dtype`) for typing.

## Done when
- `bobframes export <root> --format csv --out <dir>` writes a bundle of the drop's tables.
- `--format zip` produces one archive; `--json` lists the exported files carrying `json_schema_version`.
- **Golden parity green** — read-only over `_data/`.

## Closes
G-5.
