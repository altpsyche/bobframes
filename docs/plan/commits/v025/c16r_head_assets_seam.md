# c16r — the head_assets(sink) seam (zero-output refactor)     release: v0.2.5 · phase: packaging

> A pure refactor that gives the asset boundary ONE source of truth, so `--shared-assets` (c16t) can emit
> linked assets by construction instead of scraping rendered HTML. Render output stays BYTE-IDENTICAL;
> parity is green by construction. Rides ADR-41 (built fully at c16t).

## Goal
Extract the head asset emission (`<style>{_compose_css()}</style>` + the `<script>{_compose_js()}</script>`,
and the catalog/drill equivalent) into a single `head_assets(sink, depth)` helper with an `INLINE` sink
(today's exact bytes) and a `REF` sink (`_assets/` + depth-relative links), changing NOTHING about the
default render.

## Depends on
c16q. Touches `reports/chrome.py` (`page_open`) and `html/template.py` (its `_CSS` + `rdc_table_js` tags).

## Scope
1. **`chrome.head_assets(sink, depth=0)`** returns, for `INLINE`, the exact current string
   `'<style>'+_compose_css()+'</style>'+'<script>'+_compose_js()+'</script>'`; for `REF`,
   `'<link rel="stylesheet" href="'+('../'*depth)+'_assets/report.css">'` +
   `'<script defer src="'+('../'*depth)+'_assets/report.js"></script>'`. `page_open` calls
   `head_assets(INLINE)` (default) at the same emission point - byte-identical output.
2. **Template equivalent** for the catalog/drill family: a helper returning `INLINE`
   (`'<style>'+_CSS+'</style>'` + the `'<script>'+rdc_table_js()+'</script>'` tag) or `REF`
   (`_assets/catalog.css` + `_assets/catalog.js`), leaving the unique `__labels` inline + the per-page
   `_pagedata` `<script defer src>` refs untouched. Default INLINE - byte-identical.
3. **`paths.ASSETS_DIR = '_assets'`** added (single-sourced layout; used by the REF sink + c16s/c16t).
4. **Tests:** `tests/test_head_assets.py` - `head_assets(INLINE)` equals the exact prior inlined bytes
   (snapshot of the composed string); `head_assets(REF, d)` emits depth-correct `_assets/report.{css,js}`
   links for `d in {0,1,2,4}`; the template helper likewise.

## Constraints
- **Zero output change.** This commit must NOT refresh any golden. The INLINE sink is the sole render path
  and is byte-for-byte what `page_open`/template emit today.
- No new dependency; ASCII; the REF sink emits relative `file://`-safe links only.
- The two page families keep DISTINCT asset files (their CSS bundles + JS differ); no shared single file.

## Done when
- ALL 15 HTML goldens + `_pagedata/*.js` + preview BYTE-UNCHANGED (`pytest tests/test_parity.py` green with
  no refresh); `test_parquet_parity` untouched.
- `pytest tests/test_head_assets.py` green: INLINE == prior bytes; REF depth-correct, both families.
- QUALITY_GATES §21.1r added.

## Closes
(none) - enables c16t. Next: c16s (the `package` verb + the friendly bundle).
