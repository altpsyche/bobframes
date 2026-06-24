"""The ``bobframes ui`` server (ADR-47).

v028_0 is the skeleton: a ``ThreadingHTTPServer`` bound to ``127.0.0.1`` that serves a placeholder
page and starts/stops cleanly (so the rest of the panel -- the control page, the read-only ``/api/state``
query, the per-session security token, and the subprocess job + SSE runner -- can land on a working
spine in v028_1..-5). Threading so an in-flight stream and concurrent control requests can coexist later.

Exit codes mirror the CLI (errors.py / ARCHITECTURE §4): 0 clean stop, 1 port unavailable, 4 Ctrl+C.
"""
from __future__ import annotations

import http.server
import logging
import os
import threading
import webbrowser

from .. import errors

_logger = logging.getLogger('bobframes')

# v028_0 placeholder. v028_1 replaces this with the generated control page (server-rendered HTML +
# vanilla JS, on-brand via reports.chrome.design_tokens_css()). ASCII-only; no framework, no build step.
_PLACEHOLDER_PAGE = (
    "<!doctype html>\n"
    "<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
    "<title>bobframes ui</title>\n"
    "<style>body{font:15px/1.5 system-ui,sans-serif;max-width:42rem;margin:4rem auto;padding:0 1rem;"
    "color:#1a1a1a}code{background:#f0f0f0;padding:.1rem .3rem;border-radius:3px}</style>\n"
    "</head><body>\n"
    "<h1>bobframes ui</h1>\n"
    "<p>The local control panel is up. This is the v0.2.8 skeleton -- the guided "
    "ingest / generate / package flow lands in the following commits.</p>\n"
    "<p>Drive the pipeline from the terminal meanwhile: <code>bobframes ingest .</code></p>\n"
    "</body></html>\n"
)


class _Handler(http.server.BaseHTTPRequestHandler):
    """Serves the placeholder on ``/`` (and ``/index.html``); 404 otherwise. The read-only state
    API and POST job endpoints are added in later commits."""

    server_version = 'bobframes-ui'

    def do_GET(self) -> None:  # noqa: N802 (stdlib handler contract)
        if self.path in ('/', '/index.html'):
            body = _PLACEHOLDER_PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404, 'not found')

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        # Route request logging through the 'bobframes' logger at DEBUG so it does not scribble on
        # stderr by default; --verbose surfaces it.
        _logger.debug('ui: %s - %s', self.address_string(), fmt % args)


def build_server(root: str, *, bind: str = '127.0.0.1', port: int = 8765) -> http.server.ThreadingHTTPServer:
    """Build (do not start) the panel server. Bound to localhost only (ADR-47): the panel will spawn
    subprocesses on POST in later commits, so it must never listen on a public interface. ``root`` is
    stored on the server for the handlers to read."""
    httpd = http.server.ThreadingHTTPServer((bind, port), _Handler)
    httpd.daemon_threads = True
    httpd.bobframes_root = os.path.abspath(root)  # type: ignore[attr-defined]
    return httpd


def serve(root: str, *, bind: str = '127.0.0.1', port: int = 8765, open_browser: bool = True) -> int:
    """Start the panel and block until Ctrl+C. Returns a CLI exit code."""
    root = os.path.abspath(root)
    try:
        httpd = build_server(root, bind=bind, port=port)
    except OSError as e:
        _logger.error(f'ui: cannot bind {bind}:{port} ({e.strerror or e}); try a different --port')
        return errors.EXIT_FAILURE

    url = f'http://{bind}:{port}/'
    with httpd:
        _logger.info(f'ui: serving {root} at {url} (Ctrl+C to stop)')
        if open_browser:
            # Open after the loop is ready; a daemon timer keeps serve_forever() the blocking call.
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return errors.EXIT_INTERRUPTED
        finally:
            httpd.shutdown()
    return errors.EXIT_OK
