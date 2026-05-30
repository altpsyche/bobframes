# c12 — replay script discovery via `importlib.resources`     release: v0.1 · phase: CLI + pkg

## Goal
Locate `replay_main.py` as a packaged resource, not by walking the project tree — so it works from
an installed wheel, not just an in-tree checkout.

## Depends on
[c11](c11_cli_dispatcher.md).

## Files
- `replay/__init__.py` — NEW: `replay_script_path()` returning a real on-disk path via
  `importlib.resources.files('<pkg>.replay').joinpath('replay_main.py')`, wrapped in `as_file()` for
  zip-import safety (extracts to temp if the wheel is ever zipped).
- `pipeline` replay-launch — replace `os.path.join(project_root, '_analysis', 'replay',
  'replay_main.py')` with `replay_script_path()`.

## Changes
1. Implement `replay_script_path()` as an `as_file()` context manager (so the temp extraction, if
   any, lives for the subprocess duration).
2. Call it where `pipeline` builds `[qrenderdoc, '--python', <script>]`.

## Done when
- Replay step resolves the script when launched from a directory other than the source tree
  (simulate by `cd` elsewhere, or `pip install -e .` and run). Force-include in `pyproject`
  (ARCHITECTURE §3) keeps `replay_main.py` on disk in the wheel.
- Golden parity green; ingest replay path unaffected on the dev machine.

## Rollback
Revert the `pipeline` line + delete `replay_script_path()`.

## Closes
Mitigates the "importlib path under zipped wheels" risk ([DECISIONS §15](../../DECISIONS.md)).
