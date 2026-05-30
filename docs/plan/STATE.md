# BobFrames — implementation state

> The resumption anchor. A fresh session reads this first, then opens the `current` commit doc.
> Update the three live fields (`current`, `last_session`, `next_action`) and the checklists before
> you stop. This file is the single source of truth for progress — commit docs mirror status but
> defer to this.

```
active_release: v0.1
current:        c11_cli_dispatcher     (status: not-started)
last_session:   2026-05-30 — c03 DONE: ingest-path hardening — atomic writes (R-1/2/3),
                process-tree kill on replay timeout (R-4), RDC_ROOT save/restore (R-5),
                replay-skip→`replay_failed` (R-6), stderr logging (R-7/8), KEY_VERSION=1 (H-27),
                single UTC now_iso (H-28), manifest tool_versions+host_info (G-6/7). New
                test_hardening.py (7 mocked-subprocess tests). pytest: 11 green (4.85s).
next_action:    c11 — cli.py dispatcher. Open commits/v01/c11_cli_dispatcher.md and do exactly
                that commit. Run pytest after (keep 4 parity-suite + hardening tests green).
blockers:       none. (Run tests via: .venv\Scripts\python -m pytest bobframes/tests)
```

## v0.1 — extraction (ships first)

| | Commit | Status |
|---|---|---|
| ☑ | [c01 version](commits/v01/c01_version.md) | **done** — `import bobframes` → 0.1.0 |
| ☑ | [c02 golden harness + parity](commits/v01/c02_golden_harness.md) | **done** — 4 tests green (parity/schema/determinism/perf), commit f8cf833 |
| ☑ | [c03 reliability hardening](commits/v01/c03_hardening.md) | **done** — atomic writes, tree-kill, replay-skip, KEY_VERSION=1, provenance; 11 tests green |
| ☐ | [c11 cli.py dispatcher](commits/v01/c11_cli_dispatcher.md) | not-started ← **HERE** |
| ☐ | [c12 replay importlib.resources](commits/v01/c12_replay_importlib.md) | not-started |
| ☐ | [c13 replay-drift CI guardrail](commits/v01/c13_replay_drift_ci.md) | not-started |
| ✗ | [c14 rename](commits/v01/c14_rename.md) | **COLLAPSED** — package is `bobframes` from scaffold (ADR-7) |
| ☐ | [c15 smoke rewrite + unit tests](commits/v01/c15_smoke_tests.md) | not-started |
| ☐ | [c17 CI workflow](commits/v01/c17_ci_workflow.md) | not-started |
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
