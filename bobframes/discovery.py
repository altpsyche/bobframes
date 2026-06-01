"""Area + dated-drop walking.

Layout:
    <root>/
      <Area>/
        <YYYY-MM-DD>[_<label>]/
          <capture>.rdc, .xml, .zip.xml, .zip

Finds the newest dated drop per area; filters by --area / --label / --capture.
"""

from __future__ import annotations

import functools
import os
import re
from dataclasses import dataclass

from . import config

# Fallback / back-compat default. The active pattern comes from config (H-30); this is the
# compiled default used if config is unavailable and kept so the module-level name still resolves.
DATED_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})(?:_(.*))?$')


@functools.lru_cache(maxsize=None)
def _dated_re_compiled(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def _dated_re() -> re.Pattern:
    """The dated-drop pattern from config (H-30), compiled+cached by pattern string."""
    return _dated_re_compiled(config.get_config().discovery.dated_re)


@dataclass(frozen=True)
class Drop:
    area: str
    drop_date: str          # 'YYYY-MM-DD'
    drop_label: str         # text after the date, or '' if absent
    drop_dir: str           # absolute path to the dated folder
    captures: tuple[str, ...]  # rdc filenames without .rdc extension, sorted


def _list_areas(root: str) -> list[tuple[str, str]]:
    out = []
    for entry in sorted(os.listdir(root)):
        if entry.startswith('_') or entry.startswith('.'):
            continue
        full = os.path.join(root, entry)
        if os.path.isdir(full):
            out.append((entry, full))
    return out


def _latest_drop_dir(area_dir: str) -> tuple[str, str, str] | None:
    """Return (drop_date, drop_label, drop_dir) for newest dated sub-dir, else None."""
    dated = []
    pat = _dated_re()
    for entry in os.listdir(area_dir):
        m = pat.match(entry)
        if not m:
            continue
        full = os.path.join(area_dir, entry)
        if not os.path.isdir(full):
            continue
        dated.append((m.group(1), m.group(2) or '', full))
    if not dated:
        return None
    dated.sort(reverse=True)
    return dated[0]


def _captures(drop_dir: str) -> tuple[str, ...]:
    names = []
    for entry in sorted(os.listdir(drop_dir)):
        if entry.endswith('.rdc') and os.path.isfile(os.path.join(drop_dir, entry)):
            names.append(entry[:-4])
    names.sort(key=lambda s: (len(s), s))
    return tuple(names)


def find_drops(
    root: str,
    area_filter: str | None = None,
    label_filter: str | None = None,
    capture_filter: str | None = None,
) -> list[Drop]:
    """Return drops to process. One per area (newest dated drop).

    area_filter: exact area folder name to restrict to.
    label_filter: only return drops whose drop_label matches.
    capture_filter: restricts each drop's captures tuple to just this name.
    """
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        raise FileNotFoundError(f'root not found: {root}')

    drops: list[Drop] = []
    for area, area_dir in _list_areas(root):
        if area_filter and area != area_filter:
            continue
        latest = _latest_drop_dir(area_dir)
        if latest is None:
            continue
        drop_date, drop_label, drop_dir = latest
        if label_filter and drop_label != label_filter:
            continue
        captures = _captures(drop_dir)
        if not captures:
            continue
        if capture_filter:
            if capture_filter not in captures:
                continue
            captures = (capture_filter,)
        drops.append(Drop(
            area=area,
            drop_date=drop_date,
            drop_label=drop_label,
            drop_dir=drop_dir,
            captures=captures,
        ))
    return drops


def parse_single_drop_arg(arg: str, root: str) -> Drop:
    """Parse a positional argument like 'Chor bazar/2026-05-27_r110565/' into a Drop.

    Used when the user passes a specific drop directory rather than --area.
    """
    arg = arg.rstrip('/\\')
    parts = arg.replace('\\', '/').split('/')
    if len(parts) < 2:
        raise ValueError(f'expected <area>/<dated_drop>, got {arg!r}')
    area, dated = parts[-2], parts[-1]
    m = _dated_re().match(dated)
    if not m:
        raise ValueError(f'not a dated drop folder: {dated!r}')
    drop_dir = os.path.join(root, area, dated)
    if not os.path.isdir(drop_dir):
        raise FileNotFoundError(f'drop dir does not exist: {drop_dir}')
    return Drop(
        area=area,
        drop_date=m.group(1),
        drop_label=m.group(2) or '',
        drop_dir=drop_dir,
        captures=_captures(drop_dir),
    )
