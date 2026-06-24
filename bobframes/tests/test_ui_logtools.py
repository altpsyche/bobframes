"""v029_7: each job log pane carries Copy + Download controls (pure client JS; no server change).

Structural CI gate (the `browser` smoke is opt-in, so assert the controls are in the served page here);
the in-browser wiring is confirmed by test_ui_browser.
"""
from __future__ import annotations

from ..ui import server as _server


def test_every_log_pane_has_copy_and_download_buttons():
    page = _server.control_page()
    for bid in ('copy_run', 'dl_run', 'copy_share', 'dl_share', 'copy_ab', 'dl_ab'):
        assert f'id="{bid}"' in page, f'missing log control #{bid}'
    # the client JS implements both actions
    js = _server.panel_js()
    assert 'navigator.clipboard' in js and 'URL.createObjectURL' in js
