# Migration spine

> The ordered commit sequence. Carved from CLI_PLAN §14. Each commit leaves a working state and has
> its own doc with a "Done when" gate. Status lives in [STATE.md](STATE.md) — this file is the route,
> not the tracker. Commit numbers (`cNN`) are fixed from the original plan and never renumbered; v0.1
> deliberately skips c04–c10 (those are v0.2).

## v0.1 — pure extraction (ships first)

Each commit guarded by the golden parity gate ([QUALITY_GATES](reference/QUALITY_GATES.md)).

| Phase | Commit | Leaves working state of… |
|---|---|---|
| **0 Bootstrap** | [BOOTSTRAP.md](BOOTSTRAP.md) | new repo at `c:\Users\vsiva\dev\bobframes`, `_analysis` tree copied in, product files + this plan committed |
| **1 Safety net** | [c01 version](commits/v01/c01_version.md) | `__version__` exists; zero behavior change |
| | [c02 golden harness](commits/v01/c02_golden_harness.md) | synthetic `_data/` + frozen golden HTML + parity/schema/determinism tests; **enables every later refactor** |
| | [c03 hardening](commits/v01/c03_hardening.md) | atomic writes, process-tree kill on timeout, replay-skip, manifest provenance, `KEY_VERSION=1`, single UTC `now_iso` |
| **2 CLI + pkg** | [c11 cli.py dispatcher](commits/v01/c11_cli_dispatcher.md) | argparse dispatcher; `[project.scripts]`; verbs from ARCHITECTURE §4; stdlib logging |
| | [c12 replay importlib](commits/v01/c12_replay_importlib.md) | replay script located via `importlib.resources` (install-safe) |
| | [c13 replay-drift CI](commits/v01/c13_replay_drift_ci.md) | corrected drift test guarding H-6 ([ADR-5](DECISIONS.md)) |
| ~~3 Rename~~ | ~~[c14 rename](commits/v01/c14_rename.md)~~ | **COLLAPSED (ADR-7)** — package named `bobframes` from scaffold, so imports/literals/prog strings are written correctly from c01; no rename commit |
| **4 Finalize** | [c15 smoke + unit tests](commits/v01/c15_smoke_tests.md) | `smoke --data`; synthetic fallback; unit tests for keys/schemas/discovery/config |
| | [c17 CI workflow](commits/v01/c17_ci_workflow.md) | `.github/workflows/ci.yml`: unit+parity+schema+drift+determinism+perf on push; publish on tag |
| | [c18 docs](commits/v01/c18_docs.md) | README (from §13 outline) + CHANGELOG + LICENSE |
| | [c19 release](commits/v01/c19_release.md) | tag `v0.1.0` → CI publishes PyPI + GH Release; post-install verification |

## v0.2 — de-hardcoding (deferred; after v0.1 ships)

Operates on the renamed `bobframes/` package. Each guarded by parity.

| Commit | Leaves working state of… |
|---|---|
| [c04 paths constants](commits/v02/c04_paths_constants.md) | dir/file literals centralized in `paths.py` (H-18, H-19) |
| [c05 registry consolidation](commits/v02/c05_registry_consolidation.md) | table/entity/report lists derived from `schemas.TABLES` + `reports.ALL_REPORTS` (H-8–H-11, D-1) |
| [c06 tool resolver](commits/v02/c06_tool_resolver.md) | `config.resolve_tool()` + `errors`; glob version detection (H-7); `check` verb real |
| [c07 TOML config layer](commits/v02/c07_toml_config.md) | timeouts/weights/limits/regex/banlist from config; defaults reproduce today (H-12–H-14, H-16, H-17, H-21–H-23, H-30) |
| [c08 design tokens](commits/v02/c08_design_tokens.md) | tokens→TOML; `preview` verb; `export-tokens`; `--watch` (H-15, H-20; Track A) |
| [c09 classifier](commits/v02/c09_classifier.md) | engine-agnostic classifier TOML + UE preset; counter aliases (H-1–H-5) |
| [c10 env rename](commits/v02/c10_env_rename.md) | `RDC_*`→`BOBFRAMES_*` (legacy fallback); `RDC_INSIDE_ARGS` kept |
| [c16 report quality](commits/v02/c16_report_quality.md) | empty states, missing-col tolerance, cache SHA256, dashboard rename (R-13, Q-9, G-* polish) |

## Critical files (load-bearing across the migration)

- `pipeline.py` (was `run.py`) — the `python -m bobframes.parsers.parse_init_state` subprocess
  literal (write with the `bobframes` name from c01 — no rename) and the `replay_main.py` path
  construction (c12) are load-bearing.
- `qrd_harness.py` — tool discovery + timeout (c03/c06); `RDC_INSIDE_ARGS` wire kept.
- `rdcmd.py` — tool discovery mirror; convert timeout.
- `replay/replay_main.py` — **frozen**; resolved via `importlib.resources` (c12); schema dup guarded (c13).
- `tests/smoke.py` — full rewrite (c15); eliminate hardcoded `Chor bazar`/`r110565`/`2026-05-27`.
- `reports/cli.py`, `reports/ab.py` — `prog=` strings (use `bobframes.reports.*` from c01) +
  positional `root` alignment (c11).

## Reused functions (do not duplicate)

- `reports.cli.run_report(build_fn, module_name)` — reused by all 6 report verbs + `report <name>`.
- `reports.orchestrator.render_all_reports(root, log)` — reused by `render`.
- `discovery.find_drops(...)` — reused by new `smoke.py` and verbs taking `--area`/`--label`.
  (Note: single-arg parser is `discovery.parse_single_drop_arg`, **not** `_parse_drop_dirname`.)
- `lint.lint_file(path)` — reused by `bobframes lint` and inline by report builds.
- `schemas.expected_columns(stem)` — reused by parquetize verification + smoke schema assertions.
- `schemas.is_entity_table(stem)` — exists; basis for the c05 entity-table derivation.
- `paths.*` (16 public funcs) — frozen; treat as public API (`bobframes.paths`).
