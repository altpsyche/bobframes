"""Subprocess job runner for the panel (v028_2, ADR-47).

Heavy work is run by SPAWNING the existing verbs as subprocesses (the `cli._render_watch` precedent),
never by calling `run.main` in-process: `run.main` mutates `os.environ` and the `config._ACTIVE`
singleton, and a qrenderdoc native fault must not crash the panel. A daemon thread pumps the child's
stdout (line by line) into a queue the SSE handler drains; a `DONE` sentinel carries the end-of-stream,
with the return code on the Job.

`spawn()` is the single seam tests monkeypatch with a fake process (no GPU/RenderDoc on CI).
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading

DONE = object()  # queue sentinel: the child closed stdout and exited (Job.rc is then set)


def build_run_argv(root: str, *, force: bool = False, render_only: bool = False,
                   workers: int | None = None, pixel_grid: int = 4) -> list[str]:
    """The argv for `python -m bobframes.run` (mirrors cli._cmd_ingest). Omitting --workers lets run.py
    pick its own default."""
    argv = ['--root', os.path.abspath(root)]
    if force:
        argv += ['--force']
    if render_only:
        argv += ['--render-only']
    if workers:
        argv += ['--workers', str(int(workers))]
    argv += ['--pixel-grid', str(int(pixel_grid))]
    return argv


def spawn(argv: list[str]) -> subprocess.Popen:
    """Spawn `python -m bobframes.run <argv>` with merged stdout/stderr as text. Monkeypatched in tests."""
    return subprocess.Popen(
        [sys.executable, '-m', 'bobframes.run', *argv],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )


class Job:
    """Wraps a spawned process: pumps its stdout into ``.q`` (one line per item, then ``DONE``) and
    records ``.rc`` (the return code) when it exits."""

    def __init__(self, proc: subprocess.Popen) -> None:
        self.proc = proc
        self.q: queue.Queue = queue.Queue()
        self.rc: int | None = None
        self._t = threading.Thread(target=self._pump, daemon=True)
        self._t.start()

    def _pump(self) -> None:
        try:
            if self.proc.stdout is not None:
                for line in self.proc.stdout:
                    self.q.put(line.rstrip('\n'))
        finally:
            self.rc = self.proc.wait()
            self.q.put(DONE)

    def running(self) -> bool:
        return self.rc is None and self.proc.poll() is None

    def cancel(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
