"""Classify a `bobframes.run` stdout line into a structured progress event (v028_2).

The panel streams the verbs' raw stdout to the browser; this turns each `[HH:MM:SS] <message>` line
into ``{line, phase, replay_done, replay_total}`` so the client can draw a stage strip + a per-capture
replay bar WITHOUT parsing strings in JS. The raw line is always carried through verbatim (nothing
hidden -- ADR-23); if run.py rewords a log line the worst case is the phase strip stops advancing while
the raw log keeps scrolling. Lives server-side so it is unit-tested in pytest (no JS runtime).

Matches are substring/regex against the message, robust to the timestamp prefix and leading indent.
"""
from __future__ import annotations

import re

# Ordered (substring -> phase); the first match on a line wins. Mirrors the run.py _log() strings.
_MARKERS: tuple[tuple[str, str], ...] = (
    ('export:', 'export'),
    ('parse:', 'parse'),
    ('replay:', 'replay'),
    ('merge + parquetize', 'parquetize'),
    ('parquetize done', 'parquetize'),
    ('post-merge derives', 'derive'),
    ('derived tables', 'derive'),
    ('resource labels', 'derive'),
    ('rebuilding catalog', 'catalog'),
    ('global entities', 'catalog'),
    ('render-only:', 'render'),
    (': rendered', 'render'),
    ('done ->', 'render'),
    ('pipeline done', 'done'),
    ('render-only done', 'done'),
)

# Canonical phase order for a stage strip (display concern, exported for the client).
PHASES: tuple[str, ...] = ('export', 'parse', 'replay', 'parquetize', 'derive', 'render', 'catalog', 'done')

_REPLAY_TOTAL = re.compile(r'replay:\s*(\d+)\s+captures')


class Classifier:
    """Stateful per-job line classifier. ``feed(line)`` returns the event for that line."""

    def __init__(self) -> None:
        self.phase: str | None = None
        self.replay_total = 0
        self.replay_done = 0

    def feed(self, line: str) -> dict:
        for needle, phase in _MARKERS:
            if needle in line:
                self.phase = phase
                break
        m = _REPLAY_TOTAL.search(line)
        if m:
            self.replay_total = int(m.group(1))
        # A per-capture replay line carries `rc=` (normal, COMPLETE-on-crash, or FAILED) -> one tick.
        if self.phase == 'replay' and 'rc=' in line:
            self.replay_done += 1
        return {
            'line': line,
            'phase': self.phase,
            'replay_done': self.replay_done,
            'replay_total': self.replay_total,
        }
