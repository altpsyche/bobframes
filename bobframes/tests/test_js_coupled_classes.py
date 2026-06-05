"""v0.2.6-0: the do-not-rename guard for JS-coupled class names / host attributes (ADR-43 review #6).

The unified rdc-table engine (`_compose_js()`) `querySelector`s a set of structural classes and host
attributes that are ALSO styled in the CSS bundle (`_compose_css()` / `template._compose_css()`). The
v0.2.6 redesign refreshes the goldens, so a rename of one of these in the CSS but not the JS (or vice
versa) would silently break sort / heatmap / column-groups / expand while the golden-independent
structural tests stayed green. These asserts pin the co-presence: rename one side and a test goes red.

Scope = the structural, rename-risky coupling points (multi-hyphen tokens, low false-match risk), not
the per-cell content. The catalog/drill body markup (`data-table`, `table-scroll`) is additionally
guarded by the c16i/k/l substring asserts in test_report_structure.
"""
from __future__ import annotations

from bobframes.reports import chrome
from bobframes.html import template


# Structural classes/selectors the engine both STYLES (css) and QUERIES/SETS (js). A redesign that
# renames one side without the other breaks the coupling -> caught here.
_CSS_AND_JS = (
    'rdc-table[data-mode',   # querySelectorAll host bootstrap <-> [data-mode="static"] styling
    'col-groups',            # the column-group bar (.col-groups) <-> querySelector('.col-groups')
    'col-group-toggle',      # the toggle button class <-> className set in JS
    'sort-arrow',            # the sort indicator span <-> className set/queried in JS
    'rdc-controls',          # the expand-controls bar <-> className set in JS
    'rdc-expand-toggle',     # the expand button <-> className set in JS
)

# Host attributes the engine reads at runtime; the data-mode/data-expand state is also styled in CSS.
_JS_HOST_ATTRS = ('data-mode', 'data-table', 'data-expand')


def test_engine_classes_present_in_both_chrome_css_and_js():
    css, js = chrome._compose_css(), chrome._compose_js()
    for tok in _CSS_AND_JS:
        assert tok in css, f'{tok!r} missing from chrome._compose_css() (CSS<->JS rename desync?)'
        assert tok in js, f'{tok!r} missing from chrome._compose_js() (CSS<->JS rename desync?)'


def test_host_attributes_read_by_engine_js():
    js = chrome._compose_js()
    for attr in _JS_HOST_ATTRS:
        assert attr in js, f'{attr!r} no longer referenced by the engine JS'


def test_engine_coupling_holds_in_catalog_drill_bundle_too():
    """The catalog/drill family composes its own CSS bundle but reuses the SAME engine JS, so the same
    coupling must hold there (the `.table-scroll` virtual host is part of that family's CSS)."""
    css, js = template._compose_css(), chrome._compose_js()
    for tok in _CSS_AND_JS:
        assert tok in css, f'{tok!r} missing from template._compose_css()'
        assert tok in js, f'{tok!r} missing from engine JS'
    assert 'table-scroll' in css, 'the virtual-host .table-scroll class vanished from the catalog/drill CSS'
