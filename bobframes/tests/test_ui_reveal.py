"""v029_6: 'reveal in folder' -- POST /api/reveal opens the output folder in the OS file explorer.

`kind=package` reveals the dir beside the project (where `package` writes the zip); otherwise the
project root. Windows-only (os.startfile); os.startfile is monkeypatched so the test runs anywhere.
"""
from __future__ import annotations

import json
import os
import urllib.error

import pytest

from ._ui_util import post, running


def _nc(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def test_reveal_package_opens_beside_project(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(os, 'startfile', lambda p: calls.append(p), raising=False)
    root = tmp_path / 'proj'
    root.mkdir()
    with running(str(root)) as (httpd, port):
        j = json.loads(post(port, '/api/reveal', httpd.bobframes_token, {'kind': 'package'}).read())
    assert j['ok'] is True
    assert len(calls) == 1 and _nc(calls[0]) == _nc(str(tmp_path))     # the zip lands beside the project


def test_reveal_default_opens_project_root(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(os, 'startfile', lambda p: calls.append(p), raising=False)
    with running(str(tmp_path)) as (httpd, port):
        post(port, '/api/reveal', httpd.bobframes_token, {})
    assert len(calls) == 1 and _nc(calls[0]) == _nc(str(tmp_path))


def test_reveal_non_windows_501(tmp_path, monkeypatch):
    monkeypatch.delattr(os, 'startfile', raising=False)               # simulate a non-Windows host
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/reveal', httpd.bobframes_token, {})
        assert e.value.code == 501


def test_reveal_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/reveal', 'wrong-token', {})
        assert e.value.code == 403
