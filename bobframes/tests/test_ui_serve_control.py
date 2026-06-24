"""v029_9: list + stop the panel's background static serve.

`/api/serve` starts ONE background static server (singleton). v029_9 adds GET /api/serve (status) and
POST /api/serve/stop (release the port so a re-serve rebinds a fresh one).
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from ._ui_util import get, post, running


def test_serve_status_start_and_stop(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        tok = httpd.bobframes_token
        assert json.load(get(port, '/api/serve?t=' + tok))['serving'] is None      # nothing yet
        started = json.loads(post(port, '/api/serve', tok, {}).read())
        assert started['url'].startswith('http://127.0.0.1:')
        status = json.load(get(port, '/api/serve?t=' + tok))['serving']             # now listed
        assert status and status['port'] == started['port']
        stopped = json.loads(post(port, '/api/serve/stop', tok, {}).read())         # stop releases it
        assert stopped['stopped'] is True
        assert json.load(get(port, '/api/serve?t=' + tok))['serving'] is None


def test_serve_stop_is_noop_when_idle(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        r = json.loads(post(port, '/api/serve/stop', httpd.bobframes_token, {}).read())
        assert r['stopped'] is False


def test_serve_status_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(port, '/api/serve')
        assert e.value.code == 403
