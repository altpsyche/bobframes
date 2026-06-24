# v029_5 -- A/B: link every report in the pair     release: v0.2.9 · phase: ui

> MED finding: after an A/B run the panel linked only `summary.html`, but `bobframes ab` renders all six
> reports into `_reports/ab/<base>_vs_<cmp>/`. Surface a link to each. Zero new dep; no report HTML
> (golden untouched). Closes the MED tier of the v0.2.9 track (v029_0..5).

## Scope
- **`server.py`** -- `GET /api/ab/reports?base=&cmp=` (token-gated, read-only) -> `_ab_reports`: lists
  `*.html` in `_reports/ab/<base>_vs_<cmp>/` as `{reports: [{name, rel}]}` (`.html` stripped from name;
  `rel` is the root-relative path the existing traversal-guarded `/api/open` accepts). Run keys form a
  directory name, so they're guarded against separators / `..` (400); an un-rendered pair -> empty list.
  Reuses `_open_report(rel)` (server.py) for the actual open -- no new open path.
- **`assets/panel.js`** -- the A/B `onDone` now calls `showAbReports(b, c)`, which fetches the list and
  renders a link per report in `#ab_result`; `openAbReport` opens one via `POST /api/open {path: rel}`
  and writes the "Opened ..." note to `#ab_hint` so the link list persists (the v028_6 "don't wipe the
  region that holds the links" lesson). The old single `summary.html` link is gone.

## Gates / Done when
- After a pair is rendered, `GET /api/ab/reports` returns every `.html` (sorted, name without ext,
  rel under the pair dir); unknown pair -> empty; missing token -> 403; traversal key -> 400.
- The panel lists all pair reports; each opens via the validated `/api/open`.
- `node --check` green; the `browser` populate-smoke still green; `pytest -m "not browser"` green;
  `pytest -m golden_env` byte-parity unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `server.py`: `GET /api/ab/reports` -> `_ab_reports` (globs the pair dir; key-guarded; reuses the
  `/api/open` traversal guard for opening). `panel.js`: `showAbReports` lists+links every report,
  `openAbReport` opens one without clearing the list.
- VERIFIED: `test_ui_ab_reports` (4) -- lists every `.html` (sorted, `.txt` excluded, correct rel);
  unknown pair -> empty; missing token -> 403; `..` key -> 400. `node --check` clean; `-m browser` green;
  `-m "not browser"` **419 passed / 3 deselected** (was 415 at v029_4; +4); `-m golden_env` **5 passed
  BYTE-UNCHANGED, NO golden refresh**; no new dep. **MED tier (v029_0..5) complete.**
