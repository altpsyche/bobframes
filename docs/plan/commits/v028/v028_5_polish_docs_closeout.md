# v028_5 -- polish + docs + v0.2.8 close-out     release: v0.2.8 · phase: ui

> The release-ready close-out: dress the control panel in the report's own design tokens, document the
> guided mode for QA/product, bump the version + CHANGELOG. No new behavior; the golden gate is
> confirmed byte-unchanged (the panel still emits no report HTML).

## Scope
- **bobframes/ui/server.py (styling).** The control page's placeholder hex CSS is replaced with the
  shared design tokens: `control_page()` now substitutes a `/*TOKENS*/` marker with
  `chrome.design_tokens_css()` (lazy import) and every rule references the tokens
  (`--bg`/`--surface-1`/`--border`/`--text-*`/`--radius*`/`--sp-*`/`--fs-*`/`--accent-primary`/
  `--status-ok`/`--status-alarm`/`--accent-data`, `:focus-visible` rings, reduced-motion via the tokens'
  own media block). The panel uses the NEUTRAL default theme (theme=None) -- the panel chrome is not
  user-themed; the REPORT is, via `render --accent` (ADR-45). This is REUSE of the chrome seam, not a
  re-implementation (ADR-47).
- **README.md.** New "Guided mode (recommended for QA / product)" section after Install (`pipx install
  bobframes` -> `bobframes ui`, localhost + session-token note, stdlib-only) + a `ui` row in the
  Commands table.
- **CHANGELOG.md.** `## [0.2.8] - 2026-06-24` (Added: `bobframes ui`; Changed: the `serve` extraction)
  + the `[Unreleased]`/`[0.2.8]` compare link-refs. `bobframes lint CHANGELOG.md` exit 0.
- **bobframes/_version.py.** `0.2.7 -> 0.2.8` (SCHEMA_VERSION stays 3 -- no data change).

## Gates / Done when
- The panel renders with the on-brand tokens (the `/*TOKENS*/` marker is gone; the page references the
  shared `var(--*)`); `lint README.md` + `lint CHANGELOG.md` exit 0; `version` -> `bobframes 0.2.8`.
- `pytest -m "not browser"` green AND `pytest -m golden_env` byte-parity UNCHANGED with NO golden
  refresh (proves the report output is untouched by the version bump + the panel styling).

## As-built (DONE 2026-06-24)
- Styling, README, CHANGELOG, version bump landed as scoped. VERIFIED on the canonical .venv
  (py3.12.13/pyarrow21): `-m "not browser"` 398 passed / 2 deselected (unchanged from v028_4 -- the
  styling moved no test); `-m golden_env` 5 passed / 395 deselected (BYTE-PARITY UNCHANGED, no golden
  refresh -- the version bump does not appear in any rendered HTML, confirming the report path is
  untouched). `lint README.md` + `lint CHANGELOG.md` exit 0; `bobframes version` -> 0.2.8.
- CLEAN-WHEEL sanity: `uv build --wheel` -> `bobframes-0.2.8-py3-none-any.whl` bakes `_version` 0.2.8
  and ships `bobframes/ui/{server,jobs,progress,__init__}.py` + `bobframes/serve.py`
  (`packages=["bobframes"]` includes the new subpackage + module recursively -- no pyproject change).
- DEFERRED (ADR-23, recorded not hidden): (1) NO README screenshot embedded -- capturing the live panel
  needs a browser run that is not done unattended; the section documents launch in prose instead. (2) A
  BROWSER VISUAL sign-off of the tokenized panel (light/dark/print) is recommended before the PR but was
  not run this session (no GPU/browser harness on this box); the styling is token-only (no layout change)
  and the HTTP/structure tests pass, so the risk is cosmetic.
- No new dependency. No new ADR (rides ADR-47/45/23).

## v0.2.8 epic -- COMPLETE (release-ready)
v028_0 (`ui` verb + ADR-47 + skeleton) -> v028_1 (control page + /api/state + token guard) -> v028_2
(job runner + SSE + /api/ingest) -> v028_3 (render/package/open/serve) -> v028_4 (A/B + theming +
scaffold) -> v028_5 (this). The whole guided pipeline (detect -> ingest -> render/package/open/serve ->
A/B + accent + scaffold) drives from a zero-dependency browser panel; the golden gate is untouched
throughout.

## Next (gated on user authorization -- NOT in the green gate)
Open the v0.2.8 PR from `feat/v028-ui-control-panel`; on approval, tag `v0.2.8` -> the ci.yml publish
job (Trusted Publishing/OIDC, ADR-13) ships PyPI + a GitHub Release; verify a clean-venv
`uv pip install bobframes==0.2.8` -> `bobframes 0.2.8`. CARRY-OVER: R-19 (overdraw tie nondeterminism,
own commit).
