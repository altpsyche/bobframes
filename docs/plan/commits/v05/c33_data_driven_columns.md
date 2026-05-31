# c33 — data-driven class columns + extension-table mechanism     release: v0.5 · phase: Graphics-API epic

## Goal
Remove the last hardcoded coupling between the class list and the report columns, and add the
**unified-core + per-API extension-table** mechanism to the schema registry — both **without changing
GL output**. No new columns are emitted yet; this is the mechanism that c34/c35 use.

## Depends on
[c32](c32_pipeline_state_adapter.md). [ADR-14](../../DECISIONS.md) (unified core + extension tables).
Builds on [c05](../v02/c05_registry_consolidation.md) (the `schemas.TABLES` `category` field) and
[c09](../v02/c09_classifier.md) (`classifier.class_order`).

## Seam extended
`schemas.TABLES` (add an `api` field alongside the c05 `category`; default `api="core"` → applies to
all APIs), the report `draws_by_class_*` aggregation (generate from `classifier.class_order` instead of
a hardcoded list), `parquetize` (already auto-fills missing columns — extension tables absent for a
given API simply don't appear).

## Files
- `schemas.py` — extend each `TABLES` entry with an `api` tag (`"core"` default; `"gl"`/`"vk"` reserved
  for extension tables added in c35). Helpers: `core_tables()`, `api_tables(api)`.
- `reports/*` (draws-by-class + any class-keyed report) — generate the per-class columns from
  `classifier.class_order` rather than the inline list (equals `chrome.DRAW_CLASSES` today → identical).
- `parquetize` / `catalog` — iterate `schemas.core_tables()` for the GL path so behavior is unchanged.

## Changes
Mechanism + generation only. `class_order` today equals the hardcoded report list, so generated columns
are **byte-identical**. No extension table is registered yet → **no new columns, no schema bump**.

## Done when
- GL golden **byte-identical** (parity green) — generated class columns match the former hardcoded list.
- Schema regression green; replay-drift green.
- `schemas.api_tables("vk")` is empty (mechanism present, no tables yet).
- **No `SCHEMA_VERSION` change.**

## Closes
H-37 mechanism (the `gl*_count` columns can now move to a `"gl"` extension table in c35 without
touching core). Sets up c34/c35.
