# Hardcode / inflexibility catalog (burndown)

> Carved from CLI_PLAN §20. IDs `H-*` owned here. Priority: **P0** limits adoption beyond the current
> project (engine/vendor/schema); **P1** friction (version locks, dual-edit lists); **P2** cosmetic.
> Per [ADR-1](../DECISIONS.md), de-hardcoding is **v0.2** — only `H-27`/`H-28` land in v0.1/c03.
> Symbol-anchored (no line numbers).

## P0 — engine / vendor lock-in

| ID | Where | Hardcoded | Remediation | resolved-by | status |
|---|---|---|---|---|---|
| H-1 | `derive_post_merge._classify_draw` | UE keyword switch (basepass/shadow/prepass/…) | externalize to `derives/draw_classifier.toml`; 10-line walker; ship UE preset | [c09](../commits/v02/c09_classifier.md) | ☐ |
| H-2 | `formatters.pass_short` | UE marker strips (`FRDGBuilder::Execute`, `MobileSceneRender`, `/Engine/EngineMaterials`) | `[pass_strip]` in same TOML | c09 | ☐ |
| H-3 | `derive_post_merge._RE_FRAME_PREFIX` | UE `^Frame\s+\d+/?` | `frame_prefix_regex` in TOML | c09 | ☐ |
| H-4 | `derives/pass_class_breakdown` | counter literal `'GPU Duration'` (Arm-specific) | `[counters] gpu_duration_aliases` fall-through | c09 | ☐ |
| H-5 | `chrome.DRAW_CLASSES` + `_classify_draw` | DRAW_CLASSES enum duplicated in two places | single source: classifier `class_order`; chrome iterates it | c09 | ☐ |
| H-6 | `replay/replay_main` `*_COLS` tuples | schema cols duplicated from `schemas.py` (qrenderdoc import unreliable) | **kept by design**; CI drift detector | [c13](../commits/v01/c13_replay_drift_ci.md) | ☐ |

## P1 — tool version lock + dual-edit lists

| ID | Where | Hardcoded | Remediation | resolved-by | status |
|---|---|---|---|---|---|
| H-7 | `qrd_harness`, `rdcmd` | Arm `2026.2` path baked (breaks quarterly) | glob `Arm Performance Studio */…`, pick latest; `resolve_tool()` | [c06](../commits/v02/c06_tool_resolver.md) (ADR-2: pull-forward candidate) | ☐ |
| H-8 | `orchestrator._REPORT_MODULES` + `ab._MODULES` | 6-report list duplicated (two names) | `reports/__init__.ALL_REPORTS` | [c05](../commits/v02/c05_registry_consolidation.md) | ☐ |
| H-9 | `global_entities._ENTITY_TABLES` | 7 entity tables literal | derive from `schemas.TABLES` via `is_entity_table()` | c05 | ☐ |
| H-10 | `catalog._CATALOG_TABLE_KEYS` | 29 table names | `tuple(schemas.TABLES.keys())` | c05 | ☐ |
| H-11 | `html/template._CATEGORY_MAP` | table groupings | move `category` field into `schemas.TABLES` | c05 | ☐ |
| H-12 | `qrd_harness` timeout `600.0` | replay timeout not tunable | `[pipeline] replay_timeout_s` + `--replay-timeout` | [c07](../commits/v02/c07_toml_config.md) | ☐ |
| H-13 | `rdcmd` timeout `120.0` | convert timeout not tunable | `[pipeline] convert_timeout_s` + flag | c07 | ☐ |
| H-14 | `lint.BANNED` | inline banlist | `lint_banlist.toml` + `[lint] extra_banned` | c07 | ☐ |
| H-15 | `chrome` design tokens | tokens as inline Python string | `design_tokens.toml` | [c08](../commits/v02/c08_design_tokens.md) | ☐ |
| H-16 | `formatters._BANNED_CHROME_CHARS` | inline regex | move to lint/token TOML | c08 | ☐ |
| H-17 | `derive_post_merge` complexity weights | inline literals | `[scoring.complexity]` in config | c07 | ☐ |
| H-18 | `paths` dir literals (`_data`,`_reports`,`_cache`,`_stage`,`_tmp`,`drill`,`ab`) | scattered | module constants in `paths.py` | [c04](../commits/v02/c04_paths_constants.md) | ☐ |
| H-19 | `manifest`/`catalog`/`pipeline` literals (`_manifest.json`,`done.marker`) | scattered | `paths.py` constants | c04 | ☐ |
| H-20 | `chrome` + `delta` layout literals (bar heights, grid widths, sparkline `60x14`) | inline | `[layout]` in design_tokens.toml | c08 | ☐ |
| H-21 | `delta` `pct >= 8.0` bar-label threshold | inline | `[layout] bar_label_min_pct` | c07 | ☐ |
| H-22 | `delta` `fmt='{:+,.0f}'` | inline default | config default + per-call override | c07 | ☐ |
| H-23 | `formatters` `n=12`, `max_len=60` | rigid defaults | `[formatting] id_short_n`, `text_trunc_max` | c07 | ☐ |

## P1 — wire protocol / stable-key / manifest

| ID | Where | Note | resolved-by | status |
|---|---|---|---|---|
| H-24 | `qrd_harness`/`replay_main` `_SEP='\x1f'` | wire protocol; both ends must agree | **stays by design** | — |
| H-25 | `rdcmd` `renderdoccmd convert -f … -c <fmt>` | RenderDoc CLI contract | **stays by design** | — |
| H-26 | `qrd_harness` `qrenderdoc --python <path>` | RenderDoc-defined | **stays by design** | — |
| H-27 | `stable_keys._sha` | SHA256 no version prefix; rule change orphans keys (G-11) | add `KEY_VERSION=1`, prepend version byte | [c03](../commits/v01/c03_hardening.md) | ☐ |
| H-28 | `manifest`/`cli` timestamps | UTC vs local mixed | single `now_iso()` UTC helper | [c03](../commits/v01/c03_hardening.md) | ☐ |
| H-29 | `schemas.ID_COLS` | `(area, drop_date, drop_label, capture)` layout assumption | **frozen v1 contract**; v2 may relax | v2.0 |
| H-30 | `discovery.DATED_RE` | `YYYY-MM-DD[_label]` locked | `[discovery] drop_folder_regex` | [c07](../commits/v02/c07_toml_config.md) | ☐ |
| H-31 | English UI strings everywhere | i18n impossible | out of scope v1; roadmap only | — |

## P2 — cosmetic (leave as-is)

`H-32` rotation suffix fmt · `H-33` `_log()` `%H:%M:%S` · `H-34` reduced-motion media query
(accessibility-correct) · `H-35` `_CATEGORY_ORDER`/`_DEFAULT_OPEN` display prefs. All fine; no action.

## Stays hardcoded by design (summary)
H-6 (replay dup, guarded by c13) · H-24/25/26 (wire + RenderDoc CLI contracts) · H-29 (schema v3
contract) · H-18/19 *values* (`_data` etc. stay; only the literals get centralized). See
[ADR-2](../DECISIONS.md) for the v0.1 Arm-path decision (H-7).
