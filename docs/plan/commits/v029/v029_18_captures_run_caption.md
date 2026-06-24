# v029_18 -- Captures: single-run caption, no blank RUN cells     release: v0.2.9 · phase: ui

> Test feedback (user): with all 7 areas in one run, the v029_10 RUN-column de-dup (blank the repeated
> key) read as BROKEN -- 6 empty cells look like missing data, not "same run." Fix the presentation:
> when every area is in one run, drop the column and show the run ONCE as a caption; only show a RUN
> column when runs actually differ, and then fill every row (never blank). Supersedes v029_10's blanking.
> Zero dep; no report HTML (golden untouched).

## Scope
- **`assets/panel.js` `render()`** -- compute the distinct run keys across the discovered drops.
  - **1 run** (the common case): a `Run <code>key</code>` caption above an `Area | Captures` table (no
    RUN column, no blanks).
  - **>1 runs**: an `Area | Run | Captures` table with the run on EVERY row (no blanking).
  Rows stay sorted by `(run, area)`.

## Gates / Done when
- A single-run corpus shows no RUN column and the run once (caption); a multi-run corpus shows a
  populated RUN column. No blank run cells in either case.
- `node --check` green; the 5 `browser` smokes green (the updated single-run test asserts headers ==
  [Area, Captures] and the run appears once); `pytest -m "not browser"` green; `pytest -m golden_env`
  byte-parity unchanged, NO golden refresh. No new dependency.

## As-built (DONE 2026-06-24)
- `panel.js`: single-run caption / multi-run populated column (replaces the v029_10 blank-dedup).
- VERIFIED: `test_ui_browser.test_single_run_shows_run_once_as_caption` -- 2 areas in one run -> headers
  `[Area, Captures]`, run key appears once; the populate smoke (2 distinct runs -> Town + Bay) exercises
  the multi-run branch. `node --check` clean; `-m browser` 5 green; `-m "not browser"` **432 passed / 7
  deselected**; `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
