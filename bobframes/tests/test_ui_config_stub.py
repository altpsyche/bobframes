"""v029_1: Write a starter .bobframes.toml from the UI -- POST /api/config/stub.

When no RenderDoc tool resolves, the panel is a first-run dead end. This wires `config.write_config_stub`
to a button so a non-terminal user gets a commented config to edit. Idempotent (no overwrite).
"""
from __future__ import annotations

import json
import os
import urllib.error

import pytest

from ._ui_util import post, running


def test_config_stub_writes_then_idempotent(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        r1 = json.loads(post(port, '/api/config/stub', httpd.bobframes_token, {}).read())
        assert r1['written'] is True
        assert r1['path'].endswith('.bobframes.toml') and os.path.exists(r1['path'])
        assert '[tools]' in open(r1['path'], encoding='utf-8').read()   # the starter the user edits
        # second call must NOT overwrite (idempotent)
        r2 = json.loads(post(port, '/api/config/stub', httpd.bobframes_token, {}).read())
        assert r2['written'] is False and r2['path'] == r1['path']


def test_config_stub_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/config/stub', 'wrong-token', {})
        assert e.value.code == 403
