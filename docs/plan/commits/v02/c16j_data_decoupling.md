# c16j — decouple the heavy catalog/drill data (static; the ~21 MB TTI fix)     release: v0.2 · phase: De-hardcoding

> **DONE 2026-06-03.** Heavy VTable rows moved out of the catalog/drill HTML into `_pagedata/<key>.js`
> (a NEW sibling dir, NOT `_data/` — collision-avoiding refinement of this doc's loose `_data/<key>.js`,
> user-confirmed) loaded by a classic file://-safe `<script defer src>`. Only the heavy `__data_*` moved;
> `__colgroups_catalog`/`__labels` + the shared `_JS` stay inline. Reports/dashboard goldens byte-unchanged;
> `test_parquet_parity` green with no digests refresh. 171→176 green; browser-verified offline (real Perf
> heaviest drill 17.6 MB→134 KB shell + 17.5 MB across 28 `.js`). Closes G-21/G-22; QUALITY_GATES §21.1l
> consolidated. See STATE `last_session`.

> **Repurposed by ADR-37 (2026-06-02).** This slot was originally "SPA spine"; the SPA (ADR-36) was rejected
> on a lifespan review. c16j is now the **static** heavy-data decoupling — the one real perf fix from the
> design reviews — with NO router, NO SPA, NO whole-output rewrite. Pairs with the revived **c16i**
> (catalog/drill readability). The durable data investment lives in **c20 (`--json`)** + **c30 (schema/query)**.

## Goal
Kill the ~21 MB inline-data drill/catalog TTI by moving the heavy VTable payloads **out of the HTML** into
separate `_data/<key>.js` files loaded via a plain `<script src>`, so the page's HTML shell is tiny and
parses/paints instantly while the data streams as its own resource. Pages stay **static, multi-page, with
browser-native links** — the durable form (ADR-37).

## Depends on
`html/template.py` (the catalog root + per-drop drill renderers; the `_JS` VTable; today's inline data as
`<script>window.__data_<table>=…`). Per ADR-37, reports/dashboard are NOT touched (they stay self-contained
single files).

## Scope
1. **Externalize the heavy payloads.** Today `template.py` bakes each VTable's rows inline
   (`<script>window.__data_<table>={…}</script>`, e.g. `template.py:654`/`:1041`). Emit each instead as
   `_data/<key>.js` (`window.__data_<table>={…};` — same JSON, just in its own file) under the report root,
   and reference it from the page with a **plain classic `<script src="_data/<key>.js">`** (file://-safe; NO
   `fetch`, NO module). Applies to the catalog (root `index.html`) + every per-drop drill page.
2. **Defer so the shell paints first.** Place the data `<script src>` + the VTable-init script with `defer`
   (or at end of `<body>`) so the page structure + a skeleton/"loading" state render immediately, then the
   VTable populates when its data file has loaded. Classic scripts execute in document order, so a data
   `<script src>` placed before the init runs first — **no dynamic injection, no onload race** (that race was
   an SPA problem; in the static multi-page world it is just script order).
3. **HTML stays small + archivable.** The drill/catalog HTML no longer carries the megabytes; it is a small
   static page that links its `_data/<key>.js`. (Those pages were never portable-as-one-file or JS-optional —
   the VTable is JS — so this costs nothing real; ADR-37.)
4. **Golden restructure (scoped).** Extend the parity harness to gate the catalog/drill pages **plus** their
   `_data/*.js` files (byte-for-byte; deterministic JSON via `json.dumps(…, separators=(',',':'))`). Reports'
   goldens are UNCHANGED (they keep inline data + stay self-contained). `rendered_html_files` grows a
   `_data/*.js` companion walk for the catalog/drill family.

## Constraints (do not regress)
- **Offline, no network:** only `<script src>` of local relative files; NO `fetch`/XHR; classic script (no
  ES modules — Chrome blocks `file://` module loading). Verify by **double-clicking** the drill page
  (`file://`) in a real browser: shell paints fast, VTable populates, sort/search/scroll work.
- **Byte-deterministic:** the page + every `_data/*.js` is static (no `random`/`Date`); ASCII lint; data-
  derived text already escaped in the payload. `test_parquet_parity` untouched (presentation only, §21.9).
- **Reports/dashboard untouched** (ADR-37): they remain self-contained single files, JS-optional, golden-as-
  output. Only the catalog/drill (already JS-dependent + non-portable) decouple their data.
- VTable correctness: data must be defined before the VTable reads it (script order / `defer`); verify on the
  **real Perf data** (the actual 21 MB drill) that TTI improves and the table still works.

## Done when
- The catalog + every drill page load their rows from `_data/<key>.js` via `<script src>`; the HTML shell is
  small + paints before the data; TTI on the real 21 MB drill is visibly better; sort/search/scroll intact.
- Reports/dashboard goldens UNCHANGED; catalog/drill page + `_data/*.js` goldens refreshed + reviewed;
  `test_parity` green; `test_parquet_parity` unchanged (no digests refresh); `bobframes smoke` lint clean
  exit 0; browser-verified by double-click (offline), light + dark.

## Closes
The heavy-data half of **G-21/G-22** (the readability half is the sibling **c16i**). Resolves the real
problem behind the design reviews **statically**, per **ADR-37** (no SPA). Add **QUALITY_GATES §21.1l**
(catalog/drill page + `_data/*.js` parity; offline; deterministic) when c16i + c16j land.
