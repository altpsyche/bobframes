# c22 — isolated-stage verbs `parse` / `replay`     release: v0.3 · phase: CI/automation

## Goal
Expose the parse and replay pipeline stages as standalone verbs so engineers can debug one stage
without running a full ingest. No new extraction logic — thin CLI wrappers over the existing stage
functions.

## Depends on
[c10](../v02/c10_env_rename.md) (`--project-root` explicit arg; `RDC_ROOT` eliminated, R-5).
[c20](c20_json_output.md) for the `--json` summary.

## Seam extended
`pipeline._do_parse` and `pipeline._do_replay` (separable per the stage map) + `discovery.find_drops`
for area/label selection. Reuses the c12 `replay_script_path()` resolution and the c03 Popen/taskkill
harness — no parallel runner.

## Files
- `cli.py` — NEW verbs `parse` and `replay` (positional `<root>` default `.`, `--area`/`--label`/
  `--capture`, `--project-root`); call the stage functions over an existing/created stage dir; print a
  per-capture summary; `--json` summary object.
- `pipeline.py` — minor: make `_do_parse`/`_do_replay` callable from the CLI with an explicit stage
  root (no behavior change to the full-ingest call path).

## Changes
Stage verbs operate on the stage tree and never touch `_data/`/`_reports/` commit or render. Full
`ingest` path unchanged.

## Done when
- `bobframes parse <root> --area X --label Y` runs the parse stage standalone and writes stage CSVs.
- `bobframes replay <root> --area X --label Y` runs replay standalone (Windows + RenderDoc;
  self-hosted/nightly per [ADR-6](../../DECISIONS.md)); `--json` summary emitted.
- **Golden parity green** — render path untouched.

## Closes
G-10.
