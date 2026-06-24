"""v029_11: the panel serves a favicon (GET /favicon.ico -> 200) and links it, so the tab isn't a
broken icon and the console has no favicon 404."""
from __future__ import annotations

from ..ui import server as _server
from ._ui_util import get, running


def test_favicon_is_served(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        r = get(port, '/favicon.ico')
        assert r.getcode() == 200
        assert 'svg' in r.headers.get('Content-Type', '')
        assert b'<svg' in r.read()


def test_page_links_favicon():
    assert 'rel="icon"' in _server.control_page() and '/favicon.ico' in _server.control_page()
