# BobFrames — implementation state

> The resumption anchor. A fresh session reads this first, then opens the `current` commit doc.
> Update the three live fields (`current`, `last_session`, `next_action`) and the checklists before
> you stop. This file is the single source of truth for progress — commit docs mirror status but
> defer to this.

```
active_release: v0.1
current:        c17_ci_workflow    (status: not-started)
last_session:   2026-05-31 — c15 DONE: rewrote tests/smoke.py (G-12) — killed the hardcoded
                Chor-bazar/r110565/2026-05-27 constants + __file__-walked root. New shape: no --data
                = render-only vs bundled synthetic (CI-safe); --data DIR = full ingest via
                find_drops. Wired --data+pixel_grid through cli._cmd_smoke. Added 3 unit files
                (test_stable_keys / test_schemas_unit / test_discovery — named test_* not unit_*).
                pytest 32 green; `bobframes smoke` exit 0. Full --data path needs GPU (nightly).
next_action:    c17 — CI workflow. Open commits/v01/c17_ci_workflow.md and do exactly that commit
                (.github/workflows/ci.yml; matrix per QUALITY_GATES §21.6). Keep the 32-test suite
                green; CI step list must match the test_* filenames actually on disk (NOT unit_*).
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
| ☐ | [c17 CI workflow](commits/v01/c17_ci_workflow.md) | not-started ← **HERE** |
| ☐ | [c18 README + CHANGELOG + LICENSE](commits/v01/c18_docs.md) | not-started |
| ☐ | [c19 tag v0.1.0](commits/v01/c19_release.md) | not-started |

## v0.2 — de-hardcoding (deferred)

| | Commit | Status |
|---|---|---|
| ☐ | [c04 paths.py constants](commits/v02/c04_paths_constants.md) | deferred |
| ☐ | [c05 registry from `schemas.TABLES`](commits/v02/c05_registry_consolidation.md) | deferred |
| ☐ | [c06 tool resolver + glob version detect](commits/v02/c06_tool_resolver.md) | deferred |
| ☐ | [c07 TOML config layer](commits/v02/c07_toml_config.md) | deferred |
| ☐ | [c08 design tokens TOML + preview](commits/v02/c08_design_tokens.md) | deferred |
| ☐ | [c09 engine-agnostic classifier](commits/v02/c09_classifier.md) | deferred |
| ☐ | [c10 env-var rename `RDC_*`→`BOBFRAMES_*`](commits/v02/c10_env_rename.md) | deferred |
| ☐ | [c16 report-quality polish](commits/v02/c16_report_quality.md) | deferred |

## Status legend
`not-started` → `doing` → `done`. Use `blocked: <reason>` when stuck and record it under `blockers`.

## Session log (append newest on top; one line each)
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
