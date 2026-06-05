# v0.2.6-1c -- user theme override (`[theme]` + `--accent`)     release: v0.2.6 · phase: redesign

> The pip-user accent fix. The chrome is NEUTRAL by default (1a, ADR-44). A `pip install bobframes` user
> cannot cleanly edit the packaged `design_tokens.toml` (it lives in site-packages, lost on upgrade) and
> tokens are substituted into a chrome **module constant at import time**, so a value can't be patched at
> render. This commit lets users re-hue the accent/status/draw-class COLORS via a `.bobframes.toml`
> `[theme]` section (durable) or `--accent`/`--accent-data` CLI flags (one-shot), reusing the existing
> ADR-25 config cascade -- **no source edit, no new mechanism**. Plan:
> `~/.claude/plans/bobframes-v0-2-6-visual-enumerated-bachman.md` ("User theme override"). ADR-45.

## Goal
A user-overridable accent that rides the existing config cascade (CLI > env > config > default) and the
existing render-threading seam, such that the **`theme=None` default render is byte-identical** (goldens
green, NO refresh) and an override re-hues only the color tokens (never layout/density/parity machinery).

## The seam (verified against current code)
Only `chrome._DESIGN_TOKENS` (the `:root` var block) is theme-dependent: `_tokens.token_subst()` flattens
`_SUBST_SECTIONS=('spacing','type','radius','motion','color','shadow')`, and every other CSS asset
(`_CHROME_CSS`/`_STICKY_CSS`/components/rdc-table/print) is pure `var(--...)` refs substituted from
`layout_subst()` (no color). So an override re-runs **only** the tokens-block substitution:
`string.Template(_DESIGN_TOKENS_TMPL).substitute(token_subst() | theme)`.

## Scope
- **config.py** -- NEW frozen `ThemeCfg` (a `tokens: Mapping[str,str]` of allowlisted color overrides) +
  a `theme: ThemeCfg | None` field on `Config` (line ~148). Parse a `[theme]` table in `_build_config`
  (line ~201), filtering against the **color-hue allowlist** (warn + ignore any key outside it; mirrors the
  `[classifier].custom_path` user-overrides-a-bundled-preset precedent). Deep-merge via the existing
  `_deep_merge` (ADR-25). Allowlist (15 keys, color hues ONLY -- the neutral chrome surfaces/text/border
  stay bundled): `accent_primary`, `accent_data`, `status_{alarm,warn,ok,info}`,
  `c_{opaque,prepass,translucent,additive,decal,shadow,ui,postprocess,other}`.
- **Value validation** -- each override value is ASCII (reuse the `test_design_tokens` discipline) and free
  of `;{}` (CSS-injection guard; real token values use only `oklch()`/`light-dark()`/`,`/`%`/spaces). A bad
  value warns + is dropped (non-fatal in the designer loop; hard CI assert in `test_theme`).
- **reports/chrome.py** -- NEW public `compose_css(theme: dict | None = None) -> str`: `theme is None`
  returns the existing cached `_compose_css()` constant **byte-for-byte**; non-`None` recomputes the tokens
  block with `token_subst() | theme` and minifies `that + _PRIMITIVES_CSS + _COMPONENTS_CSS + _RDC_TABLE_CSS`.
  `head_assets(sink, depth, theme=None)` and `design_tokens_css(theme=None)` gain the same optional param
  (INLINE embeds `compose_css(theme)`; the UN-minified `:root` path re-substitutes the template). chrome does
  NOT import config (lower layer) -- it takes a plain dict.
- **Thread `theme` (a 4th optional param on the established sink/build_ts/redact seam):**
  `orchestrator.render_all_reports(..., theme=None)` -> each `mod.build(..., theme=theme)` ->
  `base.report_page(..., theme=theme)` -> `page_open(..., theme=theme)` -> `head_assets(..., theme=theme)`;
  `ab.render_pair(..., theme=theme)`; `html/template.render_root(..., theme=theme)` + the drill/per-drop
  compose path; `preview.build(theme=None)` + the `report` verb take `theme` directly. All DEFAULTED to
  None so the default render is unchanged.
- **run.py / orchestrator** -- read `config.get_config().theme` (its `.tokens` dict, or None) once and pass
  it in. CLI `--accent`/`--accent-data` override on top (CLI > config) before threading.
- **cli.py** -- `--accent <oklch>` / `--accent-data <oklch>` on `render` + `preview` (map to
  `accent_primary` / `accent_data`); `export-tokens --theme-template` emits a ready-to-paste `[theme]`
  starter block (the overridable knobs only, with the current default values as comments); `--watch` ALSO
  polls `.bobframes.toml` (it already polls `design_tokens.toml`). `package` **rejects** `--accent`/
  `--accent-data` exactly as it rejects `--format` (ADR-40 presentation-verb invariant; it bundles whatever
  the render produced).
- **Guard** -- the composed-with-override bundle runs through `chrome._undefined_token_refs` at render:
  non-fatal **warn** in `render`/`preview` (designer loop, matching c16x-3 `preview` warn), hard assert in
  `test_theme` on a planted bad override.

## Gates
- **(a) Data path FROZEN + default render byte-identical.** `test_parquet_parity` + `test_parity` +
  `test_preview_matches_golden` + the package goldens GREEN with **NO refresh** (the `theme=None` path is
  byte-identical; verify via `git status` -- ZERO golden/`_pagedata`/`digests`/`parquet` drift this commit).
- **(b) NEW `tests/test_theme.py`** -- override merges into the `:root` (a `[theme]` accent re-hues
  `--accent-primary`); the allowlist rejects a non-color key (e.g. `radius`/`sp_4`) with a warn; a bad value
  (`;{}` / non-ASCII) is dropped + the guard catches a planted undefined-ref override; CLI `--accent` >
  config `[theme]` > bundled default precedence; `package` rejects the flags; ASCII discipline on the
  template emitted by `--theme-template`.
- **(c) `test_config` extended** for the `[theme]` parse + `ThemeCfg` deep-merge.
- **(d) Browser matrix (manual)** -- a `.bobframes.toml` with a blue `[theme]` accent -> `render` ->
  light/dark show the re-hued accent on links/interactive/focus + the data-accent on charts/heatmap;
  `render --accent '<oklch>'` overrides the config. Eyeball, no golden bake (override renders aren't goldens).
- **(e) Lint/ASCII/determinism**; no new dep/build step (ADR-37 holds).

## Done when
A `[theme]` accent in `.bobframes.toml` (and `--accent` on the CLI) re-hues the reports end-to-end; the
default `theme=None` render is byte-identical (every golden green, NO refresh, ZERO drift); the allowlist +
value validation + guard reject bad overrides; `package` rejects the flags; `test_theme.py` + extended
`test_config` green; full suite green; ADR-45 appended; DESIGNER.md documents the override path.

## As-built (DONE 2026-06-05)
- **config.py** — `THEME_KEYS` (15-key color-hue allowlist), `_valid_theme_value` (ASCII + no `;{}`),
  `clean_theme_overrides` (warn + drop a non-color key OR a bad value; order-stable), frozen `ThemeCfg`
  (`tokens` tuple + `as_dict()`), `Config.theme` field parsed in `_build_config`, and `theme_for_render`
  (config `[theme]` + CLI `--accent`/`--accent-data` overlay, re-cleaned; None when nothing to override).
- **chrome.py** — `_tokens_css_for(theme)` + public `compose_css(theme=None)` (`theme` falsy returns
  `_compose_css()` byte-for-byte; else re-substitutes the tokens template with `token_subst() | theme`),
  `design_tokens_css(theme=None)`, `head_assets(sink, depth, theme=None)`, `page_open(..., theme=None)`,
  `report_page(..., theme=None)`, and `theme_undefined_tokens(theme)` (the render-time guard). Re-exported
  via `base` (`compose_css`, `theme_undefined_tokens`).
- **Threading** (4th optional param mirroring `sink`/`build_ts`/`redact`): `orchestrator.render_all_reports`
  -> the 8 builders (`build` sig + their `report_page` call) -> `report_page` -> `page_open` ->
  `head_assets`; `ab.render_pair`; `html/template.render_root` + `render_drop` (+ a `_css_for(theme)` for
  the catalog/drill family); `preview.build`; `run.process_drop`. All default None -> default render
  byte-identical.
- **run.py / cli.py** — `--accent`/`--accent-data` on `render` (run engine + cli forward, incl. into the
  `--watch` subprocess) and `preview`; `run.main` builds the effective theme via `config.theme_for_render`
  and threads it; `export-tokens --theme-template` prints a paste-ready `[theme]` block (color knobs +
  commented current defaults, ASCII); `_watch_paths` now also polls `<root>/.bobframes.toml`; `package`
  has no `--accent` (argparse rejects it) — a NOTE records the ADR-40/45 invariant.
- **package.py** — a shared/redacted bundle reads the packaged root's `[theme]` and re-renders themed
  `_assets/` (`compose_css(theme)` / `template._css_for(theme)`); `theme=None` is byte-identical to the
  c16t/c16u shared golden.
- **Guard** — `theme_undefined_tokens` runs at render: non-fatal **warn** in `orchestrator`/`preview`
  (the designer loop), a hard assert in `test_theme` on a planted `var(--bogus)` override.
- **Gate** — `test_parquet_parity` + `test_parity` + `test_preview_matches_golden` + the package goldens
  all GREEN with **NO refresh** (the `theme=None` path is byte-identical; the suite passed against the 1b
  goldens with no re-bake -> 0 golden/`_pagedata`/`digests`/`parquet` drift from 1c). NEW `tests/test_theme.py`
  (8) + `test_config` `[theme]` (5): 327 -> 340 green. ADR-45 (authored at plan time, accurate to the
  as-built); DESIGNER.md "Theme override" section. Browser-eyeballed a blue `--accent` (synthetic, light +
  dark): links / headings / data-bars / heatmap / summary-rail re-hue; KPI numerals + the draw-class donut
  palette stay (only the two accents were set). smoke render-only 17 pages lint-clean; ASCII discipline holds.

## Next
v0.2.6-2 (summary one-pager: restrained type + hero numerals, summary-scoped).
