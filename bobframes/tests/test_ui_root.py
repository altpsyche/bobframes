"""v029_2: repoint the panel at another folder without relaunching -- POST /api/root.

Lets a non-terminal user switch capture folders from the page instead of restarting `bobframes ui` from
a terminal. Validates the path is an existing directory; returns fresh state so the client re-renders.
"""
from __future__ import annotations

import json
import os
import urllib.error

import pytest

from ._ui_util import get, make_capture_root, post, running


def _nc(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def test_set_root_repoints_and_returns_fresh_state(tmp_path):
    start = tmp_path / 'start'
    start.mkdir()
    proj = make_capture_root(tmp_path)                  # Town + Bay drops
    with running(str(start)) as (httpd, port):
        s0 = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
        assert s0['drops'] == []                        # start root has no captures
        s1 = json.loads(post(port, '/api/root', httpd.bobframes_token, {'path': proj}).read())
        assert _nc(s1['root']) == _nc(proj)
        assert any(d['area'] == 'Town' for d in s1['drops'])
        # the server's active root really moved -- a fresh /api/state reflects it
        s2 = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
        assert _nc(s2['root']) == _nc(proj) and any(d['area'] == 'Bay' for d in s2['drops'])


def test_set_root_rejects_non_directory(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/root', httpd.bobframes_token, {'path': str(tmp_path / 'does_not_exist')})
        assert e.value.code == 400


def test_set_root_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/root', 'wrong-token', {'path': str(tmp_path)})
        assert e.value.code == 403
