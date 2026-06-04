"""c16r: the `head_assets(sink)` seam (ADR-41). PROVES the refactor introduced no output change
before c16t builds on it. Two contracts:

- INLINE is byte-faithful to the pre-c16r emission (so test_parity stays green by construction).
- REF emits depth-correct `_assets/` links for both page families, and the per-family manifest is the
  SINGLE source of the (filename -> content) pairing (so c16t's file-writer and the REF links cannot
  drift apart - the zero-drift property ADR-41 is built around).

See QUALITY_GATES §21.1r.
"""

from __future__ import annotations

import glob
import os

from bobframes.html import template
from bobframes.reports import base as reports_base
from bobframes.reports import chrome

from . import _render_util as u

DEPTHS = (0, 1, 2, 4)


# --- report family (chrome.page_open) -----------------------------------------

def test_report_inline_is_byte_faithful():
    """INLINE.head == today's exact `<style>{_compose_css()}</style><script>{_compose_js()}</script>`
    (the empty-JS guard preserved); body_js is '' (report-family JS rides in the head)."""
    ha = chrome.head_assets(chrome.AssetSink.INLINE)
    js = chrome._compose_js()
    assert js, "report JS is non-empty today; the guard branch is dead but kept for faithfulness"
    expected = f'<style>{chrome._compose_css()}</style><script>{js}</script>'
    assert ha.head == expected
    assert ha.body_js == ''


def test_report_inline_matches_page_open_bytes():
    """The real snapshot: page_open emits head_assets(INLINE) verbatim between the favicon <link>
    and </head>. Anchor on the reconstructed favicon literal (NOT a naive '>' split - _FAVICON_HREF
    contains literal '>' in its inline <svg>) + </head>."""
    out = chrome.page_open('snapshot')
    favicon = f'<link rel="icon" href="{chrome._FAVICON_HREF}">'
    ha = chrome.head_assets(chrome.AssetSink.INLINE)
    assert favicon + ha.head + ha.body_js + '</head>' in out
    assert out.count('<style>') == 1


def test_report_ref_depth_correct():
    """REF.head == depth-correct report.{css,js} links (css -> stylesheet, js -> DEFERRED external);
    body_js stays ''; ASCII-only with no base64 font payload leaking into the links."""
    for d in DEPTHS:
        ha = chrome.head_assets(chrome.AssetSink.REF, d)
        p = '../' * d
        expected = (f'<link rel="stylesheet" href="{p}_assets/report.css">'
                    f'<script defer src="{p}_assets/report.js"></script>')
        assert ha.head == expected, f"depth {d}"
        assert ha.body_js == ''
        assert ha.head.isascii()
        assert 'base64' not in ha.head


# --- catalog/drill family (html.template) -------------------------------------

def test_catalog_inline_is_byte_faithful():
    """INLINE for the catalog/drill family: `<style>{_CSS}</style>` (head) + the body-end engine
    `<script>{rdc_table_js()}</script>` (body_js) - the two pieces at their distinct doc positions."""
    ha = template.head_assets(reports_base.AssetSink.INLINE)
    assert ha.head == f'<style>{template._CSS}</style>'
    assert ha.body_js == f'<script>{reports_base.rdc_table_js()}</script>'


def test_catalog_inline_present_in_golden():
    """Real snapshot: the committed catalog (root) + a drill golden carry both INLINE literals
    verbatim (the bytes render_root/render_drop emit). Cheap proxy for a fresh render - test_parity
    already byte-compares the full tree."""
    inline = template.head_assets(reports_base.AssetSink.INLINE)
    catalog = open(os.path.join(u.GOLDEN_DIR, 'index.html'), encoding='utf-8').read()
    assert inline.head in catalog
    assert inline.body_js in catalog
    drills = glob.glob(os.path.join(u.GOLDEN_DIR, '_reports', 'drill', '*', '*', 'index.html'))
    assert drills, "expected at least one drill golden"
    drill = open(drills[0], encoding='utf-8').read()
    assert inline.head in drill
    assert inline.body_js in drill


def test_catalog_ref_depth_correct():
    """REF for the catalog/drill family: depth-correct catalog.{css,js} (link in head, deferred
    script in body_js); ASCII-only."""
    for d in DEPTHS:
        ha = template.head_assets(reports_base.AssetSink.REF, d)
        p = '../' * d
        assert ha.head == f'<link rel="stylesheet" href="{p}_assets/catalog.css">', f"depth {d}"
        assert ha.body_js == f'<script defer src="{p}_assets/catalog.js"></script>'
        assert (ha.head + ha.body_js).isascii()


# --- the manifest is the single source of the (filename -> content) pairing ---

def test_report_manifest_single_source():
    """REPORT_ASSETS names + kinds + content producers are the ONE source the REF links and c16t's
    writer both consume (no duplicated 'report.css' literal that could drift)."""
    by_name = {a.name: a for a in chrome.REPORT_ASSETS}
    assert set(by_name) == {'report.css', 'report.js'}
    assert by_name['report.css'].kind == 'css' and by_name['report.css'].content is chrome._compose_css
    assert by_name['report.js'].kind == 'js' and by_name['report.js'].content is chrome._compose_js
    # the REF link a page emits names exactly the file c16t will write from content()
    prefix = chrome.assets_prefix(0)
    assert by_name['report.css'].ref_link(prefix) == '<link rel="stylesheet" href="_assets/report.css">'
    assert by_name['report.js'].ref_link(prefix) == '<script defer src="_assets/report.js"></script>'


def test_catalog_manifest_single_source():
    """CATALOG_ASSETS likewise; the c16t invariant report.css==_compose_css / catalog.css==_CSS etc.
    is pinned here so a future rename cannot silently fork the asset boundary."""
    by_name = {a.name: a for a in template.CATALOG_ASSETS}
    assert set(by_name) == {'catalog.css', 'catalog.js'}
    assert by_name['catalog.css'].kind == 'css' and by_name['catalog.css'].content() == template._CSS
    assert by_name['catalog.js'].kind == 'js' and by_name['catalog.js'].content is reports_base.rdc_table_js
    # the four extractable assets map to their composer outputs (the §21.1s contract c16t writes from)
    assert chrome.REPORT_ASSETS[0].content() == chrome._compose_css()
    assert chrome.REPORT_ASSETS[1].content() == chrome._compose_js()
    assert by_name['catalog.css'].content() == template._CSS
    assert by_name['catalog.js'].content() == reports_base.rdc_table_js()
