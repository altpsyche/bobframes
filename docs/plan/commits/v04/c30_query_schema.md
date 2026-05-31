# c30 — `schema` introspection (core) + `query` optional extra     release: v0.4 · phase: Engine breadth + ergonomics

## Goal
Make the Parquet queryable for engineers without forcing a heavy dependency on everyone. `schema`
introspection ships in the **pyarrow-only core**; SQL `query` is an **opt-in extra**
(`pip install bobframes[query]` → DuckDB), per [ADR-17](../../DECISIONS.md). Chosen for tool lifespan:
lean core, opt-in power.

## Depends on
[c05](../v02/c05_registry_consolidation.md) (`schemas.TABLES` as the introspection source).

## Seam extended
`schemas.TABLES` / `expected_columns` / `infer_dtype` (introspection); `paths.*` for table discovery.
The `query` extra is isolated behind a lazy import — the core invariant **pyarrow-only** stays true.

## Files
- `bobframes/schema_cmd.py` — NEW: `schema [table]` lists tables / columns / dtypes / row counts from
  `schemas.TABLES` (+ on-disk row counts via pyarrow metadata). Core, no new dep.
- `bobframes/query_cmd.py` — NEW: `query "SQL"` runs SQL over the drop's Parquet via DuckDB; **lazy
  `import duckdb`** with a helpful message + exit code when the `[query]` extra is absent.
- `cli.py` — NEW `schema` and `query` verbs; `--json` for both.
- `pyproject.toml` — add `[project.optional-dependencies] query = ["duckdb>=1.0"]` (annotate
  ARCHITECTURE §3 deps via [ADR-17](../../DECISIONS.md); core `dependencies` stays `pyarrow` only).

## Changes
`schema` is always available. `query` errors helpfully (`pip install bobframes[query]`) when DuckDB is
missing — never a raw `ImportError`. Neither verb emits HTML.

## Done when
- `bobframes schema` (and `schema draws`) work in a **core** install (no DuckDB); `--json` carries
  `json_schema_version`.
- `bobframes query "SELECT ..."` works under `bobframes[query]`; without the extra it exits with the
  install hint (not a traceback).
- **Golden parity green** — no HTML produced.

## Closes
Serves the engineer "queryable Parquet + schema introspection" criterion. Establishes
[ADR-17](../../DECISIONS.md) (optional-dep boundary; core stays pyarrow-only).
