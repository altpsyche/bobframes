"""Static preview file server (extracted from ``cli._cmd_serve`` for reuse by ``bobframes ui``).

A stdlib ``http.server`` serving ``<root>`` read-only over localhost. ``make_server`` builds (does not
start) the server; ``serve_forever`` builds it and blocks until Ctrl+C -- the body of the ``serve`` verb.
The ``ui`` panel reuses ``make_server`` to run the static server in a background daemon thread alongside
the control panel (so a click-to-serve returns a URL instead of blocking the request handler).

No new dependency; behavior is identical to the prior inlined ``_cmd_serve`` (same ``socketserver``
TCPServer + ``SimpleHTTPRequestHandler(directory=root)`` + ``[HH:MM:SS]`` log line + exit codes).
"""
from __future__ import annotations

import functools
import http.server
import logging
import socketserver

log = logging.getLogger('bobframes')


def make_server(root: str, *, bind: str = '127.0.0.1', port: int = 8000) -> socketserver.TCPServer:
    """Build (do not start) a static file server over ``<root>``. ``port=0`` binds an ephemeral port
    (read it back from ``server.server_address[1]``); used by the panel's background serve."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    return socketserver.TCPServer((bind, port), handler)


def serve_forever(root: str, *, bind: str = '127.0.0.1', port: int = 8000) -> int:
    """Serve ``<root>`` and block until Ctrl+C. Returns a CLI exit code (0 clean, 4 interrupted)."""
    try:
        with make_server(root, bind=bind, port=port) as httpd:
            log.info(f'serving {root} at http://{bind}:{port} (Ctrl+C to stop)')
            httpd.serve_forever()
    except KeyboardInterrupt:
        return 4
    return 0
