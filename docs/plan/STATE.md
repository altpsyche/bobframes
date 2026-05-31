# BobFrames — implementation state

> The resumption anchor. A fresh session reads this first, then opens the `current` commit doc.
> Update the three live fields (`current`, `last_session`, `next_action`) and the checklists before
> you stop. This file is the single source of truth for progress — commit docs mirror status but
> defer to this.

```
active_release: v0.2    (v0.1 COMPLETE — bobframes 0.1.0 live on PyPI 2026-05-31)
current:        c06_tool_resolver    (status: not-started — c05 DONE)
last_session:   2026-05-31 — c05 DONE (registry consolidation, H-8/H-9/H-10/H-11 + D-1). schemas.TABLES
                values migrated from the raw 3-tuple to a TableSpec NamedTuple (cols, size_class,
                is_entity, category, api="core" reserved for c33). The dict was REORDERED to the old
                catalog._CATALOG_TABLE_KEYS order so catalog can derive `tuple(schemas.TABLES.keys())`
                byte-identically (render_root bakes the catalog column order into the golden root
                index.html). Added helpers table_category()/entity_tables(); expected_columns/
                is_entity_table/size_class now read named fields. catalog.py: _CATALOG_TABLE_KEYS =
                tuple(schemas.TABLES.keys()). global_entities.py: iterate schemas.entity_tables(), id_col
                by convention (col after stable_key), kind = depluralize(stem) + {render_targets:texture}
                override. template.py: dropped _CATEGORY_MAP — category now from the record; within-cat
                DISPLAY order kept in a presentation-only _TABLE_DISPLAY_ORDER tuple (a third ordering
                that matches neither TABLES nor catalog order — verified empirically — so it can't be
                derived). reports/__init__.py: NEW all_reports() accessor + register_report() (lazy
                imports; runtime-augmentable per c38; frozen ALL_REPORTS tuple intentionally rejected);
                orchestrator + ab both consume it (drops _REPORT_MODULES/_MODULES). test_schemas_unit
                fixed (5-field record unpack). Baseline 32-green BEFORE; 32-green AFTER, byte-identical
                (no golden refresh). Scratch in-memory sanity: a dummy is_entity table auto-appears in
                catalog + entity_tables + template (tails its category; existing order preserved).
                _global_entities row order shifts (ungated parquet, not in golden) — accepted.
next_action:    Do c06 — config.resolve_tool() + errors.py + glob version detection (H-7). Open
                commits/v02/c06_tool_resolver.md and do exactly that commit. NEW config.py
                (resolve_tool: BOBFRAMES_* env > [tools] config > shutil.which > known Win paths >
                ToolNotFound) + errors.py (ToolNotFound/PipelineError/exit-map); rewire rdcmd.py +
                qrd_harness.py off inline discovery (keep _SEP + RDC_INSIDE_ARGS wire); make `check`
                real (exit 0/3). Golden parity green (discovery doesn't touch render). Then c07->c10,
                c16. Roadmap: ROADMAP.md + commits/v03..v06 (c20-c39) + ADR-14..22. GIT: still on branch
                `v0.2-roadmap-c04` (off main @dedfdfc; now +ea68a63 docs +d8f61d7 c04 +<c05>; UNPUSHED).
                REAL-INGEST: run the deferred real-rdc smoke AFTER c06 — one run covers c04+c05+c06's
                ingest-path changes (ADR-6). Post-release nit (non-blocking): bump CI actions off Node20
                (checkout@v5/setup-python@v6 before 2026-06-16).
DONE-2026-05-31: c19 — bobframes 0.1.0 PUBLISHED. tag v0.1.0 -> CI publish job green (OIDC trusted
                publishing, ubuntu). Live on PyPI (wheel + sdist) + GitHub Release with both assets.
                Post-install verify from a clean PyPI install: version (0.1.0 schema 3 pyarrow 21.0.0),
                check (tools resolve), smoke render-only (9 pages, lint clean) all exit 0.
former_next:    c19 release-ops. CI GREEN confirmed after ADR-11 parity-pinning. Remote is
                github.com/altpsyche/bobframes; repointed pyproject [project.urls] + CHANGELOG refs
                mayhem-studios -> altpsyche (ADR-12) so PyPI metadata links resolve. REMAINING:
                (1) push the ADR-12 URL-fix commit; (2) set PYPI_API_TOKEN secret in altpsyche/
                bobframes via OIDC Trusted Publishing (ADR-13 — NO token/secret; publish job moved to
                ubuntu + id-token: write + pypa/gh-action-pypi-publish); (3) `git tag v0.1.0 &&
                git push origin v0.1.0` -> publish job (outward+IRREVERSIBLE — authorize first);
                (4) post-install verify per c19 Done-when.
blockers:       c19 needs the PyPI pending publisher saved (altpsyche/bobframes/ci.yml) + an authorized
                irreversible tag push. CI green; URLs fixed; PyPI name free; no token needed (ADR-13).
blockers:       none. (Run tests via: .venv\Scripts\python -m pytest bobframes/tests)
```

## v0.1 — extraction (ships first)

| | Commit | Status |
|---|---|---|
| ☑ | [c01 version](commits/v01/c01_version.md) | **done** — `import bobframes` → 0.1.0 |
| ☑ | [c02 golden harness + parity](commits/v01/c02_golden_harness.md) | **done** — 4 tests green (parity/schema/determinism/perf), commit f8cf833 |
| ☑ | [c03 reliability hardening](commits/v01/c03_hardening.md) | **done** — atomic writes, tree-kill, replay-skip, KEY_VERSION=1, provenance; 11 tests green |
| ☑ | [c11 cli.py dispatcher](commits/v01/c11_cli_dispatcher.md) | **done** — full subcommand CLI + stdlib logging (G-8); 11 tests green |
| ☑ | [c12 replay importlib.resources](commits/v01/c12_replay_importlib.md) | **done** — `replay_script_path()` resolves from wheel; 11 tests green |
| ☑ | [c13 replay-drift CI guardrail](commits/v01/c13_replay_drift_ci.md) | **done** — `test_replay_drift.py` ast-diffs replay `*_COLS` vs `schemas.py` (Option A / ADR-9); 12 tests green |
| ✗ | [c14 rename](commits/v01/c14_rename.md) | **COLLAPSED** — package is `bobframes` from scaffold (ADR-7) |
| ☑ | [c15 smoke rewrite + unit tests](commits/v01/c15_smoke_tests.md) | **done** — `--data`-driven smoke (render-only default) + 3 unit files (`test_stable_keys`/`test_schemas_unit`/`test_discovery`); 32 tests green |
| ☑ | [c17 CI workflow](commits/v01/c17_ci_workflow.md) | **done** — `.github/workflows/ci.yml`: gate matrix + tag-gated publish; YAML+gate cmds validated, build dry-checked |
| ☑ | [c18 README + CHANGELOG + LICENSE](commits/v01/c18_docs.md) | **done** — README (§13) + CHANGELOG [0.1.0] + MIT LICENSE; `lint README.md CHANGELOG.md` green |
| ☑ | [c19 tag v0.1.0](commits/v01/c19_release.md) | **done** — bobframes 0.1.0 live on PyPI + GH Release (OIDC); post-install verify green |

## v0.2 — de-hardcoding (deferred)

| | Commit | Status |
|---|---|---|
| ☑ | [c04 paths.py constants](commits/v02/c04_paths_constants.md) | **done** — 10 layout constants in paths.py; literals swept from all modules + tests; 32 green, byte-parity (H-18/H-19) |
| ☑ | [c05 registry from `schemas.TABLES`](commits/v02/c05_registry_consolidation.md) | **done** — TableSpec record (api reserved); catalog/entities/template/reports all derive; 32 green, byte-parity (H-8/9/10/11, D-1) |
| ☐ | [c06 tool resolver + glob version detect](commits/v02/c06_tool_resolver.md) | deferred |
| ☐ | [c07 TOML config layer](commits/v02/c07_toml_config.md) | deferred |
| ☐ | [c08 design tokens TOML + preview](commits/v02/c08_design_tokens.md) | deferred |
| ☐ | [c09 engine-agnostic classifier](commits/v02/c09_classifier.md) | deferred |
| ☐ | [c10 env-var rename `RDC_*`→`BOBFRAMES_*`](commits/v02/c10_env_rename.md) | deferred |
| ☐ | [c16 report-quality polish](commits/v02/c16_report_quality.md) | deferred |

## v0.3 — CI/automation surface (planned — [ROADMAP](ROADMAP.md))

| | Commit | Status |
|---|---|---|
| ☐ | [c20 --json output](commits/v03/c20_json_output.md) | planned |
| ☐ | [c21 regression gating](commits/v03/c21_regression_gating.md) | planned |
| ☐ | [c22 isolated stages](commits/v03/c22_isolated_stages.md) | planned |
| ☐ | [c23 --dry-run](commits/v03/c23_dry_run.md) | planned |
| ☐ | [c24 verify](commits/v03/c24_verify.md) | planned |
| ☐ | [c25 diff](commits/v03/c25_diff.md) | planned |
| ☐ | [c26 export](commits/v03/c26_export.md) | planned |

## v0.4 — Engine breadth + ergonomics (planned)

| | Commit | Status |
|---|---|---|
| ☐ | [c27 engine presets](commits/v04/c27_engine_presets.md) | planned |
| ☐ | [c28 texture_usage report](commits/v04/c28_texture_usage_report.md) | planned |
| ☐ | [c29 overdraw heatmap](commits/v04/c29_overdraw_heatmap.md) | planned |
| ☐ | [c30 schema + query](commits/v04/c30_query_schema.md) | planned |
| ☐ | [c31 mesh/material report](commits/v04/c31_mesh_material_report.md) | planned |

## v0.5 — Graphics-API adapter epic (planned — SCHEMA_VERSION 3→4 at c35)

| | Commit | Status |
|---|---|---|
| ☐ | [c32 PipelineStateAdapter](commits/v05/c32_pipeline_state_adapter.md) | planned |
| ☐ | [c33 data-driven columns](commits/v05/c33_data_driven_columns.md) | planned |
| ☐ | [c34 Vulkan extraction](commits/v05/c34_vulkan_extraction.md) | planned |
| ☐ | [c35 schema widening](commits/v05/c35_schema_widening.md) | planned |

## v0.6+ — Cross-platform + leads + plugins (planned)

| | Commit | Status |
|---|---|---|
| ☐ | [c36 cross-platform](commits/v06/c36_cross_platform.md) | planned |
| ☐ | [c37 historical dashboard](commits/v06/c37_historical_dashboard.md) | planned |
| ☐ | [c38 plugins](commits/v06/c38_plugins.md) | planned |
| ☐ | [c39 Figma sync](commits/v06/c39_figma_sync.md) | planned |

## Status legend
`not-started` → `doing` → `done`. Use `blocked: <reason>` when stuck and record it under `blockers`.

## Session log (append newest on top; one line each)
- 2026-05-31 — c05 DONE (registry consolidation; H-8/9/10/11 + D-1). Migrated schemas.TABLES values to
  a TableSpec NamedTuple (cols, size_class, is_entity, category, api="core" reserved for c33) and
  REORDERED the dict to the old catalog key order so `catalog._CATALOG_TABLE_KEYS = tuple(TABLES.keys())`
  stays byte-identical (render_root bakes catalog column order into the golden root index.html). Added
  table_category()/entity_tables(); helpers read named fields. global_entities now iterates
  entity_tables() with id_col-by-convention + depluralized kind ({render_targets:texture} override).
  template dropped _CATEGORY_MAP — category from the record; within-category DISPLAY order kept as a
  presentation-only _TABLE_DISPLAY_ORDER tuple (empirically a third distinct ordering vs TABLES/catalog,
  so it cannot be derived — exactly one of {catalog,template} must keep an explicit order; user chose
  catalog-derives). reports/__init__ gained all_reports()+register_report() (lazy, runtime-augmentable
  for c38; frozen ALL_REPORTS rejected); orchestrator+ab consume it (dropped _REPORT_MODULES/_MODULES).
  test_schemas_unit fixed for the 5-field record. Baseline 32-green before, 32-green after, byte-identical
  (no golden refresh). In-memory scratch check: a dummy is_entity table auto-appears in catalog +
  entities + template, tailing its category with existing order intact. _global_entities row order shifts
  (ungated parquet, not in golden) — accepted. Verified forward-fit with c06/c33/c38/ADR-14. current → c06.
- 2026-05-31 — c04 DONE (first v0.2 implementation commit). Centralized the layout literals in
  paths.py: 10 module constants (DATA_DIR/REPORTS_DIR/CACHE_DIR/STAGE_DIR/DRILL_DIR/AB_DIR/TMP_SUFFIX/
  MANIFEST_NAME/DONE_MARKER/INDEX_HTML); paths.py funcs + manifest/catalog/run/parquetize/html.template/
  reports.{cache,cli,chrome,_dashboard} + the 5 test fixtures now reference them. Reused existing paths
  funcs (reports_dir, reports_cache_dir) where they matched; added no new functions (API gained only
  constants). render_root's relative-URL strings ('_reports/...', '_data/...') routed through the
  constants too (identical bytes). TMP_SUFFIX='.tmp' (doc said '_tmp' — typo; real value kept for
  parity). Verified: baseline 32-green before, 32-green after (test_parity/schema/determinism/perf/
  hardening/smoke all pass → byte-identical, no golden refresh). Grep gate clean: the 4 gated literals
  remain only in paths.py + two `#` comments. H-18/H-19 ticked. current advances to c05.
- 2026-05-31 — v0.2+ ROADMAP produced (planning session; no code). Turned V02_PLANNING_PROMPT.md into:
  new ROADMAP.md (vision + measurable per-persona success + v0.2->v0.6 phasing); 20 per-commit docs
  c20-c39 under commits/v03..v06/ (CI/automation -> engine+ergonomics -> Vulkan adapter epic ->
  cross-platform+plugins); ADR-14..22 appended to DECISIONS.md (multi-API unified-core+extension schema,
  Vulkan-first, versioned --json, query optional extra, cross-platform@v0.6, trusted-local plugins,
  GH-Release sample, generic-first presets, per-API/engine golden); MIGRATION.md v0.3-v0.6 spine tables;
  FINDINGS (G-1/2/4/5/9/10 repointed to c20-c26, M-1/2->c38, new D-6 classify-draw drift + G-13
  texture_usage, S-1->v0.6) + HARDCODE (new H-36/37 graphics-API, H-38 platform process model) updates;
  ARCHITECTURE §3 (deps) + §12 (cross-platform) annotated by ADR pointer (frozen, not rewritten).
  Mapped all three breadth seams against real code via Explore agents (no line numbers). Strategic
  decisions locked with the user (8 of them). current stays c04 — v0.2 execution is unchanged and next.
- 2026-05-31 — c19 DONE: bobframes 0.1.0 RELEASED. Switched publish to PyPI Trusted Publishing
  (OIDC, ADR-13) — no token; user saved a pending publisher (altpsyche/bobframes/ci.yml). Pushed main
  (CI green on OIDC workflow d11c84e), then tagged v0.1.0 + pushed -> publish job green: build ->
  OIDC upload -> GH Release. Verified live: PyPI bobframes 0.1.0 (wheel + sdist), GH Release v0.1.0
  with both assets. Post-install from clean PyPI install (uv isolated): version / check / smoke
  render-only all exit 0. v0.1 extraction release COMPLETE; v0.2 de-hardcoding (c04+) is next.
- 2026-05-31 — CI green after ADR-11 fix (user confirmed). Release prep: remote is altpsyche/
  bobframes, but pyproject [project.urls] + CHANGELOG link refs pointed at mayhem-studios -> would
  404 on the PyPI page. Repointed all 5 URLs to altpsyche (ADR-12; author email @mayhem-studios.com
  left as the real contact); annotated frozen ARCHITECTURE §3. Lint clean, pyproject parses. c19 now
  gated only on: set PYPI_API_TOKEN + authorize the irreversible tag push.
- 2026-05-31 — CI first-push RED, root-caused + fixed (ADR-11). Matrix failed on {3.10,*} and
  {3.12,pa17}; passed only {3.12,pa21}/{3.13,pa21}. Reproduced each cell locally via `uv run
  --isolated --python X --with pyarrow==Y` rendering synthetic + diffing golden (read-only). Two
  independent env-variable bytes in the golden HTML: (A) drill page prints parquet on-disk KB ->
  differs by pyarrow writer (pa17 15.1 vs pa21 12.3 KB); (B) pass_gpu bar-width pct_share flips
  0.62->0.63 on py3.10 (1-ULP numpy-build diff at .2f boundary). Each cell diverged in exactly 1
  file; all functional gates + determinism (within-env) green everywhere. Fix: pin test_parity to
  canonical cell (py3.12+pa21) in ci.yml (`--ignore=test_parity.py` on all cells + a canonical-only
  test_parity step); appended ADR-11, noted QUALITY_GATES §21.6. Validated split locally: 31 + 1 = 32
  green. Re-push needed to confirm matrix green.
- 2026-05-31 — pre-release real-rdc validation: ran `bobframes smoke --data` on a junctioned temp
  root holding the real Chor bazar/2026-05-27_r110565 drop (5 captures; C:\tmp, Downloads inputs
  read-only via junction, removed safely after). Full pipeline green: parse 5x, live qrenderdoc
  replay 5x rc=0 (~176-218s each), parquetize 597199 rows, program_transitions 415, pass_class_
  breakdown 4245, atomic commit, catalog 1 drop/5 captures, global_entities 16651, 7 reports +
  dashboard + root index, lint clean -> exit 0. This is the first end-to-end run of the packaged
  ingest path (c12 replay_script_path resolution + c03 Popen/taskkill harness had only been mocked);
  schema-match on real parquet validates the H-6 dup beyond the static drift test. PyPI name free.
  c19 left BLOCKED on release-ops (no remote / token / authorized irreversible push).
- 2026-05-31 — c18 done: wrote the user-facing README.md from the §13 outline (requirements, install,
  quickstart, commands table from ARCHITECTURE §4, external tools, output layout from paths.py, the
  _analysis->bobframes migration as an ASCII table, troubleshooting incl. the G-3 `ingest --force`
  schema-migration note, advanced). Finalized CHANGELOG.md to Keep-a-Changelog with a [0.1.0] section
  (KEY_VERSION=1 key-format note, Windows-only + hard-rename `_analysis` removal callouts) and an
  empty [Unreleased]. LICENSE was already standard MIT (no change). Both .md pass the banlist gate
  `bobframes lint README.md CHANGELOG.md` (exit 0) — required dropping every arrow/em-dash and banned
  word (Keep-a-Changelog's "notable" -> reworded; avoided "the following"/"overview"/"etc."). LICENSE
  itself trips lint only because it's non-.md (linted as HTML) and MIT text contains "the following
  conditions" — left as-is (immutable legal text, not in the gate). Not advancing date assertions:
  CHANGELOG [0.1.0] is dated 2026-05-31; c19 confirms at tag. pytest 32 green.
- 2026-05-31 — packaging fix (ADR-10): dropped the redundant `"bobframes/tests/data"` wheel
  force-include in pyproject.toml. The .gitignore negation makes the fixtures tracked, so
  packages=["bobframes"] already ships them; the force-include added a 2nd copy → ~65 duplicate zip
  entries. Verified: wheel now 130/130 unique, 0 dups, still ships replay_main.py + 54 synthetic
  parquet + 2 manifests + 9 golden html; twine check passes. Kept the replay_main.py force-include
  (no dup, §3-justified). Annotated frozen ARCHITECTURE §3 with the ADR-10 pointer (not rewritten).
  pytest 32 green. Not a plan commit — current stays c18.
- 2026-05-31 — c17 done: added .github/workflows/ci.yml. test job runs on push/PR (windows-latest ×
  py{3.10,3.12,3.13} × pyarrow{17,21}); excluded the {3.13,17} cell since pyarrow 17 has no cp313
  wheel (3.13 support landed in pyarrow 18) — a faithful deviation from §21.6's literal grid. Steps:
  install + pin pyarrow, one `pytest bobframes/tests -v` (subsumes §21.6's per-file gate list since
  files are test_*.py — `tests/unit_*.py`→test_stable_keys/test_schemas_unit/test_discovery, etc.),
  `bobframes smoke` (render-only), lint golden via Get-ChildItem enumeration. publish job is v*-tag-
  gated (build → twine upload → softprops GH release), inert until c19. Validated YAML structure and
  ran every gate command locally (pytest 32 green, smoke 0, lint golden 0); dry-validated the build
  (python -m build + twine check → both wheel & sdist PASSED). Found a wheel DUPLICATE-entry warning:
  packages=["bobframes"] already ships tests/data, force-include re-adds it (ARCHITECTURE §3 frozen →
  deferred to an ADR in c18/c19). CI green-on-push not verified (no remote push this session).
- 2026-05-31 — c15 done: full rewrite of tests/smoke.py (G-12). Removed AREA='Chor bazar'/
  DROP_LABEL='r110565'/DROP_DATE + the __file__-walked ROOT. Two modes: no --data → render-only vs
  bundled synthetic via _render_util.render_fresh (CI-safe, no .rdc/GPU); --data DIR → full ingest
  using discovery.find_drops to auto-pick area+latest drop. Both assert schema match + stable_key +
  catalog + lint-clean HTML; CSV-pair check gated to full mode (synthetic is parquet-only, ADR-8).
  Wired --data + pixel_grid through cli._cmd_smoke (§4 surface unchanged). Added 3 unit files named
  test_* (NOT the doc's unit_* — no python_files override, default discovery): test_stable_keys
  (version/normalize/empty-contract/order-invariance), test_schemas_unit (expected_columns roundtrip,
  ID_COLS prefix, dtype totality), test_discovery (latest-drop pick + no-fallback when newest empty,
  filters, capture sort, parse_single_drop_arg). pytest 32 green; `bobframes smoke` exit 0. Full
  --data ingest path needs Windows+RenderDoc (self-hosted/nightly, ADR-6) — not exercised here.
- 2026-05-31 — c13 done: new tests/test_replay_drift.py ast-extracts replay_main.py `*_COLS` (resolves
  `ID_COLS + (...)`), maps var→schema stem (alias map for RT/RT_TIMELINE/STATE_CHANGE/COUNTERS), skips
  ID_COLS, diffs vs schemas.py. ADR-5's literal spec couldn't be green: verified 20 tables (not >=21)
  and events/draws/passes legitimately omit 4 host-derived cols (parent_marker_path_norm /
  parent_pass_path_norm / draw_class / marker_path_norm, added in derive_post_merge). Took Option A
  (pinned-derived allowlist): equality vs schema-minus-_DERIVED_COLS + assert >=20 + allowlist sanity
  check. Appended ADR-9 (correction recorded by append; DECISIONS frozen), added the §9 dup-policy
  comment to replay_main.py (no logic change), ticked H-6 (D-2 stays partial). pytest 12 green.
- 2026-05-30 — c12 done: added bobframes/replay/__init__.py with replay_script_path() (importlib.
  resources files()+as_file context manager); run._do_replay resolves replay_main.py through it and
  no longer walks project_root (param removed; process_drop call + c03 test updated). Confirmed it
  resolves to the real on-disk path from a foreign cwd. pytest 11 green. No new ADR (mitigates the
  zipped-wheel risk in DECISIONS §15).
- 2026-05-30 — c11 done: built full cli.py argparse dispatcher over §4 verbs (ingest/render/ab/
  report/catalog/lint/check/serve/smoke/version), positional root default '.', exit map 0/1/2/3/4,
  heavy imports lazy. run.py `_log` now routes through stdlib `logging` ('bobframes' logger,
  idempotent setup_logging, --verbose→DEBUG, [HH:MM:SS] format kept; G-8). ab.py: positional root
  + hidden --root alias. reports/cli already §4-compliant (no change). Caught+fixed a cp1252
  UnicodeEncodeError from a non-ASCII (→/…) help string. Verified end-to-end render via cli (9
  pages). pytest 11 green. No ADR (follows ADR-7).
- 2026-05-30 — c03 done: ingest hardening (R-1..R-8, H-27/28, G-6/7/11). Atomic tmp+os.replace for
  manifest/parquet-pair/done.marker; qrd_harness now Popen+taskkill tree-kill on timeout; replay
  failure → `replay_failed` (no abort); RDC_ROOT save/restore; stderr always logged; KEY_VERSION=1
  byte in stable-key hash; single UTC `now_iso` (reports/cli delegates). Added test_hardening.py
  (named test_* not unit_* so default pytest collects it — no python_files override). 11 green.
  No new ADR (follows ADR-3/4/6); golden parity untouched (render path never recomputes keys/manifest).
- 2026-05-30 — c02 done: built scrubbed synthetic fixture + golden + 4 parity/schema/determinism/
  perf tests (green); fixed .gitignore to track fixtures; committed f8cf833. Found only 1 render
  nondeterminism (catalog build timestamp) — masked.
- 2026-05-30 — Verified install-ready (uv .venv py3.12, `bobframes version` works); added cli.py
  seed; recorded ADR-8 (repo data-free, tests use external capture _data); made initial git commit.
- 2026-05-30 — Copied source into bobframes/ (46 .py), swept package-name refs, all compile; c01 done.
  Stray dev prompts (CLI_PROMPT.md, reports/OVERHAUL_PROMPT.md) dropped. Noted: `_analysis_out`
  appears in stale comments/examples (real output dir is `_data`) — candidate FINDINGS cleanup.
- 2026-05-30 — Created repo scaffold at c:\Users\vsiva\dev\bobframes (dirs + root product files).
  Package named `bobframes` directly → c14 rename collapsed (ADR-7); STATE/MIGRATION/affected commit
  docs updated. Source not yet copied; git init deferred.
- 2026-05-30 — Carved CLI_PLAN.md into this doc set. Corrections from review already baked in
  (R-9 withdrawn, R-4 → process-tree kill, §21.3 drift-test rewrite, stale names fixed).
