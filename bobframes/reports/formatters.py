"""Cell renderers and text-normalization helpers used across reports."""

from __future__ import annotations

import functools
import html as _html
import re

from .. import config
from ..derives import classifier

# Default-compiled alias kept for back-compat re-export (base.__all__). The ACTIVE scrub pattern
# comes from config (H-16); a test asserts this default equals the config default.
_BANNED_CHROME_CHARS = re.compile(r'[—–…“”‘’→←↑↓×·]')


@functools.lru_cache(maxsize=None)
def _chrome_scrub_compiled(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def _chrome_scrub() -> re.Pattern:
    """The chrome-char scrub pattern from config (H-16), compiled+cached by pattern string."""
    return _chrome_scrub_compiled(config.get_config().formatting.chrome_scrub_chars)


def per_frame(total, frames):
    """Per-frame rate ``total / frames``, the c16v multi-capture normalization (G-29).

    ``frames <= 1`` (or None) returns ``total`` UNCHANGED - the SAME object, same type - so on
    1-capture-per-frame data every formatter/heatmap renders byte-for-byte the pre-c16v counts
    (golden-neutral by construction; ``heatmap_cell`` emits the raw value via ``h()``, where a float
    ``6.0`` would serialize ``"6.0"`` != int ``"6"``). Only ``frames > 1`` divides. Callers keep RAW
    integer counters and divide at read-time via this one helper - never float-accumulate.
    """
    return total if (frames is None or frames <= 1) else total / frames


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


def fmt_id_short(v, n: int | None = None) -> str:
    if not v:
        return ''
    if n is None:
        n = config.get_config().formatting.id_short_n   # H-23
    s = str(v)
    return s[:n] if len(s) > n else s


def mesh_hash_short(hsh, n: int | None = None) -> str:
    return fmt_id_short(hsh, n)


def safe_chrome_text(s) -> str:
    """Escape + scrub banned chrome chars. Apply to all chrome strings outside <table>."""
    if s is None:
        return ''
    scrubbed = _chrome_scrub().sub('_', str(s))
    return _html.escape(scrubbed)


def trunc_mid(s: str | None, max_len: int | None = None) -> str:
    if s is None:
        return ''
    if max_len is None:
        max_len = config.get_config().formatting.text_trunc_max   # H-23
    s = str(s)
    if len(s) <= max_len:
        return s
    keep = max_len - 3
    head = keep // 2
    tail = keep - head
    return s[:head] + '...' + s[-tail:]


def trunc_left(s: str | None, max_len: int | None = None) -> str:
    """Truncate from the left, keep the suffix. For pass paths whose tail carries the signal."""
    if s is None:
        return ''
    if max_len is None:
        max_len = config.get_config().formatting.text_trunc_max   # H-23
    s = str(s)
    if len(s) <= max_len:
        return s
    return '...' + s[-(max_len - 3):]


def pass_short(path: str | None) -> str:
    """Reduce an engine pass path to its meaningful tail.

    Strips the leading ``[pass_strip].prefixes`` (UE default: FRDGBuilder::Execute/MobileSceneRender/)
    and drops ``[pass_strip].noise_segments`` (UE default: Engine/EngineMaterials) — both from the
    active classifier preset (H-2). The structural `/<Foo>.<Foo>` FName-redundancy collapse stays in
    code (engine-agnostic).
    """
    if not path:
        return ''
    s = str(path)
    strip = classifier.pass_strip()
    for pre in strip.get('prefixes', ()):
        if s.startswith(pre):
            s = s[len(pre):]
    noise = set(strip.get('noise_segments', ()))
    # Collapse /A/B/C.../<Name>.<Name> SM_X  → <Name> SM_X (FName redundant)
    parts = s.split('/')
    cleaned = []
    for p in parts:
        if not p:
            continue
        # asset prefix like "/Engine/EngineMaterials" is just noise
        if p in noise:
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
