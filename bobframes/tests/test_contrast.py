"""v0.2.6 gate: dependency-free oklch -> WCAG contrast audit of the design-token palette (ADR-43 #8).

Dark-mode / contrast regressions are invisible to the theme-agnostic HTML golden, so they need their
own check. This converts each color token's `light-dark()` oklch pair to a relative luminance (Bjorn
Ottosson's oklab -> linear-sRGB, then the WCAG luminance coefficients) and computes WCAG 2.x contrast
ratios for the load-bearing text/background pairs. No third-party dependency, deterministic.

`--text-3` (tertiary meta) FAILS AA today (~3:1, recorded G/WCAG); the v0.2.6-1a token lift raises it to
~oklch(0.48). That assertion is a STRICT xfail here: it is xfail (green) now, and FLIPS to a hard failure
(XPASS-strict) the moment 1a fixes it -- the signal to delete the marker (ADR-23: track the known gap, do
not hide it).
"""
from __future__ import annotations

import math
import re

import pytest

from bobframes.reports import _tokens

_OKLCH = re.compile(r'oklch\(\s*([0-9.]+)(%?)\s+([0-9.]+)\s+([0-9.]+)')
_AA_NORMAL = 4.5   # WCAG AA, normal text
_AA_LARGE = 3.0    # WCAG AA, large/secondary text


def _oklch_to_linear_srgb(L: float, C: float, h_deg: float) -> tuple[float, float, float]:
    """oklch -> linear-light sRGB (Ottosson 2020). Channels may fall slightly outside [0,1]."""
    h = math.radians(h_deg)
    a, b = C * math.cos(h), C * math.sin(h)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bch = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return r, g, bch


def _luminance(oklch: tuple[float, float, float]) -> float:
    """WCAG relative luminance of an oklch color (channels clamped to the sRGB gamut)."""
    r, g, b = (min(1.0, max(0.0, x)) for x in _oklch_to_linear_srgb(*oklch))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _tup(m: tuple) -> tuple[float, float, float]:
    L = float(m[0]) / 100.0 if m[1] == '%' else float(m[0])
    return (L, float(m[2]), float(m[3]))


def _resolve(name: str, subst: dict) -> tuple[tuple, tuple]:
    """A color token's (light_oklch, dark_oklch), following `var(--x)` refs and `light-dark()` pairs."""
    raw = subst[name.replace('-', '_')]
    if raw.startswith('var('):
        return _resolve(re.search(r'var\(--([\w-]+)\)', raw).group(1), subst)
    found = _OKLCH.findall(raw)
    if 'light-dark' in raw:
        return _tup(found[0]), _tup(found[1])
    return _tup(found[0]), _tup(found[0])


def _ratios(fg: str, bg: str) -> tuple[float, float]:
    """(light_ratio, dark_ratio) for fg-on-bg."""
    subst = _tokens.token_subst()
    fl, fd = _resolve(fg, subst)
    bl, bd = _resolve(bg, subst)
    return _contrast(_luminance(fl), _luminance(bl)), _contrast(_luminance(fd), _luminance(bd))


# --- converter sanity (reference values) ----------------------------------------------------------
def test_converter_matches_wcag_reference():
    black, white = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)
    assert _contrast(_luminance(white), _luminance(black)) == pytest.approx(21.0, abs=0.1)
    # a self-pair is always 1.0
    assert _contrast(_luminance((0.5, 0.0, 0.0)), _luminance((0.5, 0.0, 0.0))) == pytest.approx(1.0)


# --- palette audit (both themes) ------------------------------------------------------------------
def test_primary_text_on_background_passes_aaa():
    light, dark = _ratios('fg', 'bg')
    assert light >= 7.0, f'fg-on-bg light = {light:.2f}'
    assert dark >= 7.0, f'fg-on-bg dark = {dark:.2f}'


def test_secondary_text_on_background_passes_aa():
    light, dark = _ratios('text_2', 'bg')
    assert light >= _AA_NORMAL, f'text-2-on-bg light = {light:.2f}'
    assert dark >= _AA_NORMAL, f'text-2-on-bg dark = {dark:.2f}'


def test_tertiary_text_on_background_passes_aa():
    """v0.2.6-1a fixed --text-3 (was ~3:1, failed AA) to a chroma-0 gray that clears AA in both themes.
    (The strict-xfail that tracked the gap was removed in-commit when the fix landed -- ADR-23.)"""
    light, dark = _ratios('text_3', 'bg')
    assert light >= _AA_NORMAL, f'text-3-on-bg light = {light:.2f}'
    assert dark >= _AA_NORMAL, f'text-3-on-bg dark = {dark:.2f}'
