"""v028_4: A/B comparison + accent theming + the opt-in capture-folder scaffold.

A/B and the accent re-render are streamed subprocess jobs mocked at the spawn seam (no GPU/RenderDoc --
ADR-6): `jobs.spawn` (render reuses `python -m bobframes.run`) and `jobs.spawn_cli` (`bobframes ab`)
are monkeypatched with a fake process. The run list backing the picker is asserted via `/api/state`
(`discovery.discover_drops` monkeypatched). Scaffold creates a real folder under a tmp root.
"""
from __future__ import annotations

import json
import os
import urllib.error

import pytest

from ..ui import jobs as _jobs
from ._ui_util import get, post, running


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


class _FakeRun:
    def __init__(self, key, label, date, n):
        self.key, self.label, self.date, self.n_captures = key, label, date, n


# --- argv builders ------------------------------------------------------------------------------

def test_build_render_argv_threads_accent():
    argv = _jobs.build_render_argv('/proj', accent='oklch(0.5 0.2 250)', accent_data='red')
    assert '--render-only' in argv
    assert argv[argv.index('--accent') + 1] == 'oklch(0.5 0.2 250)'
    assert argv[argv.index('--accent-data') + 1] == 'red'
    plain = _jobs.build_render_argv('/proj')
    assert '--accent' not in plain and '--accent-data' not in plain and '--render-only' in plain


def test_build_ab_argv_mirrors_ab_verb():
    argv = _jobs.build_ab_argv('/proj', baseline_label='r1', compare_label='r2',
                               baseline_date='2026-05-27', compare_date='2026-05-28')
    assert argv[0] == 'ab'
    assert argv[argv.index('--baseline-label') + 1] == 'r1'
    assert argv[argv.index('--compare-label') + 1] == 'r2'
    assert argv[argv.index('--baseline-date') + 1] == '2026-05-27'
    assert argv[argv.index('--compare-date') + 1] == '2026-05-28'
    bare = _jobs.build_ab_argv('/proj', baseline_label='r1', compare_label='r2')
    assert '--baseline-date' not in bare and '--compare-date' not in bare


# --- /api/render accent -------------------------------------------------------------------------

def test_render_threads_accent_into_spawn(tmp_path, monkeypatch):
    seen = {}

    def fake_spawn(argv):
        seen['argv'] = argv
        return _FakeProc(["[10:00:00] render-only done"])
    monkeypatch.setattr(_jobs, 'spawn', fake_spawn)
    with running(str(tmp_path)) as (httpd, port):
        jid = json.loads(post(port, '/api/render', httpd.bobframes_token,
                              {'accent': 'oklch(0.6 0.2 30)', 'accent_data': ''}).read())['job']
        stream = get(port, f'/api/stream/{jid}?t={httpd.bobframes_token}').read().decode('utf-8')
    assert '--render-only' in seen['argv']
    assert seen['argv'][seen['argv'].index('--accent') + 1] == 'oklch(0.6 0.2 30)'
    assert '--accent-data' not in seen['argv']            # blank field -> flag omitted
    assert '"rc": 0' in stream


# --- /api/ab ------------------------------------------------------------------------------------

def test_ab_spawns_cli_and_streams(tmp_path, monkeypatch):
    seen = {}

    def fake_spawn_cli(argv):
        seen['argv'] = argv
        return _FakeProc(["[10:00:00] a/b: 2026-05-27_r1 (2 captures) vs 2026-05-28_r2 (3 captures)"])
    monkeypatch.setattr(_jobs, 'spawn_cli', fake_spawn_cli)
    with running(str(tmp_path)) as (httpd, port):
        body = {'baseline_label': 'r1', 'baseline_date': '2026-05-27',
                'compare_label': 'r2', 'compare_date': '2026-05-28'}
        jid = json.loads(post(port, '/api/ab', httpd.bobframes_token, body).read())['job']
        stream = get(port, f'/api/stream/{jid}?t={httpd.bobframes_token}').read().decode('utf-8')
    assert seen['argv'][0] == 'ab'
    assert seen['argv'][seen['argv'].index('--baseline-label') + 1] == 'r1'
    assert seen['argv'][seen['argv'].index('--compare-label') + 1] == 'r2'
    assert 'a/b:' in stream and '"rc": 0' in stream


def test_ab_requires_both_runs(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/ab', httpd.bobframes_token, {'baseline_label': 'r1'})   # no compare
        assert e.value.code == 400


# --- /api/state runs (the picker source) --------------------------------------------------------

def test_state_lists_rendered_runs(tmp_path, monkeypatch):
    from ..reports import discovery as rdisc
    runs = [_FakeRun('2026-05-27_r1', 'r1', '2026-05-27', 2),
            _FakeRun('2026-05-28_r2', 'r2', '2026-05-28', 3)]
    monkeypatch.setattr(rdisc, 'discover_drops', lambda root: runs)
    with running(str(tmp_path)) as (httpd, port):
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
    assert [r['key'] for r in s['runs']] == ['2026-05-27_r1', '2026-05-28_r2']
    assert s['runs'][1]['n_captures'] == 3


def test_state_runs_empty_without_catalog(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
    assert s['runs'] == []                                 # no catalog yet -> no runs


# --- /api/scaffold ------------------------------------------------------------------------------

def test_scaffold_creates_convention_folder(tmp_path):
    root = str(tmp_path / 'proj')
    os.makedirs(root)
    with running(root) as (httpd, port):
        r = json.loads(post(port, '/api/scaffold', httpd.bobframes_token,
                            {'area': 'Town', 'date': '2026-06-24', 'label': 'r110600'}).read())
        assert r['created'] is True
        assert os.path.basename(r['path']) == '2026-06-24_r110600'
        assert os.path.isdir(os.path.join(root, 'Town', '2026-06-24_r110600'))
        # idempotent: a second call reports already-exists.
        again = json.loads(post(port, '/api/scaffold', httpd.bobframes_token,
                                {'area': 'Town', 'date': '2026-06-24', 'label': 'r110600'}).read())
        assert again['created'] is False


def test_scaffold_rejects_bad_date_and_traversal(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as bad_date:
            post(port, '/api/scaffold', httpd.bobframes_token, {'area': 'Town', 'date': 'June 24'})
        assert bad_date.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as traversal:
            post(port, '/api/scaffold', httpd.bobframes_token, {'area': '../escape', 'date': '2026-06-24'})
        assert traversal.value.code == 400


def test_ab_and_scaffold_require_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        for path in ('/api/ab', '/api/scaffold'):
            with pytest.raises(urllib.error.HTTPError) as e:
                post(port, path, 'wrong-token', {})
            assert e.value.code == 403, path
