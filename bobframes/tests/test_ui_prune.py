"""v029_8: the panel's job registry is bounded -- it otherwise grows one id->Job entry per job forever.

`jobs.prune_registry` drops the oldest FINISHED jobs past the cap and never removes a running one (an
in-flight SSE stream keeps its own Job reference, so a pruned entry never cuts a live stream).
"""
from __future__ import annotations

from ..ui import jobs as _jobs


class _FakeJob:
    def __init__(self, running):
        self._running = running

    def running(self):
        return self._running


def test_prune_bounds_size_and_keeps_most_recent():
    reg = {f'j{i}': _FakeJob(running=False) for i in range(30)}
    _jobs.prune_registry(reg, keep=20)
    assert len(reg) == 20
    assert 'j29' in reg and 'j10' in reg          # newest kept
    assert 'j0' not in reg and 'j9' not in reg     # oldest dropped


def test_prune_never_removes_a_running_job():
    reg = {'oldest_running': _FakeJob(running=True)}
    reg.update({f'j{i}': _FakeJob(running=False) for i in range(25)})
    _jobs.prune_registry(reg, keep=20)
    assert 'oldest_running' in reg                  # survives despite being the oldest entry
    assert len(reg) == 20                            # 19 newest finished + the 1 running


def test_prune_noop_under_cap():
    reg = {f'j{i}': _FakeJob(running=False) for i in range(5)}
    _jobs.prune_registry(reg, keep=20)
    assert len(reg) == 5
