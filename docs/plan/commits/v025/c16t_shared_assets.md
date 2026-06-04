# c16t — shared-assets becomes the default bundle delivery     release: v0.2.5 · phase: packaging

> Make the small, deduped bundle the DEFAULT (the common multi-run share), via the c16r seam; `--inline`
> is the opt-out for the per-file-portable form. The standalone one-pager stays inline regardless.
> Revisits ADR-37's accepted per-page duplication now that the win is measured (ADR-41).

## Goal
`bobframes package` defaults to a shared-asset bundle: the ~95 KB of chrome (font + CSS + JS) lives once in
`_assets/` and every page links it depth-relative, collapsing the measured 1.30 MB (30 inlined pages) to
~48 KB of chrome. `--inline` reproduces c16s's self-contained-per-page bundle. All ADR-37 contracts hold.

## Depends on
c16s (the `package` verb + the inline bundle + the standalone summary) + c16r (the `head_assets` seam).

## Scope
1. **Per-family extraction via the seam.** Write once from the composer output: `_assets/report.css` ==
   `_compose_css()`, `_assets/report.js` == `_compose_js()` (the `page_open` family); `_assets/catalog.css`
   == `template._CSS`, `_assets/catalog.js` == `rdc_table_js()` (the catalog/drill family). Each page's head
   is produced by `head_assets(REF, depth)` (`depth = rel.count('/')`) - one source of truth, zero-drift (no
   scrape, no needle). The unique `__labels` inline + per-page `_pagedata/*.js` refs stay.
2. **Flip the default.** `package` defaults to shared-assets; `--inline` reproduces the c16s
   self-contained-per-page bundle byte-for-byte. The standalone `<project>-<rundate>-summary.html` beside
   the zip stays INLINE (self-contained) in BOTH modes - it must work emailed alone.
3. **README updated** to note: keep the whole extracted folder together (a shared-asset page needs the
   sibling `_assets/`); to send just one thing, use the standalone summary.html.
4. **ADR-41** appended: revisits ADR-37's "no `_assets/` extraction / accepted duplication" clause now that
   the size problem is measured; the seam keeps the INLINE render default byte-identical (no second
   render-default golden).
5. **Tests:** extend `tests/test_package.py` + `make_package_golden.py` with the `shared/` golden (now the
   default). Assert: `_assets/report.css` == `_compose_css()` (+ the other three == their composer); the
   base64 font head is ABSENT from every page; each page links the depth-correct `_assets/*` for its family;
   no `fetch(`/`type="module"`; the shared bundle is >= `(report_pages-1) * ~95 KB` smaller than `--inline`;
   **`--inline` reproduces the c16s `inline/` golden byte-for-byte**; the standalone summary is still
   self-contained (unchanged by the default flip).

## Constraints
- The default `render` output stays byte-identical (the INLINE sink is render's path; c16r holds);
  shared-asset output exists only inside the bundle.
- file://-safe relative links only; JS-optional / print / Ctrl-F all hold in the bundle after extraction.
- Two families keep distinct asset files; no shared single CSS across families.

## Done when
- Default `bobframes package <synthetic>` produces the `shared/` bundle matching golden; `--inline`
  reproduces the c16s `inline/` golden byte-for-byte.
- `pytest tests/test_package.py` green: asset bytes == composer output; font absent from pages; depth-correct
  links; no `fetch`/modules; size win >= threshold; standalone summary still self-contained.
- Browser-verified offline from `file://` AFTER EXTRACTION: catalog + a report + a drill render + JS enhances
  from the shared `_assets/`.
- ADR-41 appended; QUALITY_GATES §21.1s extended (shared default + `--inline` equivalence).

## Closes
The duplicated-chrome size problem; shared-assets is the shipped default. Next: c16u (`--redact`).

## As-built (2026-06-04) — rides ADR-41, NO new ADR (deliberate scoping per ADR-23)

Shipped shared-assets as the default `package` bundle. Deviations from the doc above, each rationalized:

1. **Mechanism pivot: copy `_data` + single render root, NOT decoupled read/write roots.** The doc (and
   the approved plan) proposed threading the REF re-render to WRITE into a staging dir while READING data
   from `<root>` (no `_data` copy). That breaks the bundle: each report computes its relative drill / CSV /
   parquet links as `os.path.relpath(target_under_<root>, out_dir_under_staging)` — with the two trees
   siblings, the links ESCAPE the bundle into the source tree (e.g. `../../../../root/_reports/drill/...`),
   and the `../` depth varies with where staging sits (a concrete `test_shared_tree_matches_golden` failure).
   Root cause: `drop_dir` is used for BOTH reading parquet and computing links; decoupling would require
   splitting that across all 8 reports + `render_drop` (invasive, high regression risk). **Shipped instead:**
   `package` shared mode copies `<root>/_data` raw into a temp staging dir and re-renders the whole tree with
   ONE `root=staging` (`sink=REF`), so every relative link resolves IN the bundle; `<root>` is only READ
   (non-mutation holds); the parquet copy is raw → digests match source. Consequently `out_root` /
   `rebuild_cache` were **not** added to the render layer (they were only for the abandoned decoupling) —
   the render-layer change is just `sink` (everywhere) + `build_ts` (the report family + orchestrator).
   (User-confirmed mid-build with the test-failure evidence.)
2. **Pinned `build_ts` for determinism (the doc did not call this out).** The report family stamps
   `base.now_iso()`, so a re-render would make two `package` runs differ → `test_package_is_deterministic`
   (a RAW byte compare) would fail. The shared re-render is given a pinned `build_ts` = the target run's
   `drop_date`. **Recorded consequence:** a shared bundle's report-page "built" line shows the run date, not
   wall-clock, and therefore differs from the `--inline` copy and the standalone summary (verbatim source
   copies). `render_root` / `render_drop` keep their catalog/manifest timestamps (already deterministic).
3. **`--inline` is the opt-out flag** (the doc wrote `--shared-assets`; shared is now the default, so the
   flag names the *exception*). `--light` stays the c16s self-contained subset.
4. **Preview gallery copied raw.** `_reports/_chrome_preview.html` (produced by `bobframes preview`, not the
   orchestrator) is copied raw from `<root>` in shared mode so the file-set matches `--inline`.
5. **A/B pages** (present only if `bobframes ab` was run; the fixtures have none) are re-rendered REF via
   `ab.render_pair`; an unresolvable `<pair>` dir is logged + omitted (never silently mislabeled, ADR-23).

Result: render layer threads `sink` (page_open/report_page/8 build()/render_root/render_drop/orchestrator/
`ab.render_pair`) + `build_ts` (8 build()+orchestrator), all defaulted → `test_parity` + `test_parquet_parity`
UNCHANGED, NO golden refresh. NEW `tests/make_package_golden.py` + `tests/data/golden_package/shared/` (HTML
normalized; `_pagedata`/`_assets`/README raw; `_data` digest-gated, not stored); `inline`/`light` reuse
`golden/`. 253 → 262 green (+9 shared asserts: `_assets/*`==composer, font absent every page,
`head_assets(REF,depth)` per family + an `all_reports()` footgun guard, no `fetch(`/modules, size-win,
`--inline`==render golden, preview-raw). Browser-verified offline from `file://` on the real Perf bundle
(catalog VTable + a report + a drill all enhance from the shared `_assets/`; 0 unresolved `_assets` links
across 30 pages). Real Perf: 2.86 MB duplicated chrome reclaimed (4 shared assets ~206 KB vs ~30 inlined
copies; zip 62.44 MB → 61.14 MB). §21.1s c16t as-built recorded; README "Sharing a report" added; ADR-41
already in DECISIONS (frozen, not re-appended).
