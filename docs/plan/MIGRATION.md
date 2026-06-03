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
| [c16b report charts](commits/v02/c16b_report_viz.md) | inline-SVG chart toolkit + flagship chart per report; shader column-diet (ADR-33, G-15 charts half) |
| [c16c report restructure](commits/v02/c16c_report_restructure.md) | section-cards + sticky-h2 + copy-buttons + dashboard small-multiples + caption/scope a11y + fill-or-hide (G-15 done) |
| [c16d report aesthetics](commits/v02/c16d_report_aesthetics.md) | visual-design pass: depth-over-borders + type hierarchy + chart finish + micro-interactions + pacing (G-17) |
| [c16e run model](commits/v02/c16e_run_model.md) | per-run truth: report ONE current run (default newest), not the cumulative union of all runs (G-19, ADR-35) |
| [c16f multi-run UX](commits/v02/c16f_multirun_ux.md) | run selector (pre-rendered per-run pages) + baseline banner + "older run" cue + dashboard->report persistence (G-18) |
| c16g quality sweep | Q-1/Q-2/Q-4/Q-7/Q-8 + D-3/D-9: stable-key dict-loop, cast-failure tally, zip strict, `_to_dict_of_lists` reuse, dead-noop, coupling/display-order docs |
| c16h reliability sweep | R-11/R-12/R-14/R-15: log cleanup failures, UTF-8 warn, single-process sidecar doc, parquetize skips markerless captures (R-10 deferred) |
| [c16i catalog + drill readability](commits/v02/c16i_catalog_drill_readability.md) | **(revived, ADR-37)** STATIC `html/template.py` pass: Inter/mono type split, roomier VTable rows, client-side heatmap cells, collapsible column groups (G-21) |
| [c16j decouple heavy data](commits/v02/c16j_data_decoupling.md) | **(repurposed, ADR-37)** move catalog/drill VTable rows to `<script src>`'d `_data/*.js` (static, file://-safe, defer); kills the ~21MB drill TTI |
| ~~ADR-36 SPA epic (c16k–c16n)~~ | **SUPERSEDED by ADR-37** — bespoke offline SPA rejected on a lifespan review (web-framework tax, weakens golden-as-correctness, loses JS-optional, hurts plugins/cross-platform). Reports stay static; only heavy data decoupled (c16j); durable data contract = c20/c30. Trail in DECISIONS ADR-36/37 + the [proposal](adr36_spa_architecture_proposal.md) |

## v0.2.5 — report packaging + exec one-pager (after v0.2, before v0.3)

A focused minor: make the reports shareable and give execs/non-technical readers a one-pager. Compositions
of existing primitives; the default `render` output stays byte-identical (ADR-37 holds). No schema bump.
See [v025_packaging_and_onepager_proposal.md](v025_packaging_and_onepager_proposal.md) + ADR-39/40/41/42.
Continues the c16 report-epic letter lineage (c17-c19 are shipped v0.1; no free integers before c20).
Order = q,r,s,t,u,v,x then the **w close-out LAST** (the letter is just a label; c16x was added after the
spine - ADR-42 - so c16w stays the final commit).

| Commit | Leaves working state of… |
|---|---|
| [c16q health + one-pager](commits/v025/c16q_health_and_onepager.md) | `bobframes/health.py` (verdict + UNKNOWN, presentation-independent) + `reports/summary.py` print-first one-pager + discoverability nav (ADR-39, G-24) |
| [c16r head_assets seam](commits/v025/c16r_head_assets_seam.md) | `head_assets(sink)` one-source-of-truth seam in chrome + template; render BYTE-UNCHANGED (zero-output refactor) |
| [c16s package verb](commits/v025/c16s_package_verb.md) | `bobframes package` -> a shareable `.zip` (stream-from-source, output outside tree) + a standalone single-file `summary.html` + a root README + run-derived naming + a `--light` preset; the output-verb taxonomy (ADR-40) |
| [c16t shared-assets default](commits/v025/c16t_shared_assets.md) | shared-assets becomes the DEFAULT bundle delivery via the seam (`--inline` opts out); per-family `_assets/` + depth-relative links; revisits ADR-37 (ADR-41) |
| [c16u redact](commits/v025/c16u_redact.md) | `--redact` at the provenance data seam, strip-by-default; abs-path completeness scan |
| [c16v multi-capture normalize](commits/v025/c16v_multicapture_normalize.md) | per-frame normalization of instancing repeat-count + shader cost across the reports + dashboard + verdict (G-29); golden-neutral on 1-capture data |
| [c16x component system](commits/v025/c16x_component_system.md) | server-side `chrome` components (`kpi_card`/`trendline`/`status_badge`) + ONE owned stylesheet + a token-validity guard + preview-gallery catalog; migrates the c16q one-pager off its inline `<style>` (ADR-42, G-30). Stop brute-forcing per-page CSS |
| [c16w close-out](commits/v025/c16w_v025_closeout.md) | v0.2.5 close-out: 0.2.0 -> 0.2.5, CHANGELOG, full re-ingest verify, tag v0.2.5 -> PyPI |

## v0.3 — CI/automation surface (after v0.2.5)

The high-leverage audience step. `--json` first (additive; no HTML-golden impact). See
[ROADMAP.md](ROADMAP.md). Each guarded by parity. **c20/c21 CONSUME `bobframes/health.verdict()` (built at
c16q) — `--json` emits the `Verdict`, `report --gate` maps its `State` to an exit code — they do NOT
re-implement it (G-25).**

| Commit | Leaves working state of… |
|---|---|
| [c20 --json output](commits/v03/c20_json_output.md) | global `--json` + `jsonout.JSON_SCHEMA_VERSION=1`; stdout=JSON, stderr=logs (G-9, ADR-16) |
| [c21 regression gating](commits/v03/c21_regression_gating.md) | `trend_table.KPIS` thresholds → c07 config; `report trend --gate` exit code |
| [c22 isolated stages](commits/v03/c22_isolated_stages.md) | standalone `parse`/`replay` verbs over the stage tree (G-10) |
| [c23 --dry-run](commits/v03/c23_dry_run.md) | `ingest --dry-run` prints the plan, zero side effects (G-1) |
| [c24 verify](commits/v03/c24_verify.md) | `verify` integrity check (schema/cols/cache-SHA/counts), exit 1 on mismatch (G-4) |
| [c25 diff](commits/v03/c25_diff.md) | `diff` drop/manifest deltas, text + JSON (G-2) |
| [c26 export](commits/v03/c26_export.md) | `export` tables to csv/json/zip from committed `_data/` (G-5) |

## v0.4 — Engine breadth + ergonomics (after v0.3)

UE + generic engines; the artist reports; schema/query. New reports add goldens; no schema bump.

| Commit | Leaves working state of… |
|---|---|
| [c27 engine presets](commits/v04/c27_engine_presets.md) | generic preset + per-engine fixture/golden harness; Unity/Godot stubs (ADR-21/22) |
| [c28 texture_usage report](commits/v04/c28_texture_usage_report.md) | the already-derived `texture_usage` surfaced as a report (G-13) |
| [c29 overdraw heatmap](commits/v04/c29_overdraw_heatmap.md) | per-RT overdraw heatmap on the overdraw report |
| [c30 schema + query](commits/v04/c30_query_schema.md) | `schema` introspection (core) + `query` via `bobframes[query]` extra (ADR-17) |
| [c31 mesh/material report](commits/v04/c31_mesh_material_report.md) | per-material draw/vertex/instance report |

## v0.5 — Graphics-API adapter epic (after v0.4)

GL adapter = today (parity-clean) → data-driven columns → Vulkan + fixture/golden → **`SCHEMA_VERSION`
3→4** at c35 (golden refresh + bobframes MINOR). Unified core + per-API extension tables (ADR-14);
Vulkan first (ADR-15).

| Commit | Leaves working state of… |
|---|---|
| [c32 PipelineStateAdapter](commits/v05/c32_pipeline_state_adapter.md) | GL extraction behind `PipelineStateAdapter` + `ctrl.API()` dispatch; **no output change** |
| [c33 data-driven columns](commits/v05/c33_data_driven_columns.md) | class columns generated from `class_order`; `api` tag on `schemas.TABLES`; GL byte-identical |
| [c34 Vulkan extraction](commits/v05/c34_vulkan_extraction.md) | `VulkanAdapter` + Vulkan fixture + golden; GL untouched |
| [c35 schema widening](commits/v05/c35_schema_widening.md) | Vulkan extension tables registered; `SCHEMA_VERSION` 3→4; **both goldens refreshed** |

## v0.6+ — Cross-platform + leads + plugins (after v0.5)

Linux/macOS locator + non-Windows tree-kill; historical dashboard + alerts; trusted-local plugins;
optional Figma sync.

| Commit | Leaves working state of… |
|---|---|
| [c36 cross-platform](commits/v06/c36_cross_platform.md) | per-OS tool locator (extends c06) + platform-dispatched tree-kill; Linux/macOS `check` (H-38, ADR-18) |
| [c37 historical dashboard](commits/v06/c37_historical_dashboard.md) | multi-drop historical dashboard + config-driven regression alerts |
| [c38 plugins](commits/v06/c38_plugins.md) | trusted-local auto-discovery of reports/derives/presets/adapters; schema-table registration (M-1/M-2, ADR-19) |
| [c39 Figma sync](commits/v06/c39_figma_sync.md) | optional `export-tokens --format figma` / sync behind a `[figma]` extra |

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
