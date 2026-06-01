"""renderdoccmd wrapper.

Locates renderdoccmd.exe via config.resolve_tool (env > config > PATH > known paths, c06)
and exposes a convert() helper that produces .xml / .zip.xml from .rdc.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from . import config


def find_renderdoccmd() -> str:
    """Resolve renderdoccmd.exe (delegates to config.resolve_tool; raises ToolNotFound)."""
    return config.resolve_tool('renderdoccmd')


def convert(rdc_path: str, out_path: str, fmt: str = 'xml', timeout_s: float = 120.0) -> float:
    """Convert .rdc to xml or zip.xml. Returns elapsed seconds.

    fmt is 'xml' or 'zip.xml'. Raises RuntimeError on failure.
    """
    if fmt not in ('xml', 'zip.xml'):
        raise ValueError(f'unknown fmt: {fmt!r}')
    cmd = [
        find_renderdoccmd(), 'convert',
        '-f', rdc_path,
        '-o', out_path,
        '-i', 'rdc',
        '-c', fmt,
    ]
    t0 = time.monotonic()
    try:
        rc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        # capture_output swallows stderr on timeout; surface the tail before re-raising (R-8).
        out = e.stderr or e.output or ''
        if isinstance(out, bytes):
            out = out.decode('utf-8', 'replace')
        print(f'renderdoccmd convert timed out after {timeout_s}s (fmt={fmt}): {out[-400:]}',
              file=sys.stderr)
        raise
    elapsed = time.monotonic() - t0
    if rc.returncode != 0:
        tail = (rc.stderr or rc.stdout or '')[-400:]
        raise RuntimeError(
            f'renderdoccmd convert failed (rc={rc.returncode}, fmt={fmt}): {tail}'
        )
    if not os.path.exists(out_path):
        raise RuntimeError(f'renderdoccmd convert reported success but {out_path} is missing')
    return elapsed


def needs_export(rdc_path: str, out_path: str) -> bool:
    """True if out_path is missing or older than rdc_path."""
    if not os.path.exists(out_path):
        return True
    return os.path.getmtime(out_path) < os.path.getmtime(rdc_path)
