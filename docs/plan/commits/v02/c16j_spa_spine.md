# c16j — SPA spine: app shell + asset bundle + golden restructure (ADR-36, phase 1)     release: v0.2

## Goal
Stand up the offline static-SPA skeleton from **[ADR-36](../../adr36_spa_architecture_proposal.md)** and
prove the contract end-to-end on **one** view (the catalog), before re-homing everything else. After
this commit the output is an **app folder** that opens by double-click (`file://`, no server), is
byte-deterministic, and is gated by a restructured golden.

## Depends on
ADR-36 (the architecture + the offline `<script src>` unlock). The existing renderers
(`reports/chrome.py` design system + web components, `html/template.py` catalog/VTable) — **reused**,
emitted as a shell + fragment instead of whole pages.

## Scope
1. **Shell `index.html`** (tiny, static): `<head>` `<link rel=stylesheet href="_assets/app.css">`, a
   `<main id="app">` mount, `<noscript>` linking the single-file export (added c16m), and
   `<script src="_assets/app.js">`. Deterministic text.
2. **`_assets/app.css`**: the WHOLE design system in one file — `design_tokens_css()` `:root` +
   `chrome_css()` + the base64-inlined Inter subset (relocated here from per-page, ADR-34/36), loaded
   ONCE. Built from the existing token skeleton (ADR-27); no new raw literals.
3. **`_assets/app.js`**: the existing web components (`components_js`: copy/search/sticky/ab-picker/
   VTable) + a **minimal hash router** (`#/catalog` for now) that, on a route, injects the route's
   `_views/<route>.html` fragment into `#app` and (for data views) injects `<script src="_data/<key>.js">`
   once, then mounts. Static, deterministic JS (no `random`/`Date`).
4. **Migrate ONE view — the catalog** — as proof: emit `_views/catalog.html` (the VTable shell, server-
   rendered by the existing `template.py` catalog renderer, **rows not baked in**) + `_data/catalog.js`
   (`window.__bf_data['catalog']={...}`). The router loads both on `#/catalog`. (Drill + reports come in
   c16k/c16l.)
5. **Golden restructure**: extend the parity harness to gate the **app-folder file-set + each file's
   bytes** — `index.html`, `_assets/app.{css,js}`, `_views/*.html`, `_data/*.js` — replacing the
   flat-`_reports/*.html` walk for the migrated view. `rendered_html_files` → `rendered_app_files`
   (html + js + css under the app, excluding caches). Refresh + byte-review the new golden.

## Constraints (do not regress)
- **Offline, no network:** only `<script src>`/`<link href>` of local relative files; NO `fetch`/XHR.
  Verify the app folder opens + the catalog renders by **double-clicking `index.html`** (`file://`) in a
  real browser (light + dark), no server.
- **Byte-deterministic:** every emitted file static (no `random`/`Date`/timestamps); ASCII lint applies
  to all emitted text (incl. `_data/*.js`, routed through `safe_chrome_text` where data-derived).
- `test_parquet_parity` untouched (presentation only, §21.9). Keep c16c a11y (router manages focus +
  `aria-live` on route change) + c16d visual language + reduced-motion/print.
- **Scope discipline:** only the catalog migrates here; the flat static reports + drill still emit as
  today (removed/migrated in c16k–c16l). Do not start the data decoupling for drill yet (c16k).

## Done when
- `index.html` + `_assets/` + `_views/catalog.html` + `_data/catalog.js` emit; opening `index.html` by
  double-click renders the catalog via `#/catalog` with the full design system, **no server, offline**.
- The restructured golden gates the app file-set byte-for-byte; `test_parity` green; `test_parquet_parity`
  unchanged (no digests refresh); `bobframes smoke` lint clean exit 0; browser-verified light/dark.

## Closes
First commit of the **ADR-36** SPA epic (c16j–c16n + close-out). Adds **QUALITY_GATES §21.1l** (app-folder
parity: file-set + bytes, offline, deterministic). No findings closed yet (G-21/G-22 close across the epic).
