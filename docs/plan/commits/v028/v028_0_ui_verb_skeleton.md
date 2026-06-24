# v028_0 -- `ui` verb + control-panel skeleton + ADR-47     release: v0.2.8 · phase: ui (control panel)

> Opens v0.2.8 (the `bobframes ui` local-web control panel; approved plan
> ~/.claude/plans/lets-plan-on-improving-bubbly-bumblebee.md). This commit lays the spine: ADR-47
> (frontends are a SURFACE above the verb taxonomy), a new top-level `ui` verb, and the
> `bobframes/ui/` package serving a placeholder page over a localhost `ThreadingHTTPServer` that
> starts/stops cleanly. The control page, read-only `/api/state`, the security token, and the
> subprocess job + SSE runner land in v028_1..-5. ZERO new dependencies (stdlib http.server, the
> `serve` pattern). No report HTML emitted -> golden gate untouched.

## Goal
`bobframes ui` exists end to end as a skeleton: the verb parses, dispatches, and a localhost server
serves a placeholder and shuts down on Ctrl+C, on a working spine the rest of the panel builds on.

## Scope
- **docs/plan/DECISIONS.md.** ADR-47 appended (append-only): human frontends layer above the ADR-40
  taxonomy; the first is a zero-dep stdlib-http local control panel that DRIVES the verbs (read-only
  state in-process; heavy work by spawning the existing CLI verbs as subprocesses); reaffirms ADR-37
  (no report-HTML artifact) + ADR-17 (no core dep); localhost bind + per-session token guard; hard
  governance limit (no JS framework / router / build step).
- **bobframes/ui/__init__.py + bobframes/ui/server.py.** New package. `build_server(root, bind, port)`
  -> a `ThreadingHTTPServer` bound to `127.0.0.1` with a `_Handler` serving the placeholder on
  `/` (200) and 404 otherwise; `serve(root, bind, port, open_browser)` blocks on `serve_forever`,
  auto-opens the browser via a short `threading.Timer`, maps Ctrl+C -> exit 4 and a bind failure ->
  exit 1. Request logging routed to the `bobframes` logger at DEBUG (no stderr scribble by default).
- **bobframes/cli.py.** `_cmd_ui` (lazy-imports `.ui.server`, so a core install never loads it) +
  a `ui` subparser: `[root=.] [--port 8765] [--bind 127.0.0.1] [--no-open]`.
- **docs/plan/STATE.md.** active_release -> v0.2.8; current -> v028_0 DONE / next v028_1.

## Gates / Done when
- `bobframes ui --help` prints the verb usage.
- The server starts, serves `/` (200, the placeholder), 404s an unknown path, and shuts down cleanly.
- `pytest -m "not browser"` stays green (no regression; this commit emits no report HTML, so the
  golden byte-parity gate is unaffected and unrefreshed).

## As-built (DONE 2026-06-24)
- ADR-47 appended to DECISIONS.md.
- `bobframes/ui/` created (`__init__.py` thin re-export of `serve`; `server.py` skeleton). Bound to
  localhost only; `daemon_threads=True`; the root is stashed on the server for later handlers.
- `_cmd_ui` + `ui` subparser wired into cli.py (lazy import; long-flag only, matching house style).
- VERIFIED: `bobframes ui --help` ok; an in-process start/stop smoke (build_server on :8799,
  serve_forever in a thread) returned 200 + the placeholder on `/`, 404 on `/nope`, and stopped
  cleanly. Full `pytest -m "not browser"` -> 365 passed / 2 deselected (no regression).
- No new dependency; no golden refresh.

## Next
v028_1: the generated control page on `/` + read-only `GET /api/state` (tools via
`config.resolve_tool_verbose`, drops via `discovery.find_drops`) + the security guard (localhost bind
+ a random per-session token required on every `/api/*` call). Tests: test_ui_state / test_ui_security
/ test_ui_smoke.
