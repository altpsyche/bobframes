# v029_16 -- progress bar for all jobs (working + replay)     release: v0.2.9 · phase: ui

> Test feedback (user): the v029_14 bar only appeared during ingest's replay; package / rebuild / A-B
> showed none. Give every job a progress affordance -- HONESTLY. The verbs emit a real per-item count
> only for the replay phase (ADR-23: don't fake a % elsewhere), so the bar is **determinate** during
> replay and an **indeterminate "working"** animation for every other phase / job. Zero dep; no report
> HTML (golden untouched).

## Scope
- **`assets/panel.js`** -- `applyProgress(t, d)`: the bar shows for EVERY running job. During replay
  (`phase === "replay"` with a total) it is determinate (`max=replay_total`, `value=replay_done`) and the
  phase strip appends `replay k/n`; for any other phase (export/parse/parquetize/derive/render/catalog,
  and all of package/rebuild/A-B) it `removeAttribute("value")` -> an indeterminate "working" bar.
  `startJob` shows the bar indeterminate from the start of every job; `done` hides it.
- A `<progress>` with no `value` attribute is indeterminate (browser-animated) -- the honest
  representation of "work is happening, no countable total."

## Gates / Done when
- Replay -> determinate bar (`value`/`max` == done/total); a non-replay phase -> indeterminate bar
  (`position === -1`) still visible. Both asserted by `browser` smokes driving the real `applyProgress`.
- `node --check` green; `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged,
  NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `panel.js`: `applyProgress` determinate-during-replay / indeterminate-otherwise; `startJob` shows the
  bar working from the start.
- VERIFIED: `test_ui_browser` (5 browser smokes) -- `test_replay_progress_bar_fills` (determinate
  value 2/max 3) + `test_progress_bar_indeterminate_for_uncounted_phase` (render phase -> position -1,
  visible) both pass; populate/dedup/narrow still green. `node --check` clean; `-m "not browser"`
  **432 passed / 7 deselected** (browser-marked; +1 deselected); `-m golden_env` **5 passed
  BYTE-UNCHANGED, NO golden refresh**; no new dep.
