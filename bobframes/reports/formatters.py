"""Cell renderers and text-normalization helpers used across reports."""

from __future__ import annotations

import html as _html
import re


_BANNED_CHROME_CHARS = re.compile(r'[—–…“”‘’→←↑↓×·]')


def fmt_int(v) -> str:
    if v is None or v == '':
        return ''
    try:
        return f'{int(v):,}'
    except (TypeError, ValueError):
        return ''


def fmt_float(v, prec: int = 3) -> str:
    if v is None or v == '':
        return ''
    try:
        return f'{float(v):,.{prec}f}'
    except (TypeError, ValueError):
        return ''


def fmt_bytes(v) -> str:
    return fmt_int(v)


def fmt_pct(v, prec: int = 1) -> str:
    if v is None or v == '':
        return ''
    try:
        return f'{float(v):.{prec}f}%'
    except (TypeError, ValueError):
        return ''


def fmt_id_short(v, n: int = 12) -> str:
    if not v:
        return ''
    s = str(v)
    return s[:n] if len(s) > n else s


def mesh_hash_short(hsh, n: int = 12) -> str:
    return fmt_id_short(hsh, n)


def safe_chrome_text(s) -> str:
    """Escape + scrub banned chrome chars. Apply to all chrome strings outside <table>."""
    if s is None:
        return ''
    scrubbed = _BANNED_CHROME_CHARS.sub('_', str(s))
    return _html.escape(scrubbed)


def trunc_mid(s: str | None, max_len: int = 60) -> str:
    if s is None:
        return ''
    s = str(s)
    if len(s) <= max_len:
        return s
    keep = max_len - 3
    head = keep // 2
    tail = keep - head
    return s[:head] + '...' + s[-tail:]


def trunc_left(s: str | None, max_len: int = 60) -> str:
    """Truncate from the left, keep the suffix. For pass paths whose tail carries the signal."""
    if s is None:
        return ''
    s = str(s)
    if len(s) <= max_len:
        return s
    return '...' + s[-(max_len - 3):]


def pass_short(path: str | None) -> str:
    """Reduce a UE pass path to its meaningful tail.

    Strips FRDGBuilder::Execute/MobileSceneRender/ prefix.
    Collapses /Engine/EngineMaterials/<Name>.<Name>/ to <Name>/.
    Collapses any `/<Foo>.<Foo>` repeated-name asset pattern to `/<Foo>`.
    """
    if not path:
        return ''
    s = str(path)
    if s.startswith('FRDGBuilder::Execute/'):
        s = s[len('FRDGBuilder::Execute/'):]
    if s.startswith('MobileSceneRender/'):
        s = s[len('MobileSceneRender/'):]
    # Collapse /A/B/C.../<Name>.<Name> SM_X  → <Name> SM_X (UE FName redundant)
    parts = s.split('/')
    cleaned = []
    for p in parts:
        if not p:
            continue
        # asset prefix like "/Engine/EngineMaterials" is just noise
        if p in ('Engine', 'EngineMaterials'):
            continue
        # collapse "Name.Name" → "Name"
        if '.' in p:
            head, _, rest = p.partition('.')
            after = rest.split(' ', 1)
            if after[0] == head:
                p = head if len(after) == 1 else f'{head} {after[1]}'
        cleaned.append(p)
    return '/'.join(cleaned)


def pass_suffix(path: str | None) -> str:
    """Last meaningful segment of a pass path, with UE noise stripped."""
    short = pass_short(path)
    if not short:
        return ''
    return short.rsplit('/', 1)[-1]
