"""v029_3: the honest ingest-time estimate -- the panel surfaces the per-capture replay budget so the
client can show `captures x replay_timeout_s` as a worst-case upper bound.

The server contract (replay_timeout_s in /api/state, read from the root's config) is pinned here; the
client-side calc + labelling is pinned by the browser populate-smoke (test_ui_browser).
"""
from __future__ import annotations

import json

from ._ui_util import get, running


def test_state_exposes_replay_budget(tmp_path):
    with running(str(tmp_path)) as (httpd, port):
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
        assert isinstance(s['replay_timeout_s'], (int, float)) and s['replay_timeout_s'] > 0
        assert s['replay_timeout_s'] == 600.0           # documented default (no override in this root)


def test_state_reflects_configured_replay_budget(tmp_path):
    """A `[pipeline] replay_timeout_s` override in the root's .bobframes.toml flows into the estimate,
    so the number is honest for a user who tuned the budget."""
    (tmp_path / '.bobframes.toml').write_text(
        'schema_version = 1\n[pipeline]\nreplay_timeout_s = 120.0\n', encoding='utf-8')
    with running(str(tmp_path)) as (httpd, port):
        s = json.load(get(port, '/api/state?t=' + httpd.bobframes_token))
        assert s['replay_timeout_s'] == 120.0
