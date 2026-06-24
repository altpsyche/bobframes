"""v029_4: the panel's progress + result regions carry aria-live, so a screen reader announces job
completion and action outcomes (a non-sighted QA/product user otherwise gets no feedback that a long
ingest finished). Structural check on the served page; the browser smoke confirms the attribute reaches
the live DOM.
"""
from __future__ import annotations

import re

from ..ui import server as _server

# Progress (phase) regions, result boxes, and the action status lines. The streaming log <pre>s are
# deliberately NOT aria-live -- announcing every log line would flood a screen reader.
_LIVE_REGIONS = ('phase', 'phase_share', 'phase_ab',          # job progress -> announces "done"/"failed"/"cancelled"
                 'share_result', 'ab_result',                 # results
                 'sc_msg', 'config_msg', 'root_msg', 'ab_hint')  # action outcomes


def test_progress_and_result_regions_are_aria_live():
    page = _server.control_page()
    for region in _LIVE_REGIONS:
        assert re.search(r'id="' + region + r'"[^>]*aria-live="polite"', page), \
            f'#{region} is missing aria-live="polite"'


def test_streaming_logs_are_not_aria_live():
    """The high-frequency log panes must NOT be aria-live (would spam the screen reader)."""
    page = _server.control_page()
    for log in ('log', 'log_share', 'log_ab'):
        assert not re.search(r'id="' + log + r'"[^>]*aria-live', page), f'#{log} should not be aria-live'
