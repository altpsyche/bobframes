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


def build_render_argv(root: str, *, accent: str | None = None,
                      accent_data: str | None = None) -> list[str]:
    """The argv for `python -m bobframes.run --render-only` (mirrors cli._cmd_render -- re-generate
    reports from existing parquet, no GPU/replay). The optional one-shot accent / accent-data overrides
    (ADR-45) re-hue the chrome without a config edit; run.py accepts both directly."""
    argv = ['--root', os.path.abspath(root), '--render-only']
    if accent:
        argv += ['--accent', accent]
    if accent_data:
        argv += ['--accent-data', accent_data]
    return argv


def build_package_argv(root: str, *, light: bool = False, redact: bool = False) -> list[str]:
    """The argv for `python -m bobframes.cli package <root>` (mirrors cli._cmd_package). `root` is the
    verb's positional argument (every bobframes verb takes <root> positionally, not as --root)."""
    argv = ['package', os.path.abspath(root)]
    if light:
        argv += ['--light']
    if redact:
        argv += ['--redact']
    return argv


def build_ab_argv(root: str, *, baseline_label: str, compare_label: str,
                  baseline_date: str | None = None, compare_date: str | None = None) -> list[str]:
    """The argv for `python -m bobframes.cli ab <root>` (mirrors cli._cmd_ab): every report for one
    (baseline, compare) drop pair. Labels are required; the dates disambiguate a label reused across
    runs (base.resolve_drop_set matches by label and/or date)."""
    argv = ['ab', os.path.abspath(root),
            '--baseline-label', baseline_label, '--compare-label', compare_label]
    if baseline_date:
        argv += ['--baseline-date', baseline_date]
    if compare_date:
        argv += ['--compare-date', compare_date]
    return argv


def spawn(argv: list[str]) -> subprocess.Popen:
    """Spawn `python -m bobframes.run <argv>` with merged stdout/stderr as text. Monkeypatched in tests."""
    return subprocess.Popen(
        [sys.executable, '-m', 'bobframes.run', *argv],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )


def spawn_cli(argv: list[str]) -> subprocess.Popen:
    """Spawn `python -m bobframes.cli <argv>` (the verbs that aren't run.py: e.g. `package`), merged
    text stdout. The separate seam tests monkeypatch for the non-ingest jobs."""
    return subprocess.Popen(
        [sys.executable, '-m', 'bobframes.cli', *argv],
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
        self.cancelled = False        # set by cancel() so the stream's terminal event reads 'cancelled'
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
        """Terminate the spawned verb process (the v029_0 Cancel button). Marks the job cancelled so the
        stream's terminal event reads 'cancelled', not 'failed'. Only the spawned process is terminated;
        deeper replay-grandchild cleanup is run.py's concern (R-4/ADR-4), out of the panel's scope."""
        if self.proc.poll() is None:
            self.cancelled = True
            self.proc.terminate()
