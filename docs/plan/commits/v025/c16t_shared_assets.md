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
