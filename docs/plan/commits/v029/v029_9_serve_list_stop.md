# v029_9 -- list / stop the background static serve     release: v0.2.9 · phase: ui  (LOW)

> LOW finding: `/api/serve` starts ONE background static server (singleton) with no way to see it or stop
> it from the UI -- it only died on panel shutdown. Add status + stop. Zero new dep; no report HTML
> (golden untouched).

## Scope
- **`server.py`** -- `GET /api/serve` (token-gated) returns `{serving: {url,port}|null}`; `POST
  /api/serve/stop` -> `_stop_serve`: `shutdown()` + `server_close()` the aux httpd (mirrors
  `_shutdown_aux`), clears `bobframes_serve`/`bobframes_serve_httpd` so a later `/api/serve` rebinds a
  fresh port; `{stopped: bool}` (false if nothing was serving).
- **`assets/panel.js`** -- `showServe(info)` renders the URL + a "Stop server" link (-> `POST
  /api/serve/stop`); the Serve action and a new `checkServe()` (run on load) both call it, so an
  already-running serve is surfaced after a page reload and can be stopped.

## Gates / Done when
- `GET /api/serve` reflects start/stop; `POST /api/serve/stop` releases the port (a re-serve rebinds);
  idle stop -> `stopped:false`; status without token -> 403.
- `node --check` green; the `browser` populate-smoke still green (the new `checkServe()` init call does
  not break populate); `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged,
  NO golden refresh. No new runtime dependency.

## As-built (DONE 2026-06-24)
- `server.py`: `GET /api/serve` status + `POST /api/serve/stop` -> `_stop_serve`. `panel.js`:
  `showServe` (URL + Stop link) + `checkServe()` on load.
- VERIFIED: `test_ui_serve_control` (3) -- status null -> start -> listed (same port) -> stop -> null;
  idle stop -> `stopped:false`; status needs token (403). `node --check` clean; `-m browser` green;
  `-m "not browser"` **430 passed / 3 deselected** (was 427 at v029_8; +3); `-m golden_env` **5 passed
  BYTE-UNCHANGED, NO golden refresh**; no new dep.
