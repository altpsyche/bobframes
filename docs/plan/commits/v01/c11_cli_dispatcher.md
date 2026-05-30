# c11 — cli.py dispatcher + `[project.scripts]`     release: v0.1 · phase: CLI + pkg

## Goal
A single argparse dispatcher exposing the verbs in [ARCHITECTURE §4](../../ARCHITECTURE.md). Wires
the installed `bobframes` binary; callable as `python -m bobframes.cli`. (Package is `bobframes` from
the scaffold — [ADR-7](../../DECISIONS.md); no `_analysis.cli` interim.)

## Depends on
[c03](c03_hardening.md).

## Files
- `cli.py` — **expand the c01 seed** (which currently handles `version` + delegates everything else
  to `run.main`). Add subparsers for `ingest`, `render`, `ab`, `report`, `catalog`, `lint`, `check`,
  `serve`, `smoke`. Positional `root` default `.`; long-flag-only; exit-code map. Replace the
  delegate-to-`run` fallback with real dispatch.
- `pyproject.toml` — `[project.scripts] bobframes = "bobframes.cli:main"` (already set in the
  scaffold; no flip — c14 collapsed).
- `reports/cli.py` — `prog=` string + positional `root` default `.` (align with §4).
- `reports/ab.py` — `--root` flag → positional default `.`; accept `--root` as hidden alias one release.

## Changes
1. Build the dispatcher; **reuse existing functions** (do not reimplement): `reports.cli.run_report`,
   `reports.orchestrator.render_all_reports`, `discovery.find_drops`, `lint.lint_file`,
   `reports.ab` entry. `version` prints `__version__` + `schemas.SCHEMA_VERSION` + `pyarrow.__version__`.
2. Switch to stdlib `logging`, INFO default, per-subparser `--verbose` → DEBUG (G-8). Keep
   `[HH:MM:SS] message` lines.
3. Map exit codes per §4 (0/1/2/3/4).

## Done when
- `python -m bobframes.cli version` → `… 0.1.0  schema 3  pyarrow X.Y.Z`.
- `python -m bobframes.cli render .` and `… ingest .` behave as the legacy entry.
- Golden parity green.

## Rollback
Delete `cli.py`; revert `pyproject` scripts + the two report-arg tweaks.

## Closes
G-8. Sets up the binary contract; verbs `preview`/`export-tokens` remain v0.2.
