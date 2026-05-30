"""Stable cross-capture entity keys.

Raw resource IDs are per-capture replay state; they cannot be joined across
captures or drops. Each entity table carries `stable_key` computed from
content/shape so reports can identify "the same shader" across drops.

When inputs are unknown/null, stable_key is the empty string. Reports filter
`WHERE stable_key != ''` for cross-drop joins.
"""

from __future__ import annotations

import hashlib
import re

# Version byte prepended to every stable-key hash input. Bump when a key-derivation
# rule changes so old and new keys are provably distinct (rebuild with `ingest --force`).
KEY_VERSION = 1

_LINE_COMMENT = re.compile(r'//[^\n]*')
_BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.DOTALL)
_TRAILING_WS = re.compile(r'[ \t]+$', re.MULTILINE)
_BLANK_RUNS = re.compile(r'\n{3,}')


def normalize_glsl(source: str) -> str:
    """Strip comments + trailing whitespace + collapse blank-line runs."""
    if not source:
        return ''
    s = _BLOCK_COMMENT.sub('', source)
    s = _LINE_COMMENT.sub('', s)
    s = _TRAILING_WS.sub('', s)
    s = _BLANK_RUNS.sub('\n\n', s)
    return s.strip()


def _sha(payload: str) -> str:
    return hashlib.sha256(bytes([KEY_VERSION]) + payload.encode('utf-8')).hexdigest()


def shader_key(normalized_source: str) -> str:
    if not normalized_source:
        return ''
    return _sha(normalized_source)


def program_key(attached_shader_keys: list[str]) -> str:
    keys = [k for k in attached_shader_keys if k]
    if not keys:
        return ''
    return _sha('|'.join(sorted(keys)))


def texture_key(label, fmt, width, height, depth, mip_levels, sample_count) -> str:
    if fmt is None or width is None or height is None:
        return ''
    payload = f"{label or ''}|{fmt}|{width}|{height}|{depth or 0}|{mip_levels or 1}|{sample_count or 1}"
    return _sha(payload)


def sampler_key(
    min_filter, mag_filter,
    wrap_s, wrap_t, wrap_r,
    max_anisotropy, compare_mode, compare_func,
) -> str:
    if min_filter is None or mag_filter is None:
        return ''
    payload = f"{min_filter}|{mag_filter}|{wrap_s}|{wrap_t}|{wrap_r}|{max_anisotropy}|{compare_mode}|{compare_func}"
    return _sha(payload)


def buffer_key(usage_hint, allocated_size_bytes, first_usage_target) -> str:
    if allocated_size_bytes is None or allocated_size_bytes <= 0:
        return ''
    payload = f"{usage_hint or ''}|{allocated_size_bytes}|{first_usage_target or ''}"
    return _sha(payload)


def fbo_key(attached_keys: list[str]) -> str:
    keys = [k for k in attached_keys if k]
    if not keys:
        return ''
    return _sha('|'.join(sorted(keys)))
