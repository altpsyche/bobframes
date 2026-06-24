"""Shared helpers for the `bobframes ui` panel tests (v028_1).

Starts the stdlib panel server on an ephemeral port in a daemon thread and hits it with `urllib`,
so the tests exercise the real HTTP surface (token gating, JSON shape) without a browser or GPU.
"""
from __future__ import annotations

import contextlib
import os
import threading
import urllib.request

from ..ui import server as _server


def make_capture_root(tmp_path) -> str:
    """A tmp project root with the `<Area>/<YYYY-MM-DD[_label]>/*.rdc` convention (mirrors
    test_discovery): Town has the newest dated drop with 3 captures; Bay a single undated-label drop."""
    root = str(tmp_path / 'proj')
    layout = (('Town', '2026-05-27_old', ('1',)),
              ('Town', '2026-05-28_new', ('1', '2', '10')),
              ('Bay', '2026-01-01', ('cap',)))
    for area, key, caps in layout:
        for cap in caps:
            p = os.path.join(root, area, key, f'{cap}.rdc')
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'w', encoding='utf-8').close()
    return root


@contextlib.contextmanager
def running(root: str):
    """Run the panel server on an ephemeral port; yield (httpd, port)."""
    httpd = _server.build_server(root, port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd, httpd.server_address[1]
    finally:
        httpd.shutdown()
        t.join(timeout=5)


def get(port: int, path: str, headers: dict | None = None):
    """GET http://127.0.0.1:<port><path>; returns the response (raises HTTPError on >=400)."""
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', headers=headers or {})
    return urllib.request.urlopen(req, timeout=5)
