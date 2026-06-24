"""v028_1: end-to-end smoke -- the panel serves its control page and read-only state over HTTP."""
from __future__ import annotations

import json

from ._ui_util import get, running


def test_root_page_and_state_smoke(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        page = get(port, '/')
        assert page.getcode() == 200
        body = page.read().decode('utf-8')
        assert 'bobframes ui' in body and '/api/state' in body   # the page knows to fetch state
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
        assert {'root', 'tools', 'drops', 'convention', 'platform', 'windows'} <= set(s)
