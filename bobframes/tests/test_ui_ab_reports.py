"""v029_5: list every report in an A/B pair so the panel links them all, not just summary.html.

GET /api/ab/reports?base=&cmp= enumerates `_reports/ab/<base>_vs_<cmp>/*.html`; each `rel` is consumed
by the traversal-guarded /api/open. Run keys form a directory name, so they are guarded against
separators / `..`.
"""
from __future__ import annotations

import json
import urllib.error

import pytest

from ._ui_util import get, running


def _make_pair(root, base, cmp_, names):
    d = root / '_reports' / 'ab' / f'{base}_vs_{cmp_}'
    d.mkdir(parents=True)
    for n in names:
        (d / n).write_text('x', encoding='utf-8')
    return d


def test_ab_reports_lists_every_html_in_the_pair(tmp_path):
    _make_pair(tmp_path, 'A', 'B', ('summary.html', 'pass_gpu.html', 'overdraw.html', 'notes.txt'))
    with running(str(tmp_path)) as (httpd, port):
        j = json.load(get(port, '/api/ab/reports?base=A&cmp=B&t=' + httpd.bobframes_token))
    names = [r['name'] for r in j['reports']]
    assert names == ['overdraw', 'pass_gpu', 'summary']             # sorted, .html stripped, .txt excluded
    assert all(r['rel'] == f"_reports/ab/A_vs_B/{r['name']}.html" for r in j['reports'])


def test_ab_reports_unknown_pair_is_empty(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        j = json.load(get(port, '/api/ab/reports?base=X&cmp=Y&t=' + httpd.bobframes_token))
        assert j['reports'] == []


def test_ab_reports_requires_token(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(port, '/api/ab/reports?base=A&cmp=B')
        assert e.value.code == 403


def test_ab_reports_rejects_traversal_keys(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(port, '/api/ab/reports?base=..&cmp=B&t=' + httpd.bobframes_token)
        assert e.value.code == 400
