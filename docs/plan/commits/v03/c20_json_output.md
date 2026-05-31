# c20 — `--json` global flag + versioned `json_schema_version`     release: v0.3 · phase: CI/automation

## Goal
Give every verb a machine-readable output mode for CI consumers. `--json` emits a single JSON object
to **stdout**; human logs stay on **stderr**. The JSON is a **versioned contract** from day one
([ADR-16](../../DECISIONS.md)) — an independent `json_schema_version` (not the data `SCHEMA_VERSION`).
Purely additive: no HTML is produced, so the golden is untouched.

## Depends on
v0.2 shipped (c11 cli dispatcher; c05 `ALL_REPORTS` for report metadata). First commit of v0.3.

## Seam extended
`cli.py` argparse `common` parser (global flags); the existing `_cmd_*` handlers; the exit-code map
(0/1/2/3/4). No parallel CLI — one global flag threaded to handlers.

## Files
- `bobframes/jsonout.py` — NEW: `JSON_SCHEMA_VERSION = 1`; `emit(obj)` writes
  `{"json_schema_version": 1, ...}` to stdout (one object, newline-terminated); helpers for the common
  envelope (verb, ok, exit_code).
- `cli.py` — add `--json` to the `common` parser; each handler builds a result dict and routes through
  `jsonout.emit` when set. Logging already on stderr via `_configure_logging` (G-8) — verify no INFO
  leaks to stdout under `--json`.
- `tests/test_json_contract.py` — NEW (`test_*` discovery): asserts `version --json` / `check --json`
  carry `json_schema_version` and the documented key set; asserts stdout is valid single-object JSON.

## Changes
JSON shapes for `version` (version/schema/pyarrow), `check` (resolved tool paths + precedence),
`catalog` (drop/capture counts), `report`-metadata, and the v0.3 verbs as they land (`verify` c24,
`diff` c25, `export` c26). Bump `JSON_SCHEMA_VERSION` only on a breaking JSON-shape change; document
the cadence in the ADR.

## Done when
- `bobframes version --json` and `bobframes check --json` emit valid JSON carrying
  `json_schema_version`; nothing but the JSON object hits stdout (logs on stderr).
- `test_json_contract.py` green; pins `json_schema_version` + the key set per verb.
- **Golden parity green** — no HTML emitted by `--json`; rendered output unchanged.

## Closes
G-9. Establishes [ADR-16](../../DECISIONS.md) (the versioned `--json` contract) for every later verb.
