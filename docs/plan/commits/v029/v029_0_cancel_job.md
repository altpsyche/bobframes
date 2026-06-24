# v029_0 -- Cancel a running job + open the v0.2.9 polish track     release: v0.2.9 · phase: ui

> First commit of the v0.2.9 `bobframes ui` panel-polish track (approved plan
> ~/.claude/plans/plan-a-ui-improvement-track-sharded-sky.md). Closes the MED finding "a 600s/capture
> ingest is unstoppable from the UI": expose `jobs.Job.cancel()` via `POST /api/cancel/<job>` + a Cancel
> button. Also opens the track (STATE / INDEX / ROADMAP). Zero new dep; no report HTML (golden untouched).

## Why this commit exists
A streamed ingest can run 600s per capture. The panel could START it but had no way to STOP it -- a user
who picked the wrong folder or wants to abort had to kill the terminal. `jobs.Job.cancel()` already
existed (v028_2) but was wired to nothing.

## Scope
- **`jobs.py`** -- `Job.cancelled` flag (init False); `Job.cancel()` sets it before `proc.terminate()`,
  so the terminal event can distinguish a user cancel from a real failure. Only the spawned verb process
  is terminated; deeper replay-grandchild cleanup is run.py's concern (R-4/ADR-4), out of panel scope.
- **`server.py`** -- `POST /api/cancel/<job>` (token-gated like every POST) -> `_cancel_job(jid)`:
  looks the job up in the registry, calls `cancel()`, returns `{ok, cancelled}` (404 if no such job).
  The SSE terminal `done` event now carries `cancelled` alongside `rc`.
- **`assets/panel.js` + the shell** -- a **Cancel** button in each job panel (ingest/render-share/ab),
  hidden until a job id arrives, hidden again on `done`; `cancelJob(t)` POSTs `/api/cancel/<job>`; the
  stream's `done` handler reads `cancelled` and shows a neutral "cancelled" (not "failed (exit N)" --
  honest labelling, ADR-23).
- **Track open** -- STATE `active_release = v0.2.9` (+ 0.2.8 recorded SHIPPED), `commits/v029/`,
  INDEX + ROADMAP 0.2.9 rows. No new ADR (rides ADR-47/45/23). `_version` + CHANGELOG deferred to the
  v029_13 close-out (the v028 pattern: dev under the prior shipped version, bump at close-out).

## Gates / Done when
- `POST /api/cancel/<job>` terminates a running (mocked) job; its stream's terminal event carries
  `"cancelled": true`; unknown job -> 404; missing token -> 403.
- The Cancel button shows while a job runs and hides on completion.
- `node --check bobframes/ui/assets/panel.js` green; the `browser` populate-smoke still green;
  `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged, NO golden refresh.
- No new runtime dependency.

## As-built (DONE 2026-06-24)
- `jobs.Job`: `cancelled` flag; `cancel()` sets it before `terminate()`. `server.py`: `POST
  /api/cancel/<job>` -> `_cancel_job` (404 on unknown); SSE `done` event now `{rc, cancelled}`.
  `panel.js` + shell: a Cancel button per job panel (`cancel_run`/`cancel_share`/`cancel_ab`), shown on
  job start / hidden on done; `cancelJob()` POSTs the cancel; the done handler shows "cancelled".
- VERIFIED: `test_ui_cancel` (3) -- cancel terminates a blocking mocked job + the stream's terminal
  event carries `"cancelled": true` + the job is no longer running; unknown job -> 404; missing token ->
  403. `node --check` clean; `-m browser` populate-smoke green (the new buttons' init wiring does not
  throw -> the page still populates); `-m "not browser"` **406 passed / 3 deselected** (was 403 at
  v028_8; +3 cancel tests); `-m golden_env` **5 passed BYTE-UNCHANGED, NO golden refresh**; no new dep.
- Track opened: STATE `active_release = v0.2.9` (0.2.8 recorded SHIPPED), `commits/v029/`, INDEX +
  ROADMAP 0.2.9 rows. No new ADR.
