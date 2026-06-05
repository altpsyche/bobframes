"""c16x-2: the escape-by-construction element builder (chrome.el / raw / el_void / classes; ADR-42).

Subsumes the roadmap's C6 -- a component built through el() cannot emit an unescaped attribute value or
text child (escaping is structural, not a per-call h() the author can forget). These pin the contract
directly (golden-independent); the icon/kpi_chip migrations are additionally gated byte-for-byte by
test_parity (they appear on rendered pages).
"""
from __future__ import annotations

import pytest

from bobframes.reports import chrome
from bobframes.reports.chrome import el, el_void, raw, classes, _Raw


def test_text_child_is_escaped():
    assert el('div', None, 'a & <b>') == '<div>a &amp; &lt;b&gt;</div>'


def test_raw_child_passes_verbatim():
    inner = el('span', {'class': 'x'}, 'a&b')
    assert isinstance(inner, _Raw)
    assert el('div', None, inner) == '<div><span class="x">a&amp;b</span></div>'
    assert el('div', None, raw('<i>ok</i>')) == '<div><i>ok</i></div>'   # no double-escape


def test_none_and_false_children_skipped():
    assert el('div', None, 'a', None, False, 'b') == '<div>ab</div>'
    assert el('div', None, ('' or None), ('keep' if True else None)) == '<div>keep</div>'


def test_zero_and_empty_string_children_kept():
    assert el('span', None, 0) == '<span>0</span>'      # 0 is not False-by-identity
    assert el('span', None, '') == '<span></span>'


def test_attr_value_escaped_and_quoted():
    assert el('a', {'href': 'x"&\'<'}) == '<a href="x&quot;&amp;&#x27;&lt;"></a>'


def test_attr_none_false_omitted_true_boolean():
    assert el('div', {'a': None, 'b': False, 'c': True, 'd': 'v'}) == '<div c d="v"></div>'


def test_attr_insertion_order_preserved():
    assert el('x', {'b': '1', 'a': '2'}) == '<x b="1" a="2"></x>'


def test_unsafe_attr_name_raises():
    for bad in ('a b', 'a"', 'on click', 'x>y', ''):
        with pytest.raises(ValueError):
            el('div', {bad: 'v'})


def test_el_void():
    assert el_void('link', {'rel': 'icon'}) == '<link rel="icon">'
    assert el_void('use', {'href': '#i'}, self_close=True) == '<use href="#i"/>'


def test_classes_skips_falsy():
    assert classes('a', '', None, 'b') == 'a b'
    assert classes() == ''


def test_nesting_returns_raw_no_double_escape():
    out = el('div', None, el('span', None, 'a&b'))
    assert isinstance(out, _Raw)
    assert out == '<div><span>a&amp;b</span></div>'


# --- the c16x-2 byte-identical leaf migrations (also gated end-to-end by test_parity) ---

def test_icon_byte_identical():
    assert chrome.icon('warn') == '<svg class="icon" aria-hidden="true"><use href="#icon-warn"/></svg>'


def test_kpi_chip_byte_identical():
    assert chrome.kpi_chip('draws', '1,234', delta='+4%', tone='neg') == (
        '<div class="kpi-chip tone-neg">'
        '<div class="kpi-label">draws</div>'
        '<div class="kpi-value">1,234</div>'
        '<div class="kpi-delta">+4%</div>'
        '</div>')
    assert chrome.kpi_chip('x', '0', tone='neutral') == (   # no delta -> no delta div
        '<div class="kpi-chip tone-neutral">'
        '<div class="kpi-label">x</div>'
        '<div class="kpi-value">0</div>'
        '</div>')
