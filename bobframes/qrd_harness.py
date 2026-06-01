"""Launch qrenderdoc.exe --python <script> with payload args via env.

qrenderdoc swallows positional argv after the script path (treats them as
captures to open) so we pass arguments via the RDC_INSIDE_ARGS env var,
joined by \\x1f (unit separator).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from . import config

_SEP = '\x1f'


def _kill_tree(pid: int) -> None:
    """Kill a process AND its descendants. qrenderdoc spawns GPU/replay
    grandchildren that survive a bare child kill and keep file locks held for
    the next run (R-4, ADR-4); `subprocess` only reaps the direct child. Uses
    Windows `taskkill /T /F`. Best-effort — never raises."""
    try:
        subprocess.run(
            ['taskkill', '/T', '/F', '/PID', str(pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
        )
    except Exception:
        pass


def find_qrenderdoc() -> str:
    """Resolve qrenderdoc.exe (delegates to config.resolve_tool; raises ToolNotFound)."""
    return config.resolve_tool('qrenderdoc')


def run(
    script_path: str,
    payload_args: list[str],
    log_path: str | None = None,
    timeout_s: float = 600.0,
) -> tuple[int, float]:
    """Launch qrenderdoc --python script_path with payload via env.

    Returns (returncode, elapsed_seconds). The replay script is responsible
    for writing its own output files; we only forward the exit code.

    Output is redirected directly to log_path (NOT captured through PIPE) to
    avoid Windows hang: capture_output=True keeps pipes open until ALL inherited
    handles close, including any grandchild qrenderdoc helpers that may inherit
    them; the pipes can stay open indefinitely past the main process exit.
    """
    qrd = find_qrenderdoc()
    env = dict(os.environ)
    env['RDC_INSIDE_ARGS'] = _SEP.join(payload_args)

    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    t0 = time.monotonic()
    logf = None
    if log_path:
        logf = open(log_path, 'a', encoding='utf-8', buffering=1)
    try:
        if logf:
            logf.write(f'\n--- qrd_harness launching {os.path.basename(script_path)} ---\n')
            logf.flush()
            stdout = logf
            stderr = subprocess.STDOUT
        else:
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL

        # Popen (not subprocess.run) so we hold the pid for a process-tree kill on timeout.
        proc = subprocess.Popen([qrd, '--python', script_path], env=env,
                                stdout=stdout, stderr=stderr)
        try:
            proc.communicate(timeout=timeout_s)
            rc = proc.returncode
            if logf:
                logf.write(f'\n--- rc={rc}, elapsed={time.monotonic()-t0:.2f}s ---\n')
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            try:
                proc.wait(timeout=30)
            except Exception:
                pass
            rc = -1
            if logf:
                logf.write(f'\n--- TIMEOUT after {timeout_s}s; killed process tree pid={proc.pid} ---\n')
    finally:
        if logf:
            logf.close()
    elapsed = time.monotonic() - t0
    return rc, elapsed


def parse_inside_args(argv: list[str]) -> list[str]:
    """Called from inside qrenderdoc to retrieve payload args.

    qrenderdoc passes script path as argv[0] (approximately) and may swallow
    later positionals; the canonical source is RDC_INSIDE_ARGS.
    """
    env = os.environ.get('RDC_INSIDE_ARGS', '')
    if env:
        return env.split(_SEP)
    return argv[1:] if len(argv) > 1 else []
