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

_DEFAULT_QRD = (
    r'c:/Program Files/Arm/Arm Performance Studio 2026.2'
    r'/renderdoc_for_arm_gpus/qrenderdoc.exe'
)

_SEP = '\x1f'


def find_qrenderdoc() -> str:
    env = os.environ.get('RENDERDOC_QRENDERDOC', '').strip()
    if env and os.path.exists(env):
        return env
    if os.path.exists(_DEFAULT_QRD):
        return _DEFAULT_QRD
    raise FileNotFoundError(
        'qrenderdoc.exe not found. Set RENDERDOC_QRENDERDOC env var or install '
        'Arm Performance Studio 2026.2.'
    )


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
    if log_path:
        with open(log_path, 'a', encoding='utf-8', buffering=1) as logf:
            logf.write(f'\n--- qrd_harness launching {os.path.basename(script_path)} ---\n')
            logf.flush()
            try:
                proc = subprocess.run(
                    [qrd, '--python', script_path],
                    env=env,
                    stdout=logf,
                    stderr=subprocess.STDOUT,
                    timeout=timeout_s,
                )
                rc = proc.returncode
                logf.write(f'\n--- rc={rc}, elapsed={time.monotonic()-t0:.2f}s ---\n')
            except subprocess.TimeoutExpired as e:
                logf.write(f'\n--- TIMEOUT after {timeout_s}s ---\n')
                rc = -1
    else:
        try:
            proc = subprocess.run(
                [qrd, '--python', script_path],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout_s,
            )
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = -1
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
