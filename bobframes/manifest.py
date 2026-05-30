"""Per-drop _manifest.json writer.

Records schema version, build timestamp, per-capture replay status, row
counts per table, and rotated-dir name (if a previous _analysis_out was
rotated during this run).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import subprocess
from typing import Any

from . import qrd_harness, rdcmd, schemas
from ._version import __version__


def now_iso() -> str:
    """Single source of truth for timestamps: always UTC, second precision."""
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def _tool_version(path: str) -> str:
    """Best-effort `<tool> --version` first line. Never raises."""
    try:
        p = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=15)
        out = (p.stdout or p.stderr or '').strip()
        return out.splitlines()[0].strip() if out else 'unknown'
    except Exception:
        return 'unknown'


def gather_tool_versions() -> dict[str, str]:
    """Record renderdoccmd / qrenderdoc versions at ingest (G-6). Best-effort."""
    versions: dict[str, str] = {}
    try:
        versions['renderdoccmd'] = _tool_version(rdcmd.find_renderdoccmd())
    except Exception:
        versions['renderdoccmd'] = 'unknown'
    try:
        versions['qrenderdoc'] = _tool_version(qrd_harness.find_qrenderdoc())
    except Exception:
        versions['qrenderdoc'] = 'unknown'
    return versions


def gather_host_info() -> dict[str, str]:
    """Record GPU/driver/CPU/OS + bobframes version at ingest (G-7). Best-effort."""
    gpu, driver = 'unknown', 'unknown'
    try:
        ps = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-CimInstance Win32_VideoController | '
             'Select-Object -First 1 -Property Name,DriverVersion | ConvertTo-Json -Compress'],
            capture_output=True, text=True, timeout=20,
        )
        if ps.returncode == 0 and ps.stdout.strip():
            obj = json.loads(ps.stdout)
            if isinstance(obj, list):
                obj = obj[0] if obj else {}
            gpu = (obj.get('Name') or 'unknown').strip()
            driver = (obj.get('DriverVersion') or 'unknown').strip()
    except Exception:
        pass
    return {
        'gpu': gpu,
        'gpu_driver': driver,
        'cpu': platform.processor() or 'unknown',
        'os': platform.platform(),
        'bobframes': __version__,
    }


def build_manifest(
    *,
    area: str,
    drop_date: str,
    drop_label: str,
    captures: list[str],
    capture_status: dict[str, str],
    row_counts: dict[str, int],
    rotated_from: str | None,
    build_timestamp: str | None = None,
    tool_versions: dict[str, str] | None = None,
    host_info: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        'schema_version': schemas.SCHEMA_VERSION,
        'build_timestamp': build_timestamp or now_iso(),
        'area': area,
        'drop_date': drop_date,
        'drop_label': drop_label,
        'captures': sorted(captures, key=lambda s: (len(s), s)),
        'capture_status': dict(capture_status),
        'row_counts': dict(row_counts),
        'tool_versions': dict(tool_versions or {}),
        'host_info': dict(host_info or {}),
        'rotated_from': rotated_from,
    }


def write_manifest(out_dir: str, manifest: dict[str, Any]) -> str:
    """Atomically write _manifest.json (tmp + os.replace) so a crash mid-write
    never leaves a partial file the catalog would silently skip (R-1)."""
    path = os.path.join(out_dir, '_manifest.json')
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, sort_keys=False)
            f.write('\n')
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return path


def read_manifest(out_dir: str) -> dict[str, Any]:
    path = os.path.join(out_dir, '_manifest.json')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
