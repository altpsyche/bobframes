# v028_8 -- externalize panel JS/CSS to served static assets     release: v0.2.8 · phase: ui

> The highest-leverage structural fix from the review: move the inline `<script>`/`<style>` out of a
> Python string into real files served as static assets. This makes the client a file that
> `node --check`/lint validate directly (under the v028_7 gate) and makes the v028_2 bug class -- a
> Python-string escape splitting a JS literal -- **structurally impossible**. Still zero deps; still no
> report HTML (golden gate / ADR-37 untouched). Last pre-ship commit before the v0.2.8 release.

## Why this commit exists
v028_2..6 carried the whole panel client inside `server._CONTROL_PAGE`, a Python string. That is exactly
how the v028_2 bug happened (a normal triple-quoted string turned `"\n"` into a real newline mid-JS-
literal). v028_7 added a `node --check` gate, but the JS still lived in a string the gate had to *extract*
from. Externalizing to real files removes the embedding entirely: there is no Python string for an escape
to corrupt, and the gate + lint run on the file as-shipped.

## Scope
- **`bobframes/ui/assets/panel.js`** -- the client JS, verbatim from the old `<script>`. Served at
  `GET /panel.js`.
- **`bobframes/ui/assets/panel.css`** -- the panel's static CSS rules, verbatim from the old `<style>`
  (everything except the `/*TOKENS*/` marker). Served at `GET /panel.css`.
- **`server.py`** -- `control_page()` now builds a JS-free HTML **shell** (`_SHELL`, a plain string: HTML
  + a tiny inline `<style>` carrying `chrome.design_tokens_css()` -- the only dynamic, theme-derived CSS
  -- + `<link rel="stylesheet" href="/panel.css">` + `<script src="/panel.js"></script>`). New
  `panel_js()` / `panel_css()` read the assets via `importlib.resources` (the report-chrome convention),
  and `do_GET` serves `/panel.js` (`text/javascript`) and `/panel.css` (`text/css`) **without** a token
  (they hold no secret and carry no state; the session token stays in the page URL, and panel.js reads it
  from `location.search` as before). The design tokens stay server-rendered inline so the report-token
  reuse (ADR-45/ADR-47) is unchanged; panel.css references the token vars.
- **Tests** -- `test_ui_js_parses` now `node --check`s the real `bobframes/ui/assets/panel.js`;
  `test_ui_smoke` asserts the shell links `/panel.js` + `/panel.css`, the assets serve without a token
  with correct content-types, and (node-absent fallback) the page embeds no inline `<script>` while
  panel.js preserves the exact `"\n"` literal v028_2 broke. **ci.yml** simplifies to
  `node --check bobframes/ui/assets/panel.js`. **CHANGELOG** [0.2.8]: a Changed line (assets externalized)
  + a Tests/CI line (the JS-execution guard).
- **Packaging** -- no `pyproject` change: `packages=["bobframes"]` ships `bobframes/ui/assets/*`
  recursively (ADR-10, the same mechanism that ships `design_tokens.toml` + the woff2 fonts).

## Gates / Done when
- `GET /panel.js` + `GET /panel.css` return `200` with correct content-types; the page renders
  identically (token-styled, same sections/ids).
- `node --check bobframes/ui/assets/panel.js` green; the v028_7 `browser` populate-smoke still green.
- `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged, NO golden refresh.
- `uv build --wheel` then unzip confirms `bobframes/ui/assets/panel.{js,css}` are in the wheel.
- No new runtime dependency.

## As-built (DONE 2026-06-24)
- **`bobframes/ui/assets/panel.{js,css}`** created (JS + static CSS lifted verbatim from the old inline
  blocks). **`server.py`**: `_SHELL` (HTML-only, plain string) + inline `<style>` token injection +
  `<link>`/`<script src>`; `_asset()`/`panel_js()`/`panel_css()` via `importlib.resources`; `do_GET`
  serves `/panel.js` (`text/javascript`) + `/panel.css` (`text/css`) untokened.
- VERIFIED: `node --check bobframes/ui/assets/panel.js` clean; served page links both assets, embeds no
  inline `<script>`, tokens still inline; `/panel.js` + `/panel.css` -> 200 with right content-types;
  `-m browser` populate-smoke green (live panel loads the externalized assets over http and still fills
  `#root`/`#tools`/`#drops`); `-m "not browser"` **403 passed / 3 deselected** (was 402 at v028_7; +1 =
  the extra test_ui_smoke asset test); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**.
- **Wheel:** `bobframes-0.2.8-py3-none-any.whl` ships `bobframes/ui/assets/panel.css` + `panel.js`
  (`packages=["bobframes"]` recursive -- NO pyproject change, per ADR-10). No new dependency.
- v028_2 bug class now **structurally impossible** -- no JS is embedded in any Python string.
- No new ADR (rides ADR-47/45/23). **v0.2.8 pre-ship hardening complete** (v028_7 gate + v028_8
  externalize); next is the v0.2.8 release sequence (GATED on user authorization).
