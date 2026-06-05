"""c16x-5: structural asserts for the promoted build-health components (chrome.kpi_card / status_badge
/ movement, delta.trendline; ADR-42). Golden-independent (mirrors test_report_structure); the summary
golden additionally gates them end-to-end at visual parity.
"""
from __future__ import annotations

from bobframes.reports import chrome, delta


def test_kpi_card_markup_and_escaping():
    out = chrome.kpi_card('avg draws', '28,410', delta_html='<span class="delta-pill neg">+4%</span>',
                          trend='<svg></svg>', note='5 areas', tone='neg')
    assert out == (
        '<div class="kpi-chip tone-neg">'
        '<div class="kpi-label">avg draws</div>'
        '<div class="kpi-value">28,410</div>'
        '<div class="kpi-delta"><span class="delta-pill neg">+4%</span></div>'   # delta spliced raw
        '<div class="kpi-note dim">5 areas</div>'
        '<svg></svg></div>')                                                     # trend spliced raw
    assert '<div class="kpi-delta"></div>' in chrome.kpi_card('x', '0')          # empty delta div present
    assert '&amp;' in chrome.kpi_card('a & b', '0')                              # label escaped


def test_status_badge_markup():
    assert chrome.status_badge('AT_RISK', 'Needs attention') == \
        '<span class="bh-status s-AT_RISK">Needs attention</span>'
    assert chrome.status_badge('OK', 'a & b') == '<span class="bh-status s-OK">a &amp; b</span>'


def test_movement_markup():
    out = chrome.movement([('Improvements', '<ul></ul>'), ('Regressions', '<ul></ul>')],
                          rollup_html='<p>r</p>')
    assert out == ('<div class="movement">'
                   '<div class="mv-col"><h3>Improvements</h3><ul></ul></div>'
                   '<div class="mv-col"><h3>Regressions</h3><ul></ul></div>'
                   '<p>r</p></div>')


def test_trendline_renamed_classes():
    out = delta.trendline([3, 5, 4, 8], tone='neg')
    assert 'class="trendline tone-neg"' in out
    assert ('class="trendline-fill"' in out and 'class="trendline-line"' in out
            and 'class="trendline-dot"' in out)
    assert 'bh-trend' not in out and 'bh-fill' not in out          # old names gone
    assert delta.trendline([1]) == ''                              # < 2 points -> ''


def test_summary_css_relocated_into_owned_bundle():
    """The summary component CSS lives in the owned bundle now (not a per-page <style>), renamed
    .bh-trend* -> .trendline*; the guard stays clean."""
    css = chrome._compose_css()
    assert '.trendline-fill' in css and '.trendline-line' in css
    assert '.bh-trend' not in css                                  # renamed away
    assert '[data-page-kind="summary"]' in css                     # scoped -> inert elsewhere
    assert chrome.undefined_tokens() == set()
