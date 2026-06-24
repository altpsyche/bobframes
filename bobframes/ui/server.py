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
import secrets
import sys
import threading
import webbrowser
from urllib.parse import parse_qs, urlparse

from .. import errors

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
  fetch("/api/state?t=" + encodeURIComponent(TOKEN))
    .then(function(r){ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
    .then(render)
    .catch(function(e){
      el("root").innerHTML = '<span class="bad">Could not load state ('+esc(e.message)+'). Open the panel via the link printed in the terminal (it carries the session token).</span>';
    });
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
        self.send_error(404, 'not found')

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
