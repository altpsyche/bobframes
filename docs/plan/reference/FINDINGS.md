# Code-review findings (burndown)

> Carved from CLI_PLAN §17. IDs owned here: `R-*` (reliability), `Q-*` (code quality), `D-*` (system
> design), `S-*` (scalability), `C-*` (concurrency), `M-*` (modularity), `G-*` (gaps). `resolved-by`
> names the commit that closes the row; tick `status` when it lands. References are symbol-anchored
> (no line numbers — they drift).

## Reliability — P0 (ship-blockers; → [c03](../commits/v01/c03_hardening.md))

| ID | Where | Finding | Fix | resolved-by | status |
|---|---|---|---|---|---|
| R-1 | `manifest.write_manifest` | `_manifest.json` written non-atomically; crash mid-write corrupts; catalog silently skips drop | `.tmp` then `os.replace()` | c03 | ☑ |
| R-2 | `parquetize._write_pair` | Parquet+CSV written sequentially; Parquet committed even if CSV fails (split-brain pair) | stage both `.tmp`, atomic rename, rollback both on either failure | c03 | ☑ |
| R-3 | `pipeline` done.marker write | `done.marker` bare-write after commit; crash → duplicate re-process | tmp + `os.replace()` | c03 | ☑ |
| R-4 | `qrd_harness` timeout except | `subprocess.run` kills the *direct* child, but qrenderdoc GPU/replay **grandchildren** survive and hold locks | reap the **process tree** (`taskkill /T /F /PID` or Win32 job object) — see [ADR-4](../DECISIONS.md) | c03 | ☑ |
| R-5 | `pipeline._do_parse` | `os.environ['RDC_ROOT']` set globally, never restored; later drops inherit stale value | save/restore around parse, or pass as explicit arg (folds into c10 env rename) | c03 | ☑ |
| R-6 | `pipeline` replay loop | single capture replay failure raises → aborts whole drop merge | skip + record `capture_status='replay_failed'` in manifest | c03 | ☑ |
| R-7 | `pipeline._do_parse` | returns stderr only when `rc != 0`; rc==0 parse failures lose stderr | always log stderr regardless of rc | c03 | ☑ |
| R-8 | `rdcmd` convert | `TimeoutExpired` with `capture_output=True` loses stderr | try/except, log stderr tail (~400 chars) before re-raise | c03 | ☑ |
| ~~R-9~~ | `catalog._per_capture_row_counts` | **WITHDRAWN — false positive.** `+= 1` per row IS the correct per-capture count; `+= t.num_rows` would over-count. See [ADR-3](../DECISIONS.md). | none | — | ✗ n/a |

## Reliability — P1

| ID | Where | Finding | Fix | resolved-by | status |
|---|---|---|---|---|---|
| R-10 | `parquetize` CSV read | full table accumulated in memory | stream via `pyarrow.csv.read_csv()`; revisit only if OOM | v0.2 | ☐ |
| R-11 | `parquetize._copy_sidecars` | overwrites without lock; two drops racing same shader | acceptable single-process; document | v0.2 (doc) | ☐ |
| R-12 | `pipeline` stage cleanup | `ignore_errors=True` swallows lock failures; stale tmp next run | log warning on failure; safer tmp cleanup next run | v0.2 | ☐ |
| R-13 | `reports/cache` | corrupted cache parquet silently returns empty dict | SHA256 sidecar; invalidate on mismatch | [c16](../commits/v02/c16_report_quality.md) | ☐ |
| R-14 | `parsers/parse_init_state` | `errors='replace'` substitutes bad UTF-8; partial CSV if truncated | validate chunk count; manifest `parse_status='partial'` | v0.2 | ☐ |
| R-15 | `replay/replay_main` | crash mid-run leaves stage half-written; re-run reads incomplete CSVs | per-capture tmp dir; atomic rename on clean exit | v0.2 | ☐ |

## Code quality — P1 (→ v0.2)

| ID | Where | Finding | resolved-by | status |
|---|---|---|---|---|
| Q-1 | `parquetize._apply_stable_key` | 60-line if-elif; collapse to a `dict[table → (cols, key_fn)]` loop | v0.2 | ☐ |
| Q-2 | `parquetize._cast_value` | swallows coercion errors silently → 0/0.0 | aggregate failure counts, log summary | v0.2 | ☐ |
| Q-3 | `derive_post_merge` complexity weights | magic numbers → module constant dict | [c07](../commits/v02/c07_toml_config.md) | ☐ |
| Q-4 | `derive_post_merge` zip | no length assertion; silent truncation on drift | `strict=True` (Py3.10+) | v0.2 | ☐ |
| Q-5 | `pipeline._parse_one` | args passed both positional + `RDC_ROOT`; comment disagrees | pick one (positional) | [c10](../commits/v02/c10_env_rename.md) | ☐ |
| Q-6 | report emitters | header/strip/open/close boilerplate duplicated ×6 | extract `chrome.report_page(...)` | v0.2 | ☐ |
| Q-7 | `reports/cache` + callers | `{c: t.column(c).to_pylist() ...}` repeated | `cache._to_dict_of_lists(table)` | v0.2 | ☐ |
| Q-8 | `parsers/parse_init_state` | noop self-assignment on `target_history` | delete or implement | v0.2 | ☐ |
| Q-9 | `reports/_dashboard` | underscore prefix but it's a full report | rename `dashboard.py` | [c16](../commits/v02/c16_report_quality.md) | ☐ |

## System design — P1

| ID | Finding | resolved-by | status |
|---|---|---|---|
| D-1 | 6-report list duplicated: `orchestrator._REPORT_MODULES` + `ab._MODULES` (**different names**, same content) | [c05](../commits/v02/c05_registry_consolidation.md) | ☐ |
| D-2 | `parquetize` couples to `schemas`; must verify + raise SchemaMismatch with diff | partially [c13](../commits/v01/c13_replay_drift_ci.md) + v0.2 | ☐ |
| D-3 | `pipeline` imports `reports.orchestrator` at top — fine post-rename; document expected coupling | doc | ☐ |
| D-4 | `manifest` `.get('captures') or .get('stems')` shows schema drift between old/new manifests | v0.2 (manifest_schema_version) | ☐ |
| D-5 | `derive_post_merge` callable on partial data with no guard | v0.2 (precondition check) | ☐ |

## Scalability — P2 (defer unless measured)

| ID | Finding | resolved-by |
|---|---|---|
| S-1 | replay is sequential (600s × N worst case) — investigate parallel qrenderdoc | v0.2+ |
| S-2 | parquetize merge single-threaded across tables | v0.2+ |
| S-3 | catalog full scan every run — incremental via mtime | v0.2+ |
| S-4 | global_entities full scan + O(n) memory | v0.2+ |
| S-5 | derive_post_merge full read-modify-write per table — vectorize | v0.2+ |

## Concurrency / Modularity

| ID | Finding | resolved-by |
|---|---|---|
| C-1 | `os.replace(tmp, out)` race window — acceptable single-user CLI; document non-concurrent assumption | doc (v0.2 may add file lock) |
| M-1 | new `derives/` module needs manual import — auto-discovery via `pkgutil.iter_modules` + `build()` convention | v0.2+ (relates c05) |
| M-2 | new schema table needs central edit — register via decorator | v0.2+ |
| M-3 | `probes/whatif.py` not CLI-exposed | not in v1 (documented advanced pattern) |

## Gaps / misses (production CLI checklist)

| ID | Gap | resolved-by | status |
|---|---|---|---|
| G-1 | no `--dry-run` | v0.2 (ingest) | ☐ |
| G-2 | no `--diff` between manifests/drops | v0.2 (`bobframes diff`) | ☐ |
| G-3 | no schema migration path (`SCHEMA_VERSION` bump strands `_data/`) | v1.0 (`bobframes migrate`); for v0.1 document `ingest --force` | ☐ |
| G-4 | no integrity-check verb | v0.2 (`bobframes verify`) | ☐ |
| G-5 | no CSV export verb (CSV pairs already written) | v0.2 (`bobframes export`) | ☐ |
| G-6 | manifest lacks `renderdoccmd --version` | [c03](../commits/v01/c03_hardening.md) | ☑ |
| G-7 | manifest lacks host GPU/driver/CPU/OS | [c03](../commits/v01/c03_hardening.md) | ☑ |
| G-8 | single global log level | [c11](../commits/v01/c11_cli_dispatcher.md) (stdlib logging, `--verbose`) | ☑ |
| G-9 | no `--json` structured output for CI | v0.2 | ☐ |
| G-10 | no isolated-stage testing verbs | v0.2 (`bobframes parse`/`replay`) | ☐ |
| G-11 | `stable_keys` SHA256 has no version prefix — rule change orphans keys | [c03](../commits/v01/c03_hardening.md) (`KEY_VERSION=1`; H-27) | ☑ |
| G-12 | `tests/smoke.py` brittle hardcoded constants | [c15](../commits/v01/c15_smoke_tests.md) | ☐ |

## XSS / safety — no findings (recorded)

All HTML emit paths use `chrome.h()` or `html.escape()`; `formatters.safe_chrome_text()` adds
banned-token scrubbing on top of escape; lint catches escapes that slip through. **No fix needed.**
