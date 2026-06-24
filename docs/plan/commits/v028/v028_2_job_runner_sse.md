# v028_2 -- subprocess job runner + SSE progress + /api/ingest     release: v0.2.8 · phase: ui

> The live-progress core. The panel runs heavy work by SPAWNING the existing verb (`python -m
> bobframes.run`) as a subprocess (the `cli._render_watch` precedent -- never in-process, so the
> `os.environ`/`config._ACTIVE` mutation and a qrenderdoc native fault cannot corrupt the panel) and
> streams its `[HH:MM:SS]` stdout to the browser over Server-Sent Events. A server-side classifier
> turns each line into a structured event (phase + replay k/n) so the client draws a stage strip + a
> per-capture bar without parsing strings. Still zero deps; still no report HTML.

## Scope
- **bobframes/ui/jobs.py (new).** `build_run_argv(root, force, render_only, workers, pixel_grid)`
  (mirrors `cli._cmd_ingest`); `spawn(argv)` -> `Popen([sys.executable, '-m', 'bobframes.run', ...])`
  with merged text stdout (the single seam tests monkeypatch); `Job(proc)` pumps stdout line-by-line
  into a `queue.Queue` on a daemon thread, appends a `DONE` sentinel, and records `.rc`; `running()`
  / `cancel()`.
- **bobframes/ui/progress.py (new).** A stateful `Classifier.feed(line) -> {line, phase, replay_done,
  replay_total}` keyed on run.py's stable `_log()` substrings + a `replay: N captures` regex; a per-
  capture replay line (`rc=`) ticks the counter. Server-side so it is unit-tested in pytest. The raw
  line is always carried through verbatim (ADR-23) -- a reworded log degrades to "phase strip stalls,
  log keeps scrolling".
- **bobframes/ui/server.py.** `build_server` adds a `bobframes_jobs` registry. `POST /api/ingest`
  (token-gated; coerces the JSON body via `_ingest_opts`; one job at a time -> 409 when busy; returns
  `{job}` 202). `GET /api/stream/<job>` (token via query -- EventSource cannot set headers): an
  `text/event-stream` that relays each classified line as a `data:` event + a `: keepalive` every idle
  second (the 600s/capture replay) + a final `event: done` with the return code; `Connection: close`.
  Control page gains a Run card (force / render-only / workers + Ingest) that POSTs then consumes the
  EventSource into a stage line + a raw log pane, and refreshes the drop list on a clean exit.
- **tests.** `test_ui_progress.py` (the classifier vs a faithful run.py transcript -- the highest-value
  lock); `test_ui_jobs.py` (mocked `spawn` -> POST /api/ingest + the SSE relay + rc, the 403/409/404
  paths, and `build_run_argv`). `_ui_util.post` added.

## Gates / Done when
- A mocked ingest streams its scripted stdout to the SSE client and the `done` event carries the rc.
- `/api/ingest` is token-gated; an unknown stream job 404s; the classifier maps a real transcript to
  the right phases + replay count.
- `pytest -m "not browser"` green (no regression; no golden refresh -- panel emits no report HTML).

## As-built (DONE 2026-06-24)
- jobs.py + progress.py + the server endpoints + the Run-card client implemented as scoped.
- No GPU/RenderDoc: the run path is exercised with a monkeypatched `spawn` emitting a scripted
  transcript (the ADR-6 mocked-subprocess discipline). 16 new ui tests total across v028_1+v028_2.
- VERIFIED: 8/8 new (progress 3 + jobs 5); full `pytest -m "not browser"` -> 381 passed / 2 deselected
  (was 373; +8). No new dependency; no golden refresh.

## Next
v028_3: share & explore -- `POST /api/render` (with the v028_4 theme flags later), `POST /api/package`
(light/redact toggles via `package.build`), `POST /api/open` (`webbrowser.open(root_index_html)`),
`POST /api/serve` (the `_cmd_serve` body, optionally extracted to `serve.serve_forever`).
