# v028_3 -- share & explore: render / package / open / serve     release: v0.2.8 · phase: ui

> With ingest + live progress in place (v028_2), this closes the happy path's tail: re-generate
> reports, build a shareable bundle, open the report, and serve it over http -- all from the panel.
> Render and package are streamed subprocess jobs (reuse the v028_2 SSE relay); open and serve are
> one-shot in-process actions. Still zero deps; still no report HTML (golden gate / ADR-37 untouched).

## Scope
- **bobframes/serve.py (new).** The `_cmd_serve` body extracted to `make_server(root, bind, port)`
  (build, don't start; `port=0` -> ephemeral) + `serve_forever(root, bind, port) -> int` (build +
  block, the verb). `cli._cmd_serve` now calls `serve.serve_forever`; behavior is identical (same
  `socketserver.TCPServer` + `SimpleHTTPRequestHandler(directory=root)` + `[HH:MM:SS]` log + exit
  codes). The panel reuses `make_server` for its background click-to-serve.
- **bobframes/ui/jobs.py.** `build_package_argv(root, light, redact)` (mirrors `cli._cmd_package`;
  `package` takes `<root>` positionally) + `spawn_cli(argv)` -> `Popen([python, -m, bobframes.cli, ...])`
  for the verbs that aren't `run.py` (the second spawn seam tests monkeypatch).
- **bobframes/ui/server.py.** `_start_job` refactored to take a zero-arg proc *factory* (run only AFTER
  the busy check, so a 409 never spawns). New POST endpoints (all token-gated):
  - `POST /api/render` -> a render-only job (`build_run_argv(root, render_only=True)` -> no GPU/replay).
    Accent / theme flags ride this endpoint in v028_4.
  - `POST /api/package` -> a streamed `bobframes package` job (`spawn_cli` + `build_package_argv`);
    friendly `light` / `redact` toggles via `_package_opts`.
  - `POST /api/open` -> `webbrowser.open(paths.root_index_html(root))` (in-process; the panel runs on
    the user's own machine, ADR-47 localhost). 409 if nothing is rendered yet.
  - `POST /api/serve` -> a background static file server over `<root>` via `serve.make_server` in a
    daemon thread; returns `{url, port}` (default ephemeral port so it never collides). Idempotent --
    a second call returns the already-running server. `_shutdown_aux` stops it on panel shutdown
    (wired into `serve()`'s finally + the test harness `running()`).
  - Control page gains a **Share & explore** card: Re-generate / Open / Serve buttons + a Package
    block (light/redact toggles). JS refactored into `startJob` (streamed; reuses the SSE pane) +
    `action` (one-shot; shows the JSON result).
- **tests.** `test_ui_share.py` (7): `build_package_argv`; render spawns `--render-only` + streams;
  package spawns the `package` verb with toggles + streams; open calls `webbrowser` (and 409s with no
  report); serve starts a REAL background static server fetched over http (+ idempotent); all four
  actions are token-gated.

## Gates / Done when
- Each action invokes the right verb with the chosen options (render -> render-only; package -> the
  `package` verb with light/redact; open -> the root index; serve -> a static server over root).
- `/api/render` `/api/package` `/api/open` `/api/serve` are token-gated; `/api/serve` actually serves
  `<root>` over http; `/api/open` 409s when no report exists.
- `pytest -m "not browser"` green (no regression; no golden refresh -- panel emits no report HTML).

## As-built (DONE 2026-06-24)
- serve.py extraction + jobs additions + the four endpoints + the Share & explore card implemented as
  scoped. No GPU/RenderDoc: render/package exercised with a monkeypatched `spawn`/`spawn_cli` emitting
  a scripted transcript (the ADR-6 mocked-subprocess discipline); serve uses a real stdlib static
  server on an ephemeral port; open captures `webbrowser.open`.
- DECISION (no patch-fix): package runs as a SUBPROCESS (`bobframes.cli package`) like the other heavy
  verbs, not in-process -- consistent isolation (the panel never imports the renderer), at the cost of
  surfacing the zip path via the streamed log rather than structured JSON (acceptable for v1; a
  structured result is the v0.3 `api.py` seam's job, the same convergence noted for progress).
- `serve` uses an EPHEMERAL port by default (not the cli verb's `8000`) so click-to-serve never fails
  on a busy port; a body `port` pins it. Recorded as a deliberate panel-vs-verb difference.
- VERIFIED: 7/7 new (`test_ui_share`); full `pytest -m "not browser"` -> 388 passed / 2 deselected
  (was 381; +7). No new dependency; no golden refresh.

## Next
v028_4: A/B + theming -- the run-list picker for `POST /api/ab`; accent inputs driving the render
endpoint's `--accent`/`--accent-data`; the opt-in `POST /api/scaffold` (convention-correct folder).
