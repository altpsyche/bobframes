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
| R-16 | `qrd_harness.run` (`_harness.log` open) + `run.py` commit (`os.replace` tmp→final) | **Inheritable replay-log handle inside the committed `.tmp` dir blocks the atomic commit.** `qrd_harness` opens `_stage/<cap>/_harness.log` and hands it to qrenderdoc as stdout; on Windows that OS handle is inheritable and propagates to children AND to any handle-inheriting process started meanwhile (observed: the **adb** server daemon — Android platform-tools — which respawns and grabs it). Because the log lives under `_stage` *inside* `<drop>.tmp`, the held handle makes `os.replace(tmp, final)` fail `[WinError 5] Access is denied`, failing the whole drop at commit **after** a fully successful export/parse/replay/parquetize/derive. Reproduced on the c06 real-ingest smoke (Chor bazar, 5 captures, 597199 rows): every stage green, commit failed; salvaged by killing adb + completing the rename. Broader than R-4/ADR-4 (the holder is a *third-party* process, not a replay grandchild, so tree-kill won't help). **Fixed:** stage tree relocated to a SIBLING of the commit dir (`paths.drop_stage_dir` = `<drop>.stage`, not `<drop>.tmp/_stage`); commit now happens BEFORE the (best-effort, post-commit) stage cleanup, so a held `_harness.log` can never be inside the renamed dir. Invariant guarded by `test_hardening.test_stage_dir_is_sibling_not_inside_commit_dir`. | audit 2026-06-01 real-ingest | ☑ |

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
| D-1 | 6-report list duplicated: `orchestrator._REPORT_MODULES` + `ab._MODULES` (**different names**, same content) | [c05](../commits/v02/c05_registry_consolidation.md) | ☑ |
| D-2 | `parquetize` couples to `schemas`; must verify + raise SchemaMismatch with diff | partially [c13](../commits/v01/c13_replay_drift_ci.md) + v0.2 | ☐ |
| D-3 | `pipeline` imports `reports.orchestrator` at top — fine post-rename; document expected coupling | doc | ☐ |
| D-4 | `manifest` `.get('captures') or .get('stems')` shows schema drift between old/new manifests | [c16](../commits/v02/c16_report_quality.md) (manifest schema-version guard) | ☐ |
| D-5 | `derive_post_merge` callable on partial data with no guard | v0.2 (precondition check) | ☐ |
| D-6 | `_classify_draw` exists in **two drifted copies** — `derive_post_merge._classify_draw` (has `basepass`→opaque) vs `replay_main._classify_draw` (lacks `basepass`, adds `shadowdepth` + explicit alpha check). ADR-9 says `draw_class` is host-derived, so the replay copy may be **dead** — verify consumption during c09. c09's single TOML walker collapses both. | [c09](../commits/v02/c09_classifier.md) (verified at [c27](../commits/v04/c27_engine_presets.md)) | ☐ |
| D-7 | **Frozen DECISIONS versioning contract is UNBUILT.** `render`/`catalog`/`ab` must refuse on `manifest.schema_version != schemas.SCHEMA_VERSION` (→ exit 1, fix `ingest --force`); code grep shows `reports/` has **zero** schema-version checks, `catalog.py` only records it. Load-bearing for [c24](../commits/v03/c24_verify.md) (verify) + [c35](../commits/v05/c35_schema_widening.md) (the first bump's migration story). | [c16](../commits/v02/c16_report_quality.md) (`manifest.assert_compatible`) | ☐ |
| D-8 | **Drill HTML embeds writer-dependent bytes → cross-env output divergence (root cause behind [ADR-11](../DECISIONS.md)).** `html.template._file_size_label` renders `os.path.getsize(<table>.parquet/.csv)` as `KB` into the per-drop drill page; the on-disk size depends on the pyarrow writer (pa17 `15.1 KB` vs pa21 `12.3 KB`), so the "golden" HTML is not byte-stable across the matrix and ADR-11 pins parity to one cell to compensate. Fix the **content** so it stops carrying env-sensitive bytes: render a writer-independent figure (logical/uncompressed bytes or row count) or drop the size span; then the byte-snapshot can hold across pyarrow versions. (The companion pass_gpu `pct_share` 1-ULP-at-`.2f` flip is genuinely numpy-build-level and stays accepted under ADR-11 — D-8 is only the *fixable* half.) Output-changing → its commit refreshes the golden. | [c06a](../commits/v02/c06a_drill_size_dehardcode.md) | ☑ (writer-KB half dropped; float-ULP stays under ADR-11) |
| D-9 | **`html.template._TABLE_DISPLAY_ORDER` is pinned empirically, not understood.** c05 kept it as an explicit presentation tuple because it matches neither `schemas.TABLES` nor catalog order ("verified empirically, can't be derived"). The *reason* the within-category display order differs is unrecorded, so a future schema/catalog change could silently break it. Recover and document the ordering's origin (or prove it arbitrary and pick a derivable rule). | v0.2 (doc/derive; audit 2026-06-01) | ☐ |

## Scalability — P2 (defer unless measured)

| ID | Finding | resolved-by |
|---|---|---|
| S-1 | replay is sequential (600s × N worst case) — investigate parallel qrenderdoc | v0.6 (measure-then-optimize; profile a real multi-capture wall-clock first — [ROADMAP](../ROADMAP.md)) |
| S-2 | parquetize merge single-threaded across tables | v0.2+ |
| S-3 | catalog full scan every run — incremental via mtime | v0.2+ |
| S-4 | global_entities full scan + O(n) memory | v0.2+ |
| S-5 | derive_post_merge full read-modify-write per table — vectorize | v0.2+ |

## Concurrency / Modularity

| ID | Finding | resolved-by |
|---|---|---|
| C-1 | `os.replace(tmp, out)` race window — acceptable single-user CLI; document non-concurrent assumption | doc (v0.2 may add file lock) |
| M-1 | new `derives/` module needs manual import — auto-discovery via `pkgutil.iter_modules` + `build()` convention | [c38](../commits/v06/c38_plugins.md) (relates c05) |
| M-2 | new schema table needs central edit — register via decorator | [c38](../commits/v06/c38_plugins.md) |
| M-3 | `probes/whatif.py` not CLI-exposed | not in v1 (documented advanced pattern) |

## Gaps / misses (production CLI checklist)

| ID | Gap | resolved-by | status |
|---|---|---|---|
| G-1 | no `--dry-run` | [c23](../commits/v03/c23_dry_run.md) | ☐ |
| G-2 | no `--diff` between manifests/drops | [c25](../commits/v03/c25_diff.md) | ☐ |
| G-3 | no schema migration path (`SCHEMA_VERSION` bump strands `_data/`) | v1.0 (`bobframes migrate`); [c35](../commits/v05/c35_schema_widening.md) documents `ingest --force` at the first bump | ☐ |
| G-4 | no integrity-check verb | [c24](../commits/v03/c24_verify.md) | ☐ |
| G-5 | no CSV export verb (CSV pairs already written) | [c26](../commits/v03/c26_export.md) | ☐ |
| G-6 | manifest lacks `renderdoccmd --version` | [c03](../commits/v01/c03_hardening.md) | ☑ |
| G-7 | manifest lacks host GPU/driver/CPU/OS | [c03](../commits/v01/c03_hardening.md) | ☑ |
| G-8 | single global log level | [c11](../commits/v01/c11_cli_dispatcher.md) (stdlib logging, `--verbose`) | ☑ |
| G-9 | no `--json` structured output for CI | [c20](../commits/v03/c20_json_output.md) | ☐ |
| G-10 | no isolated-stage testing verbs | [c22](../commits/v03/c22_isolated_stages.md) | ☐ |
| G-13 | `texture_usage` computed in pipeline + tracked in catalog but never surfaced as a report | [c28](../commits/v04/c28_texture_usage_report.md) | ☐ |
| G-11 | `stable_keys` SHA256 has no version prefix — rule change orphans keys | [c03](../commits/v01/c03_hardening.md) (`KEY_VERSION=1`; H-27) | ☑ |
| G-12 | `tests/smoke.py` brittle hardcoded constants | [c15](../commits/v01/c15_smoke_tests.md) | ☑ |
| G-14 | **Golden parity gates rendered HTML only — Parquet outputs are ungated.** `test_parity` (via `_render_util.rendered_html_files`) walks `.html` and explicitly skips `_cache`/`_data`, so "byte-parity green" means *render logic unchanged*, NOT *all outputs unchanged*: c05's `_global_entities` row-order change was invisible to the gate and "accepted." Add a Parquet-snapshot parity gate (stable schema + row order, or a content hash per table) so data-path regressions are caught, not just HTML. | [c06b](../commits/v02/c06b_parquet_parity_gate.md) (writer-independent logical digest over `_data/**/*.parquet`, full matrix; relates [c21](../commits/v03/c21_regression_gating.md); audit 2026-06-01) | ☑ |

## XSS / safety — no findings (recorded)

All HTML emit paths use `chrome.h()` or `html.escape()`; `formatters.safe_chrome_text()` adds
banned-token scrubbing on top of escape; lint catches escapes that slip through. **No fix needed.**
