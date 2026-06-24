"""v028_2: the subprocess job runner + SSE (mocked spawn -- no GPU/RenderDoc, the ADR-6 discipline).

`jobs.spawn` is monkeypatched with a fake process that emits a scripted stdout transcript; the test
asserts POST /api/ingest starts a job and GET /api/stream/<job> relays the classified lines + a final
`done` event carrying the return code.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from ..ui import jobs as _jobs
from ._ui_util import get, post, running

_SCRIPT = [
    "[10:00:00] pipeline: 1 drop(s); root=.",
    "[10:00:00]   replay: 2 captures (sequential)",
    "[10:00:10]     1: rc=0 10.0s",
    "[10:00:20]     2: rc=0 10.0s",
    "[10:00:21]   merge + parquetize",
    "[10:00:22] pipeline done: 1 drops processed",
]


class _FakeProc:
    def __init__(self, lines, rc=0):
        self.stdout = iter(lines)
        self.returncode = None
        self._rc = rc

    def wait(self):
        self.returncode = self._rc
        return self._rc

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15


def test_build_run_argv_mirrors_ingest():
    argv = _jobs.build_run_argv('/proj', force=True, render_only=False, workers=8, pixel_grid=2)
    assert '--root' in argv and '--force' in argv
    assert argv[argv.index('--workers') + 1] == '8'
    assert argv[argv.index('--pixel-grid') + 1] == '2'
    assert '--render-only' not in argv


def test_ingest_streams_stdout_and_return_code(tmp_path, monkeypatch):
    monkeypatch.setattr(_jobs, 'spawn', lambda argv: _FakeProc(list(_SCRIPT), rc=0))
    with running(str(tmp_path)) as (httpd, port):
        started = json.loads(post(port, '/api/ingest', httpd.bobframes_token, {'render_only': True}).read())
        assert 'job' in started
        stream = get(port, f"/api/stream/{started['job']}?t={httpd.bobframes_token}").read().decode('utf-8')
    assert 'replay: 2 captures' in stream                 # raw line relayed verbatim
    assert '"replay_total": 2' in stream and '"replay_done": 2' in stream
    assert 'event: done' in stream and '"rc": 0' in stream


def test_ingest_reports_nonzero_rc(tmp_path, monkeypatch):
    monkeypatch.setattr(_jobs, 'spawn', lambda argv: _FakeProc(['[10:00:00] boom'], rc=1))
    with running(str(tmp_path)) as (httpd, port):
        jid = json.loads(post(port, '/api/ingest', httpd.bobframes_token, {}).read())['job']
        stream = get(port, f'/api/stream/{jid}?t={httpd.bobframes_token}').read().decode('utf-8')
    assert 'event: done' in stream and '"rc": 1' in stream


def test_ingest_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/ingest', 'wrong-token', {})
        assert e.value.code == 403


def test_stream_unknown_job_404(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(port, f'/api/stream/nope?t={httpd.bobframes_token}')
        assert e.value.code == 404
