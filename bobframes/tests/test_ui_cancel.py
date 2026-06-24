"""v029_0: Cancel a running job from the UI -- POST /api/cancel/<job> wires jobs.Job.cancel().

A 600s/capture ingest is otherwise unstoppable from the panel. The fake process blocks until terminated
(mirrors the test_ui_jobs mocked-spawn discipline -- no GPU/RenderDoc); the test starts a job, cancels
it over HTTP, and asserts the stream's terminal event carries ``cancelled`` (so the panel reads
'cancelled', not 'failed').
"""
from __future__ import annotations

import json
import threading
import urllib.error

import pytest

from ..ui import jobs as _jobs
from ._ui_util import get, post, running


class _BlockingProc:
    """A fake spawned process that emits one line then blocks until terminate() -- so the job stays
    'running' and can be cancelled. terminate() unblocks stdout (-> EOF) and yields a non-zero rc."""

    def __init__(self):
        self._stop = threading.Event()
        self.returncode = None
        self.stdout = self._gen()

    def _gen(self):
        yield "[10:00:00] pipeline: replaying captures (this is slow)"
        self._stop.wait(timeout=10)        # block until cancelled (safety timeout so a test can't hang)

    def wait(self):
        self.returncode = -15
        return self.returncode

    def poll(self):
        return self.returncode             # None while running -> Job.running() True -> cancel() acts

    def terminate(self):
        self._stop.set()


def test_cancel_terminates_running_job_and_marks_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(_jobs, 'spawn', lambda argv: _BlockingProc())
    with running(str(tmp_path)) as (httpd, port):
        jid = json.loads(post(port, '/api/ingest', httpd.bobframes_token, {}).read())['job']
        r = json.loads(post(port, f'/api/cancel/{jid}', httpd.bobframes_token, {}).read())
        assert r['cancelled'] is True
        # the stream drains the queued line + the terminal 'done' event (cancelled, non-zero rc)
        stream = get(port, f'/api/stream/{jid}?t={httpd.bobframes_token}').read().decode('utf-8')
    assert 'event: done' in stream
    assert '"cancelled": true' in stream
    # and the underlying job really terminated (rc set, no longer running)
    assert httpd.bobframes_jobs[jid].running() is False


def test_cancel_unknown_job_404(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/cancel/nope', httpd.bobframes_token, {})
        assert e.value.code == 404


def test_cancel_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/cancel/whatever', 'wrong-token', {})
        assert e.value.code == 403
