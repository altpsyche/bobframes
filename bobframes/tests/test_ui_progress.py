"""v028_2: the stdout-line progress classifier (the highest-value lock on the SSE contract).

Fed a representative `bobframes.run` transcript (the [HH:MM:SS]-prefixed, indented lines the panel
streams), the Classifier must track the phase + the per-capture replay k/n. If run.py rewords a line
the worst case is a phase stops advancing (the raw log still scrolls) -- this test catches that.
"""
from __future__ import annotations

from ..ui.progress import Classifier

# A faithful slice of run.py's _log() output (with the handler's [HH:MM:SS] prefix + indent).
_TRANSCRIPT = [
    "[10:00:00] pipeline: 1 drop(s); root=.",
    "[10:00:00] == drop: Town / 2026-05-28_new (3 captures) ==",
    "[10:00:00]   export: 3/3 captures need export (workers=4)",
    "[10:00:05]   export done in 5.0s",
    "[10:00:05]   parse: 3 captures (workers=4)",
    "[10:00:07]   parse done in 2.0s",
    "[10:00:07]   replay: 3 captures (sequential)",
    "[10:00:20]     1: rc=0 13.0s",
    "[10:00:33]     2: rc=0 13.0s",
    "[10:00:46]     10: rc=0 but replay COMPLETE (qrenderdoc crashed on shutdown); ...",
    "[10:00:46]   merge + parquetize",
    "[10:00:47]   parquetize done in 1.0s (1234 rows)",
    "[10:00:47]   post-merge derives applied (0.5s)",
    "[10:00:48]   done -> _reports/Town/index.html",
    "[10:00:48] rebuilding catalog",
    "[10:00:48]   catalog: 1 drops, 3 captures",
    "[10:00:49] pipeline done: 1 drops processed",
]


def _run():
    c = Classifier()
    return c, [c.feed(line) for line in _TRANSCRIPT]


def test_phase_transitions():
    c, events = _run()
    by = {line: ev['phase'] for line, ev in zip(_TRANSCRIPT, events)}
    assert by["[10:00:00]   export: 3/3 captures need export (workers=4)"] == 'export'
    assert by["[10:00:05]   parse: 3 captures (workers=4)"] == 'parse'
    assert by["[10:00:07]   replay: 3 captures (sequential)"] == 'replay'
    assert by["[10:00:46]   merge + parquetize"] == 'parquetize'
    assert by["[10:00:47]   post-merge derives applied (0.5s)"] == 'derive'
    assert by["[10:00:48]   done -> _reports/Town/index.html"] == 'render'
    assert by["[10:00:48] rebuilding catalog"] == 'catalog'
    assert c.phase == 'done'


def test_replay_ticks_count_each_capture():
    c, events = _run()
    # total parsed from the "replay: N captures" line
    assert c.replay_total == 3
    # exactly one tick per capture line (incl. the COMPLETE-on-crash variant), none before replay
    assert c.replay_done == 3
    replay_line = next(ev for ln, ev in zip(_TRANSCRIPT, events) if ln.endswith("(sequential)"))
    assert replay_line['replay_done'] == 0 and replay_line['replay_total'] == 3


def test_line_is_carried_verbatim():
    c = Classifier()
    raw = "[10:00:00]   export: 3/3 captures need export (workers=4)"
    assert c.feed(raw)['line'] == raw
