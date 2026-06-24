"""v028_1/8: end-to-end smoke -- the panel serves its control page, the externalized static assets, and
read-only state over HTTP."""
from __future__ import annotations

import json

from ..ui import server as _server
from ._ui_util import get, running


def test_root_page_links_assets_and_state_smoke(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        page = get(port, '/')
        assert page.getcode() == 200
        body = page.read().decode('utf-8')
        # The shell links the externalized client + styles (v028_8); the fetch('/api/state') call now
        # lives in panel.js, not in the page HTML.
        assert 'bobframes ui' in body
        assert '<script src="/panel.js"></script>' in body
        assert '<link rel="stylesheet" href="/panel.css">' in body
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
        assert {'root', 'tools', 'drops', 'runs', 'convention', 'platform', 'windows'} <= set(s)


def test_static_assets_serve_without_token(tmp_path):
    """The static client + styles are open (they hold no secret and carry no state; the token is in the
    page URL and panel.js reads it from there). Content-types must be right or the browser ignores them."""
    with running(str(tmp_path)) as (httpd, port):
        js = get(port, '/panel.js')
        assert js.getcode() == 200 and 'javascript' in js.headers.get('Content-Type', '')
        assert 'loadState' in js.read().decode('utf-8')          # the real client, not an error page
        css = get(port, '/panel.css')
        assert css.getcode() == 200 and 'text/css' in css.headers.get('Content-Type', '')


def test_no_js_embedded_in_the_python_page_string():
    """v028_8 retires the v028_2 failure mode structurally: the served shell embeds NO JavaScript (it is
    HTML-only + a <script src>), so a Python-string escape can no longer split a JS literal. The real
    parse gate is `node --check` on panel.js (test_ui_js_parses). As a node-absent fallback, assert the
    JS that v028_2 broke survives intact in the asset (the two-char ``"\\n"`` escape)."""
    page = _server.control_page()
    assert '<script>' not in page                                # no inline script body, only <script src>
    assert '<script src="/panel.js"></script>' in page
    js = _server.panel_js()
    assert r'd.line + "\n"' in js                                 # the exact literal v028_2 turned into a newline
