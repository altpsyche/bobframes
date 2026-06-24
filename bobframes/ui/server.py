"""The ``bobframes ui`` server (ADR-47).

A zero-dependency local-web control panel on the stdlib ``http.server`` that DRIVES the existing verbs
for QA / product who are not comfortable in a terminal. It emits no report HTML (golden gate / ADR-37
untouched) and pulls no dependency into core (ADR-17).

v028_0 spine: a localhost ``ThreadingHTTPServer`` that starts/stops cleanly.
v028_1 (this): the generated control page on ``/``, a read-only ``GET /api/state`` (tools + drops), and
the security guard -- localhost bind + a random per-session token required on every ``/api/*`` call.
v028_2.. add the subprocess job runner + SSE progress and the action endpoints.

Security (ADR-47): the panel will spawn subprocesses on POST in later commits, so it (a) binds
``127.0.0.1`` only and (b) mints a random per-session token at startup that the auto-opened URL carries
and every ``/api/*`` request must present (else 403). The control page reads the token from its own URL.

Exit codes mirror the CLI (errors.py / ARCHITECTURE §4): 0 clean stop, 1 port unavailable, 4 Ctrl+C.
"""
from __future__ import annotations

import http.server
import json
import logging
import os
import queue
import secrets
import sys
import threading
import webbrowser
from urllib.parse import parse_qs, urlparse

from .. import errors
from . import jobs, progress

_logger = logging.getLogger('bobframes')

# The capture-folder convention surfaced to the user when no drops are found (matches discovery).
_CONVENTION = '<Area>/<YYYY-MM-DD[_label]>/*.rdc'


# --- read-only state (in-process; no side effects) ---------------------------------------------

def _tool_state() -> list[dict]:
    """Resolve the external tools exactly as `bobframes check` does (cli._cmd_check)."""
    from .. import config
    from ..errors import ToolNotFound
    out: list[dict] = []
    for name in ('renderdoccmd', 'qrenderdoc'):
        try:
            path, source = config.resolve_tool_verbose(name)
            out.append({'name': name, 'found': True, 'path': path,
                        'source': '' if source == path else source})
        except ToolNotFound as e:
            out.append({'name': name, 'found': False, 'message': e.format_message()})
    return out


def _drop_state(root: str) -> list[dict] | None:
    """Discovered drops via discovery.find_drops (one per area, newest). None if the root is missing."""
    from .. import discovery
    try:
        drops = discovery.find_drops(root)
    except FileNotFoundError:
        return None
    return [{'area': d.area, 'date': d.drop_date, 'label': d.drop_label,
             'captures': list(d.captures), 'n_captures': len(d.captures)} for d in drops]


def panel_state(root: str) -> dict:
    """The full read-only state the control page renders. Pure: resolves tools + discovers drops."""
    return {
        'root': os.path.abspath(root),
        'platform': sys.platform,
        'windows': sys.platform == 'win32',
        'convention': _CONVENTION,
        'tools': _tool_state(),
        'drops': _drop_state(root),
    }


# --- control page (server-rendered HTML + vanilla JS; no framework, no build step) --------------

def control_page() -> str:
    """The single control page. ASCII-only; reads the session token from its own URL (``?t=``) and
    fetches ``/api/state`` to render tools + drops. On-brand styling polish is v028_5."""
    # NOTE: JS lives in a normal <script>; { } in the JS are fine (this is a plain string, not a
    # str.Template). Keep ASCII and avoid backticks-in-Python by building the JS with regular quotes.
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bobframes ui</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.5 system-ui, sans-serif; max-width: 52rem; margin: 2.5rem auto; padding: 0 1rem; }
  h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
  .muted { color: #6b7280; }
  .card { border: 1px solid #d1d5db; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
  .row { display: flex; gap: .5rem; align-items: baseline; }
  .ok { color: #15803d; } .bad { color: #b91c1c; }
  code { background: #00000010; padding: .1rem .35rem; border-radius: 4px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #e5e7eb; }
  pre { white-space: pre-wrap; font-size: 12px; color: #6b7280; }
</style>
</head><body>
<h1>bobframes ui</h1>
<p class="muted" id="root">Loading...</p>
<div class="card"><h2>RenderDoc tools</h2><div id="tools">...</div></div>
<div class="card"><h2>Capture drops</h2><div id="drops">...</div></div>
<div class="card"><h2>Run pipeline</h2>
  <label><input type="checkbox" id="force"> force re-ingest (rebuild from captures)</label><br>
  <label><input type="checkbox" id="render_only"> render only (rebuild reports from existing data)</label><br>
  <label>workers <input type="number" id="workers" min="1" style="width:4rem"></label>
  <button id="ingest">Ingest</button>
  <p id="phase" class="muted"></p>
  <pre id="log" style="max-height:18rem;overflow:auto"></pre>
</div>
<script>
  var TOKEN = new URLSearchParams(location.search).get("t") || "";
  function esc(s){var d=document.createElement("div");d.textContent=(s==null?"":String(s));return d.innerHTML;}
  function el(id){return document.getElementById(id);}
  function render(s){
    el("root").innerHTML = "Project root: <code>" + esc(s.root) + "</code>";
    var t = s.tools.map(function(x){
      return x.found
        ? '<div class="row"><span class="ok">OK</span> <strong>'+esc(x.name)+'</strong> <code>'+esc(x.path)+'</code> <span class="muted">'+esc(x.source)+'</span></div>'
        : '<div><div class="row"><span class="bad">missing</span> <strong>'+esc(x.name)+'</strong></div><pre>'+esc(x.message)+'</pre></div>';
    }).join("");
    el("tools").innerHTML = t || '<p class="muted">none</p>';
    if (s.drops === null) {
      el("drops").innerHTML = '<p class="bad">Folder not found: <code>'+esc(s.root)+'</code></p>';
    } else if (s.drops.length === 0) {
      el("drops").innerHTML = '<p class="muted">No capture drops found. Expected layout: <code>'+esc(s.convention)+'</code></p>';
    } else {
      var rows = s.drops.map(function(d){
        var key = esc(d.date) + (d.label ? "_" + esc(d.label) : "");
        return "<tr><td>"+esc(d.area)+"</td><td>"+key+"</td><td>"+esc(d.n_captures)+" capture(s)</td></tr>";
      }).join("");
      el("drops").innerHTML = "<table><thead><tr><th>Area</th><th>Run</th><th>Captures</th></tr></thead><tbody>"+rows+"</tbody></table>";
    }
  }
  function loadState(){
    fetch("/api/state?t=" + encodeURIComponent(TOKEN))
      .then(function(r){ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
      .then(render)
      .catch(function(e){
        el("root").innerHTML = '<span class="bad">Could not load state ('+esc(e.message)+'). Open the panel via the link printed in the terminal (it carries the session token).</span>';
      });
  }
  function stream(job){
    var es = new EventSource("/api/stream/" + job + "?t=" + encodeURIComponent(TOKEN));
    var log = el("log");
    es.onmessage = function(ev){
      var d = JSON.parse(ev.data);
      log.textContent += d.line + "\n"; log.scrollTop = log.scrollHeight;
      var p = d.phase || "running";
      if (d.replay_total) p += "  -  replay " + d.replay_done + "/" + d.replay_total;
      el("phase").textContent = p;
    };
    es.addEventListener("done", function(ev){
      var rc = JSON.parse(ev.data).rc;
      el("phase").innerHTML = (rc === 0) ? '<span class="ok">done (exit 0)</span>' : '<span class="bad">exit ' + esc(rc) + '</span>';
      es.close();
      if (rc === 0) loadState();          // refresh the drops list after a successful run
    });
  }
  el("ingest").onclick = function(){
    var body = { force: el("force").checked, render_only: el("render_only").checked, workers: el("workers").value };
    el("log").textContent = ""; el("phase").textContent = "starting...";
    fetch("/api/ingest?t=" + encodeURIComponent(TOKEN), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Bobframes-Token": TOKEN },
      body: JSON.stringify(body)
    })
      .then(function(r){ if (r.status === 409) throw new Error("a job is already running"); if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function(j){ stream(j.job); })
      .catch(function(e){ el("phase").innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; });
  };
  loadState();
</script>
</body></html>
"""


# --- HTTP handler ------------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    """Serves the control page on ``/`` and the token-gated read-only ``/api/state``. POST job
    endpoints arrive in v028_2."""

    server_version = 'bobframes-ui'
    protocol_version = 'HTTP/1.1'

    def _has_valid_token(self, query: dict) -> bool:
        want = getattr(self.server, 'bobframes_token', '')
        got = (self.headers.get('X-Bobframes-Token')
               or (query.get('t', [''])[0] if query else ''))
        return bool(want) and bool(got) and secrets.compare_digest(str(got), str(want))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode('utf-8'), 'application/json; charset=utf-8')

    def do_GET(self) -> None:  # noqa: N802 (stdlib handler contract)
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path in ('/', '/index.html'):
            self._send(200, control_page().encode('utf-8'), 'text/html; charset=utf-8')
            return
        if path == '/api/state':
            if not self._has_valid_token(query):
                self._send_json({'error': 'forbidden'}, code=403)
                return
            root = getattr(self.server, 'bobframes_root', '.')
            self._send_json(panel_state(root))
            return
        if path.startswith('/api/stream/'):
            if not self._has_valid_token(query):           # EventSource can only auth via the query
                self._send_json({'error': 'forbidden'}, code=403)
                return
            job = self.server.bobframes_jobs.get(path[len('/api/stream/'):])  # type: ignore[attr-defined]
            if job is None:
                self.send_error(404, 'no such job')
                return
            self._stream(job)
            return
        self.send_error(404, 'not found')

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if not self._has_valid_token(query):
            self._send_json({'error': 'forbidden'}, code=403)
            return
        if path == '/api/ingest':
            self._start_job(jobs.build_run_argv(
                self.server.bobframes_root, **self._ingest_opts(self._read_json_body())))  # type: ignore[attr-defined]
            return
        self.send_error(404, 'not found')

    # --- job helpers ---------------------------------------------------------------------------

    def _read_json_body(self) -> dict:
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return {}

    @staticmethod
    def _ingest_opts(body: dict) -> dict:
        """Coerce the POST body into build_run_argv kwargs (defensive: never trust the client)."""
        workers = body.get('workers')
        return {
            'force': bool(body.get('force')),
            'render_only': bool(body.get('render_only')),
            'workers': int(workers) if str(workers or '').isdigit() else None,
            'pixel_grid': int(body['pixel_grid']) if str(body.get('pixel_grid') or '').isdigit() else 4,
        }

    def _start_job(self, argv: list[str]) -> None:
        registry = self.server.bobframes_jobs                # type: ignore[attr-defined]
        if any(j.running() for j in registry.values()):      # one job at a time (single-user panel)
            self._send_json({'error': 'busy'}, code=409)
            return
        job = jobs.Job(jobs.spawn(argv))
        jid = secrets.token_urlsafe(6)
        registry[jid] = job
        self._send_json({'job': jid}, code=202)

    def _stream(self, job: jobs.Job) -> None:
        """Server-Sent Events: relay the job's stdout (classified) until DONE; final `done` event
        carries the return code. No Content-Length (streamed); connection closes at end."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        cls = progress.Classifier()
        try:
            while True:
                try:
                    item = job.q.get(timeout=1.0)
                except queue.Empty:
                    self.wfile.write(b': keepalive\n\n')    # keep the slow 600s replay connection warm
                    self.wfile.flush()
                    continue
                if item is jobs.DONE:
                    self.wfile.write(f'event: done\ndata: {json.dumps({"rc": job.rc})}\n\n'.encode('utf-8'))
                    self.wfile.flush()
                    return
                self.wfile.write(f'data: {json.dumps(cls.feed(item))}\n\n'.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return                                            # client navigated away; the job keeps running

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        _logger.debug('ui: %s - %s', self.address_string(), fmt % args)


# --- server lifecycle --------------------------------------------------------------------------

def build_server(root: str, *, bind: str = '127.0.0.1', port: int = 8765) -> http.server.ThreadingHTTPServer:
    """Build (do not start) the panel server. Localhost-only bind (ADR-47). Mints a per-session token
    and stashes it + the abspath root on the server for the handlers. ``port=0`` binds an ephemeral
    port (used by tests; read it back from ``server_address[1]``)."""
    httpd = http.server.ThreadingHTTPServer((bind, port), _Handler)
    httpd.daemon_threads = True
    httpd.bobframes_root = os.path.abspath(root)         # type: ignore[attr-defined]
    httpd.bobframes_token = secrets.token_urlsafe(32)    # type: ignore[attr-defined]
    httpd.bobframes_jobs = {}                            # type: ignore[attr-defined]  id -> jobs.Job
    return httpd


def serve(root: str, *, bind: str = '127.0.0.1', port: int = 8765, open_browser: bool = True) -> int:
    """Start the panel and block until Ctrl+C. Returns a CLI exit code."""
    root = os.path.abspath(root)
    try:
        httpd = build_server(root, bind=bind, port=port)
    except OSError as e:
        _logger.error(f'ui: cannot bind {bind}:{port} ({e.strerror or e}); try a different --port')
        return errors.EXIT_FAILURE

    # The token rides in the opened URL; every /api/* call must present it (ADR-47).
    url = f'http://{bind}:{port}/?t={httpd.bobframes_token}'  # type: ignore[attr-defined]
    with httpd:
        _logger.info(f'ui: serving {root} at {url} (Ctrl+C to stop)')
        if open_browser:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return errors.EXIT_INTERRUPTED
        finally:
            httpd.shutdown()
    return errors.EXIT_OK
