# c16o — table a11y parity (both rdc-table modes)     release: v0.2 · phase: De-hardcoding

> **Status: DONE (2026-06-03).** 190 -> 191 green (+`test_c16o_search_input_labelled`,
> `test_c16l_engine_in_shared_report_bundle` extended). A shared `wireSortHeader(th, ci, onSort)` helper
> (authored once in the engine IIFE) makes the sort `<th>` keyboard-operable (`tabindex=0` + Enter/Space →
> `sort(ci)`) in BOTH modes; `VTable.buildHead`/`sort` now set `aria-sort` none→asc/desc (mirroring
> `StaticTable._paintSort`) so catalog/drill announce sort state too; the virtual filter `<input>` gains an
> `aria-label` (`filter <table>` / `filter catalog`) in `html/template.py`. Sort RESULT + row content
> unchanged - only how sort is reached/announced. All 15 HTML goldens + preview refreshed (engine JS inline
> on every page); `_pagedata/*.js` + `digests.json` + `golden_parquet` byte-unchanged, `test_parquet_parity`
> green with NO digests refresh (§21.9). smoke render-only 15 pages lint clean exit 0. Browser-verified
> offline (headless Chrome over CDP, `file://`, real Perf): static - tabindex/aria-sort/focusable/Enter-sorts/
> expand-toggle; virtual catalog - 25 built headers all tabindex+aria-sort, search aria-label, Enter sorts;
> dark mode differs. No new ADR (rides ADR-38 a11y tail). QUALITY_GATES §21.1p added; G-23 a11y tail closed.

> **ADR-38 (a11y tail).** The unified `rdc-table` engine has two modes (StaticTable / VTable). c16l restored
> `aria-sort` on the STATIC engine (parity with the deleted `rdc-sortable-table`), but the VTable (catalog/
> drill, virtual) never got it, and neither mode's sort headers are keyboard-operable. c16o brings the
> engine to a11y parity across both modes so a feature added once works the same everywhere.

## Goal
Make sorting + filtering accessible and consistent across BOTH table modes. Today (confirmed in
`reports/chrome.py`): `aria-sort` is set only by `StaticTable._wireHeaders`/`_paintSort`; `VTable.buildHead`
sets none. In both modes the sortable header is a bare `<th>` with a click listener (no `tabindex`/`role`),
so sort is mouse-only — not reachable by keyboard. The virtual search `<input type="search">` has a
`placeholder` but no accessible label.

## Depends on
`c16k`/`c16l`/`c16m` (the one engine; StaticTable already announces `aria-sort`). ADR-38.

## Scope
1. **VTable `aria-sort` (virtual parity).** In `VTable.buildHead`/`sort`, set `aria-sort`
   `none`→`ascending`/`descending` on the header `<th>` (mirror `StaticTable._paintSort`), so screen readers
   announce sort state on catalog/drill too — closing the gap recorded at c16l ("VTable sort still has no
   aria-sort - separate a11y pass").
2. **Keyboard-operable sort headers (both modes).** The sort `<th>` carry a click listener but aren't
   focusable. Add `tabindex="0"` + `role="columnheader"`(implicit) + an Enter/Space key handler that
   triggers the same `sort(ci)` (shared between StaticTable + VTable), so sorting works without a mouse.
   Keep the visual cursor:pointer. Deterministic, offline.
3. **Search input label.** Give the virtual filter `<input type="search">` an `aria-label`
   (e.g. `filter <table>`) in `html/template.py` (the placeholder is not a label substitute).
4. **Verification sweep (the live eyeball c16m/c16n deferred).** In a real browser on real Perf, confirm:
   the expand-toggle click flips `data-expand` (cells reveal); JS-off shows clip + `title=` + Ctrl-F; dark
   mode; `aria-sort` announced on both modes (DOM check); keyboard Tab→Enter sorts; reduced-motion holds.

## Constraints (do not regress)
- Behavior/markup-only on the engine (inline on every page) → expect a golden refresh; `test_parquet_parity`
  untouched (§21.9). Offline + byte-deterministic (no `random`/`Date`) + ASCII. The aria-sort/keyboard
  additions must not change row content or the sort RESULT (only how it is reached/announced).

## Done when
- VTable announces `aria-sort` (none→asc/desc) — parity with StaticTable, verified in the rendered DOM both
  modes; sort headers are keyboard-focusable + Enter/Space sorts in both modes; the virtual search input has
  an `aria-label`.
- Golden refreshed + reviewed; `test_parity` green; `test_parquet_parity` green with no digests refresh;
  `bobframes smoke` lint clean; browser-verified offline (incl. keyboard + a screen-reader-ish aria check).
- `test_report_structure`/`test_c16l_engine_in_shared_report_bundle` extended: `aria-sort` set by BOTH
  engines; sort headers `tabindex`; search input labelled.

## Closes
The G-23 a11y tail — both modes of the one engine at sort/filter a11y parity.
