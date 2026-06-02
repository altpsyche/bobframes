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

## Hard invariants (ADR-36, post-review — establish these HERE, they govern the whole epic)
- **Classic scripts only — NO ES modules.** Chrome blocks `file://` ES-module loading outright, so
  `app.js` is one classic `<script>` (the existing `components_js` IIFE style); no `<script type=module>`,
  no `import`/`import()`, no bundler that emits modules. This is the single rule that keeps double-click
  working; a "modernize to modules" reflex breaks the whole app offline.
- **`#/route` vs `#anchor` scheme.** The router claims ONLY hashes with a leading slash (`#/catalog`,
  `#/report/<name>`, `#/run/<key>/<report>`, `#/drill/<area>/<drop>`). A **bare** `#anchor` (e.g. the
  reports' `#counts`/`#top_meshes`/`#<area>`/sticky-h2 targets) means **scroll within the current view**,
  never a route. Implement the router to ignore non-`/` hashes (let the browser/scroll handle them).
  Existing in-view links are rewritten to this scheme as their views migrate (c16l).
- **Default route.** The root `index.html` is now the SHELL (not the catalog); define the default route
  on open (recommend `#/dashboard`) and a fallback for an unknown hash.
- **Async data load is sequenced** (matters from c16k): the router awaits a `_data/<key>.js` `onload`
  before mounting its VTable — never "inject then mount." Stub the loader contract here.

## Scope
1. **Shell `index.html`** (tiny, static): `<head>` `<link rel=stylesheet href="_assets/app.css">`, a
   `<main id="app">` mount, `<noscript>` linking the single-file export (added c16m), and a **classic**
   `<script src="_assets/app.js">` (no `type=module`). Deterministic text. Defines the default route.
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
6. **Runtime navigation smoke (NOT optional — the byte-golden no longer proves the app works).** The
   static golden proves the files are deterministic; it does NOT prove the router loads + mounts a view.
   Add a **headless-Chrome navigation smoke** (Chrome is already used for the screenshot review → no new
   dependency): open `index.html` over `file://`, navigate to `#/catalog`, `--dump-dom` (or screenshot),
   assert the catalog VTable mounted + a known cell rendered (and a bad route shows the fallback). This
   becomes part of the gate for every later phase. Without it, CI is green on a dead app.

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
- **The headless-Chrome navigation smoke passes** (catalog mounts via `#/catalog` over `file://`; bad
  route → fallback). `app.js` is a classic script (no `type=module`); the `#/route` vs `#anchor` scheme +
  default route are in place. Opening `index.html` by double-click works with no server.

## Closes
First commit of the **ADR-36** SPA epic (c16j–c16n + close-out). Adds **QUALITY_GATES §21.1l** (app-folder
parity: file-set + bytes, offline, deterministic, **+ the headless-Chrome navigation smoke** — the runtime
gate that the byte-golden cannot provide). No findings closed yet (G-21/G-22 close across the epic).
