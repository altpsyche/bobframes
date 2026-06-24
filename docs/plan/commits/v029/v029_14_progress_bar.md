# v029_14 -- replay progress bar     release: v0.2.9 · phase: ui

> Test-driven follow-up (user, while testing the panel before release): ingest showed only a textual
> `replay k/n` counter, no visual bar. The data was already there (`progress.Classifier` emits
> `replay_done`/`replay_total`), so bind a real `<progress>` to it. Post-close-out but pre-release, so it
> rides into v0.2.9. Zero new dep; no report HTML (golden untouched).

## Scope
- **`server.py` (`_SHELL`)** -- a `<progress id="bar_run|bar_share|bar_ab" max="1" value="0" hidden>` in
  each job panel (between the action row and the log).
- **`assets/panel.css`** -- full-width progress styling on `--accent-data`.
- **`assets/panel.js`** -- the per-line stream update is factored into `applyProgress(t, d)` (log + phase
  strip + bar): when `d.replay_total` is set it shows the bar and sets `max=replay_total`,
  `value=replay_done` (replay is the only countable phase -- sequential per-capture). `startJob` resets
  + hides the bar per run; the `done` handler hides it (the phase shows the outcome). `T` objects gain a
  `bar` id.

## Gates / Done when
- Feeding scripted replay lines through the real panel JS fills the bar (`value`/`max` bound to
  `replay_done`/`replay_total`), asserted by a `browser` smoke calling `applyProgress`.
- `node --check` green; the other browser smokes still green; `pytest -m "not browser"` green;
  `pytest -m golden_env` byte-parity unchanged, NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `_SHELL`: 3 `<progress>` bars; `panel.css`: accent-styled full-width bar; `panel.js`: `applyProgress`
  refactor + bar reset/fill/hide.
- VERIFIED: `test_ui_browser.test_replay_progress_bar_fills` (browser) -- scripted `replay 2/3` ->
  bar visible, `value==2`, `max==3`; the other 3 browser smokes still pass (4 total). `node --check`
  clean; `-m "not browser"` **432 passed / 6 deselected** (browser-marked test; +1 deselected);
  `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep. CHANGELOG [0.2.9] gains the
  progress-bar line.
