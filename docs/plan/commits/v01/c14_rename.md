# c14 — atomic rename `_analysis` → `bobframes`     release: v0.1 · phase: Rename

> **⚠️ COLLAPSED — do not execute.** Per [ADR-7](../../DECISIONS.md), the package is named
> `bobframes` from the scaffold, so there is no rename to perform. This file is kept for provenance
> and link stability. The "Done when" reviewer checks below are folded into c01 (write all
> imports/literals/prog strings with the `bobframes` name) and verified by the c02 parity gate.
> Skip to [c15](c15_smoke_tests.md).

## Goal (historical — superseded)
The disruptive, atomic rename. Single commit, no half-state, no shim. After it, the package is
`bobframes`, the binary installs, and `python -m _analysis.*` is gone.

## Depends on
[c11](c11_cli_dispatcher.md), [c12](c12_replay_importlib.md), [c13](c13_replay_drift_ci.md). Do on a
quiet day — it touches every module. The c02 parity gate is the bisect safety net.

## Files (whole package + a few literals)
- `git mv _analysis bobframes` (preserve history).
- Sweep imports: `from _analysis…` / `import _analysis…` → `bobframes…` across all modules.
- `pipeline` subprocess literal: `'-m', '_analysis.parsers.parse_init_state'` → `'-m',
  'bobframes.parsers.parse_init_state'`.
- `replay_script_path()` package arg → `bobframes.replay` (from c12).
- `reports/cli.py` + `reports/ab.py` `prog=` strings → `bobframes.reports.*`.
- `pyproject.toml`: `name = "bobframes"`, `[project.scripts] bobframes = "bobframes.cli:main"`,
  `[tool.hatch.version] path = "bobframes/_version.py"`, force-include paths.

## Changes
Mechanical rename + literal/prog/script updates. No logic change. `_analysis/` directory ceases to
exist; no compatibility shim ([DECISIONS — backwards-compat](../../DECISIONS.md)).

## Done when
- `pip install -e .` then `bobframes version` / `bobframes check` / `bobframes smoke` all run.
- `grep -r "_analysis" bobframes/` → zero hits (except the README "Migrating from `_analysis`" prose
  and this plan's history).
- `python -m _analysis.run` → `ModuleNotFoundError` (expected — it's the documented hard break).
- Golden parity + schema + drift + determinism all green.
- Reviewer checklist (DECISIONS §15): imports clean, dir gone, `pyproject` present, `check` runs.

## Rollback
Single commit — `git revert`. No partial state to untangle.

## Closes
D-3 (coupling acceptable post-rename, documented). Q-9 dashboard rename deferred to
[c16](../v02/c16_report_quality.md).
