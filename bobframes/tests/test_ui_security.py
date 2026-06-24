"""v028_1: the `bobframes ui` security guard (ADR-47).

POST endpoints (v028_2+) spawn subprocesses, so `/api/*` is gated by a per-session token and the
server binds localhost only. These tests lock the token contract before any action endpoint exists.
"""
from __future__ import annotations

import urllib.error

import pytest

from ._ui_util import get, running


def test_state_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as no_tok:
            get(port, '/api/state')
        assert no_tok.value.code == 403
        with pytest.raises(urllib.error.HTTPError) as bad_tok:
            get(port, '/api/state?t=wrong')
        assert bad_tok.value.code == 403
        ok = get(port, '/api/state?t=' + httpd.bobframes_token)
        assert ok.getcode() == 200


def test_token_accepted_via_header(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        ok = get(port, '/api/state', headers={'X-Bobframes-Token': httpd.bobframes_token})
        assert ok.getcode() == 200


def test_control_page_is_viewable_without_token(tmp_path):
    # The page itself is open (it then fetches state with the token carried in its own URL); only
    # the /api/* surface is gated.
    with running(str(tmp_path)) as (httpd, port):
        r = get(port, '/')
        assert r.getcode() == 200
        assert b'bobframes ui' in r.read()


def test_server_binds_localhost(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        assert httpd.server_address[0] == '127.0.0.1'
