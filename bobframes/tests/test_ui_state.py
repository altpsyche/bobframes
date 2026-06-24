"""v028_1: the read-only `GET /api/state` (tools + drops) the control page renders."""
from __future__ import annotations

import json

from ._ui_util import get, make_capture_root, running


def test_state_lists_drops_for_the_capture_root(tmp_path):
    root = make_capture_root(tmp_path)
    with running(root) as (httpd, port):
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
    assert s['root'].replace('\\', '/').endswith('proj')
    assert s['convention'] == '<Area>/<YYYY-MM-DD[_label]>/*.rdc'
    areas = {d['area'] for d in s['drops']}
    assert areas == {'Town', 'Bay'}                          # _data-style noise dirs excluded by discovery
    town = next(d for d in s['drops'] if d['area'] == 'Town')
    assert (town['date'], town['label'], town['n_captures']) == ('2026-05-28', 'new', 3)
    # Two tools resolved (found-ness depends on the host; structure is the contract).
    assert isinstance(s['tools'], list) and {t['name'] for t in s['tools']} == {'renderdoccmd', 'qrenderdoc'}


def test_state_missing_root_reports_null_drops(tmp_path):
    missing = str(tmp_path / 'nope')
    with running(missing) as (httpd, port):
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
    assert s['drops'] is None


def test_state_empty_root_has_no_drops(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
    assert s['drops'] == []
