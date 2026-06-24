# v028_1 -- control page + read-only /api/state + security guard     release: v0.2.8 · phase: ui

> Second v0.2.8 commit. Replaces the v028_0 placeholder with the real control page, adds a read-only
> `GET /api/state` (RenderDoc tools + discovered drops), and installs the ADR-47 security guard: the
> server (already localhost-only) now mints a per-session token that the auto-opened URL carries and
> every `/api/*` request must present (else 403). Still zero deps; still no report HTML.

## Goal
The panel page loads in a browser, fetches state, and shows the resolved RenderDoc tools + the
discovered capture drops for the chosen folder; `/api/*` is token-gated end to end.

## Scope
- **bobframes/ui/server.py.**
  - `panel_state(root)` -- pure read-only state: `_tool_state()` (resolve renderdoccmd + qrenderdoc via
    `config.resolve_tool_verbose`, exactly as `cli._cmd_check`; `ToolNotFound` -> `{found: false,
    message}`) + `_drop_state(root)` (`discovery.find_drops` -> area/date/label/captures; `None` if the
    root is missing) + `platform`/`windows`/`convention`.
  - `control_page()` -- the single server-rendered HTML page (vanilla JS, no framework/router/build
    step per ADR-47). Reads the session token from its own `?t=` URL, fetches `/api/state`, renders the
    tools + a drops table (with empty/`missing-root` states surfacing the `<Area>/<date[_label]>/*.rdc`
    convention).
  - Security: `build_server` mints `bobframes_token = secrets.token_urlsafe(32)`; `_Handler` serves the
    page on `/` (open) and `/api/state` only with a valid token (query `t=` or `X-Bobframes-Token`
    header, `secrets.compare_digest`), else 403. `serve()` puts the token in the opened URL.
- **bobframes/tests/_ui_util.py (new).** `make_capture_root` (the test_discovery `<Area>/<date>/*.rdc`
  layout), a `running(root)` ephemeral-port server contextmanager, and a `get()` helper.
- **tests/test_ui_security.py, test_ui_state.py, test_ui_smoke.py (new).** Token gating (no/bad/good
  token + header path), localhost bind, the drops/tools JSON shape against a real capture tree,
  missing-root -> null drops, and the page+state smoke.

## Gates / Done when
- `GET /` returns the control page; `GET /api/state?t=<token>` returns tools + drops for the fixture.
- `/api/state` without a valid token returns 403; the server binds `127.0.0.1`.
- `pytest -m "not browser"` green (no regression; no golden refresh -- the panel emits no report HTML).

## As-built (DONE 2026-06-24)
- `panel_state` + `control_page` + the token guard implemented in `bobframes/ui/server.py`
  (HTTP/1.1, `ThreadingHTTPServer`). Page is ASCII-only, self-contained; on-brand styling via
  `chrome.design_tokens_css()` is deferred to v028_5 polish.
- 8 new tests (security 4, state 3, smoke 1) all green; full `pytest -m "not browser"` -> 373 passed /
  2 deselected (was 365; +8). No golden refresh; no new dependency.

## Next
v028_2: the subprocess job runner + SSE progress + `POST /api/ingest`. Spawn `python -m bobframes.run`
(the `_render_watch` precedent), stream its `[HH:MM:SS]` stdout to the browser over Server-Sent Events
(`GET /api/stream/<job>`), terminal event carrying the return code; client stage strip + per-capture
replay bar + raw log pane. Test `test_ui_jobs` with a mocked spawn (no GPU).
