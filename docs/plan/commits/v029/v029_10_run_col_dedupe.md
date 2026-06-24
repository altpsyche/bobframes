# v029_10 -- Captures "RUN" column de-duplication     release: v0.2.9 · phase: ui  (LOW)

> LOW finding: the Captures table lists one row per area (newest drop), so areas captured in the same run
> repeat the same run key down the RUN column (e.g. the real 7-area / 4-run corpus). Show each run once.
> Client display only; zero new dep; no report HTML (golden untouched).

## Scope
- **`assets/panel.js` `render()`** -- the drops rows are sorted by `(runKey, area)` and the RUN cell is
  blanked when it equals the row above, so each run key prints once per group. `runKey(d)` =
  `date[_label]`. No data hidden (the area + capture count still print on every row); only the repeated
  key is de-duplicated.

## Gates / Done when
- Two areas in the same run render the run key on the first row only (the second row's RUN cell is
  empty); distinct runs are unaffected.
- `node --check` green; the `browser` populate-smoke still green; a new `browser` test asserts the
  de-dup on a shared-run fixture; `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity
  unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `panel.js`: `runKey` helper + sort-by-(run,area) + blank-repeated-run-cell in the drops table.
- VERIFIED: `test_ui_browser.test_run_column_dedupes_shared_run` (browser) -- two areas sharing
  `2026-06-01_r1` render cells `['2026-06-01_r1', '']`; the populate smoke (distinct runs) still passes.
  `node --check` clean; `-m "not browser"` **430 passed / 4 deselected** (unchanged count -- the new test
  is browser-marked; +1 deselected); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**;
  no new dep.
