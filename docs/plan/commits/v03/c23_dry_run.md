# c23 — `ingest --dry-run`     release: v0.3 · phase: CI/automation

## Goal
Let a user (and CI) see exactly what an ingest *would* do — drops found, captures, stages, output
paths, resolved tool versions — without touching the filesystem.

## Depends on
[c20](c20_json_output.md) (`--json` plan). Reuses [c06](../v02/c06_tool_resolver.md) `resolve_tool`
for the tool-version preview.

## Seam extended
`pipeline.main` / `process_drop` preflight + `discovery.find_drops` + `config.resolve_tool`. The plan
is assembled from the same resolution the real run uses — no parallel planner.

## Files
- `pipeline.py` — thread a `dry_run` flag from `main` through `process_drop`; before any side effect
  (export/parse/replay/commit/marker) print the resolved plan and return 0.
- `cli.py` — add `--dry-run` to the `ingest` subparser; `--json` emits the plan object.

## Changes
Dry-run resolves drops/captures/stage+output paths/tool versions and prints them; **no files created
or modified**. Real ingest path unchanged when the flag is absent.

## Done when
- `bobframes ingest <root> --dry-run` prints the plan and exits 0 with **zero filesystem changes**
  (verify via before/after mtime scan in a test).
- `--json` emits the plan carrying `json_schema_version`.
- **Golden parity green.**

## Closes
G-1.
