# v029_3 -- honest ingest time estimate     release: v0.2.9 · phase: ui

> MED finding: ingest replays each capture through a 600s budget with no time affordance, so a user
> can't tell if a run will take 2 minutes or an hour. Show `captures x replay_timeout_s` as a labelled
> WORST-CASE upper bound (ADR-23: it's the per-capture budget, not the expected time -- never a promise).
> Zero new dep; no report HTML (golden untouched).

## Scope
- **`server.py`** -- `panel_state` gains `replay_timeout_s`, read from the root's resolved config
  (`cfg.pipeline.replay_timeout_s`) via `_replay_timeout_s(root)` -> `config._build_config(root)` (the
  NON-mutating builder, so the panel never disturbs the global `config._ACTIVE` singleton); falls back to
  the documented 600.0 default if config can't be built. So the estimate honours a user who tuned the
  budget in `.bobframes.toml`.
- **`assets/panel.js` + shell** -- a `#ingest_estimate` hint in the Generate section; `render()` sums the
  discovered drops' captures and shows "Estimated ingest: up to ~X for N capture(s) -- worst case, Ys
  replay budget each, run sequentially." (`fmtDur` -> seconds under 90s, else minutes). It stays visible
  during the job, complementing the live per-capture `replay k/n` bar. Empty when there are no captures.

## Gates / Done when
- `/api/state` exposes `replay_timeout_s` (default 600.0; reflects a `[pipeline] replay_timeout_s`
  override in the root config).
- The estimate renders in-browser as a labelled upper bound (the populate-smoke asserts it: 4 captures
  x 600s -> ~40 min).
- `node --check` green; `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged,
  NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `server.py`: `_replay_timeout_s(root)` (non-mutating `_build_config`) + `replay_timeout_s` in
  `panel_state`. `panel.js`: `fmtDur` + a worst-case estimate line summing drop captures.
- VERIFIED: `test_ui_estimate` (2) -- state exposes the default 600.0 + reflects a 120.0 config override.
  `test_ui_browser` extended -> the in-browser estimate reads "4 capture(s) ... min" (the JS calc, end to
  end). `node --check` clean; `-m browser` green; `-m "not browser"` **413 passed / 3 deselected** (was
  411 at v029_2; +2); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
