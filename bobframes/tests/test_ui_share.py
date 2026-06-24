"""v028_3: the share & explore actions -- render / package (streamed jobs) + open / serve (one-shot).

Heavy work is mocked at the spawn seam (no GPU/RenderDoc -- the ADR-6 discipline): `jobs.spawn`
(render reuses `python -m bobframes.run`) and `jobs.spawn_cli` (`bobframes package`) are monkeypatched
with a fake process emitting a scripted transcript. `open` is verified by capturing `webbrowser.open`;
`serve` starts a REAL background static server and is fetched over http to prove it serves the root.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from ..ui import jobs as _jobs
from ..ui import server as _server
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


def test_build_package_argv_mirrors_package_verb():
    argv = _jobs.build_package_argv('/proj', light=True, redact=True)
    assert argv[0] == 'package'              # the cli verb, positional <root> (not --root)
    assert '--light' in argv and '--redact' in argv
    plain = _jobs.build_package_argv('/proj')
    assert '--light' not in plain and '--redact' not in plain


def test_render_spawns_render_only_and_streams(tmp_path, monkeypatch):
    seen = {}
    script = ["[10:00:00] render-only: re-rendering 1 drop(s) from existing parquet",
              "[10:00:01] render-only done"]

    def fake_spawn(argv):
        seen['argv'] = argv
        return _FakeProc(script)
    monkeypatch.setattr(_jobs, 'spawn', fake_spawn)
    with running(str(tmp_path)) as (httpd, port):
        jid = json.loads(post(port, '/api/render', httpd.bobframes_token, {}).read())['job']
        stream = get(port, f'/api/stream/{jid}?t={httpd.bobframes_token}').read().decode('utf-8')
    assert '--render-only' in seen['argv'] and '--force' not in seen['argv']
    assert 'render-only done' in stream
    assert 'event: done' in stream and '"rc": 0' in stream


def test_package_spawns_cli_with_toggles_and_streams(tmp_path, monkeypatch):
    seen = {}
    script = ["[10:00:00] packaged 12 files, 4096 bytes; zip /out/proj-2026-report.zip"]

    def fake_spawn_cli(argv):
        seen['argv'] = argv
        return _FakeProc(script)
    monkeypatch.setattr(_jobs, 'spawn_cli', fake_spawn_cli)
    with running(str(tmp_path)) as (httpd, port):
        jid = json.loads(post(port, '/api/package', httpd.bobframes_token,
                              {'light': True, 'redact': False}).read())['job']
        stream = get(port, f'/api/stream/{jid}?t={httpd.bobframes_token}').read().decode('utf-8')
    assert seen['argv'][0] == 'package' and '--light' in seen['argv'] and '--redact' not in seen['argv']
    assert 'packaged 12 files' in stream and '"rc": 0' in stream


def test_open_calls_webbrowser_when_report_exists(tmp_path, monkeypatch):
    (tmp_path / 'index.html').write_text('<html></html>', encoding='utf-8')
    opened = {}
    monkeypatch.setattr(_server.webbrowser, 'open', lambda url: opened.setdefault('url', url))
    with running(str(tmp_path)) as (httpd, port):
        r = json.loads(post(port, '/api/open', httpd.bobframes_token, {}).read())
    assert r['ok'] is True
    assert opened['url'].endswith('index.html')


def test_open_409_when_no_report(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/open', httpd.bobframes_token, {})
        assert e.value.code == 409


def test_open_relative_path_opens_ab_page(tmp_path, monkeypatch):
    # The A/B card opens the pair's self-contained summary via a relative path under root.
    pair = '2026-06-11_rA_vs_2026-06-15_rB'
    page = tmp_path / '_reports' / 'ab' / pair / 'summary.html'
    page.parent.mkdir(parents=True)
    page.write_text('<html></html>', encoding='utf-8')
    opened = {}
    monkeypatch.setattr(_server.webbrowser, 'open', lambda url: opened.setdefault('url', url))
    rel = f'_reports/ab/{pair}/summary.html'
    with running(str(tmp_path)) as (httpd, port):
        r = json.loads(post(port, '/api/open', httpd.bobframes_token, {'path': rel}).read())
    assert r['ok'] is True
    assert opened['url'].replace('\\', '/').endswith(rel)


def test_open_rejects_path_traversal(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            post(port, '/api/open', httpd.bobframes_token, {'path': '../../Windows/System32/x.html'})
        assert e.value.code == 400


def test_serve_starts_a_background_static_server(tmp_path):
    (tmp_path / 'index.html').write_text('<h1>served root</h1>', encoding='utf-8')
    with running(str(tmp_path)) as (httpd, port):
        info = json.loads(post(port, '/api/serve', httpd.bobframes_token, {}).read())
        assert info['port'] and info['url'].startswith('http://127.0.0.1:')
        body = urllib.request.urlopen(info['url'], timeout=5).read().decode('utf-8')
        assert 'served root' in body                       # the static server really serves <root>
        # idempotent: a second call returns the same already-running server.
        again = json.loads(post(port, '/api/serve', httpd.bobframes_token, {}).read())
        assert again == info


def test_share_actions_require_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        for path in ('/api/render', '/api/package', '/api/open', '/api/serve'):
            with pytest.raises(urllib.error.HTTPError) as e:
                post(port, path, 'wrong-token', {})
            assert e.value.code == 403, path
