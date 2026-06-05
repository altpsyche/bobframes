"""c16x-1: the chrome CSS/JS live as real files under reports/assets/ (loaded via importlib.resources,
the design_tokens.toml precedent), not Python string literals.

Byte-identity of the COMPOSED output is gated end-to-end by test_parity / test_design_tokens. These
asserts pin the focused MECHANISM (QUALITY_GATES §21.1u): the files exist + are ASCII, the loaded
constants are the file contents verbatim, and every template placeholder still resolves after the file
load (the new failure mode introduced by moving the literals out of Python).
"""
from __future__ import annotations

from importlib.resources import files as _files

from bobframes.reports import chrome
from bobframes.html import template

_ASSET_DIR = _files('bobframes.reports').joinpath('assets')

# Every text asset the chrome/template bundles now load from disk.
_CSS_ASSETS = [
    'design_tokens.css', 'chrome.css', 'sticky.css', 'link_kind.css', 'container.css',
    'print.css', 'components.css', 'rdc_table.css', 'per_drop.css',
]
# JS + the icon sprite. rdc_table.js carries the U+25B2/U+25BC sort-arrow glyphs (a non-ASCII <script>
# body, which the whole-page lint banlist exempts -- see base._lint_or_raise); these were inline before
# c16x-1 and the extraction is byte-faithful, so the file is NOT ASCII-constrained.
_OTHER_ASSETS = ['components.js', 'rdc_table.js', 'icon_sprite.html']


def test_assets_exist():
    """Each bundled asset resolves via importlib.resources -> ships in the wheel (the woff2 precedent)."""
    for name in _CSS_ASSETS + _OTHER_ASSETS:
        p = _ASSET_DIR.joinpath(name)
        assert p.is_file(), f'missing bundled asset {name}'
        assert p.read_text(encoding='utf-8'), f'empty asset {name}'


def test_css_assets_are_ascii():
    """CSS uses no glyphs (ellipsis via the text-overflow keyword, not the char), so every shipped .css
    is ASCII. JS is exempt (rdc_table.js sort arrows) -- the whole-page lint already governs that."""
    for name in _CSS_ASSETS:
        _ASSET_DIR.joinpath(name).read_text(encoding='utf-8').encode('ascii')


def test_constants_are_the_file_contents_verbatim():
    """The module constants are the file contents (no stale inline literal left behind)."""
    assert chrome._DESIGN_TOKENS_TMPL == _ASSET_DIR.joinpath('design_tokens.css').read_text(encoding='utf-8')
    assert chrome._CHROME_CSS_TMPL == _ASSET_DIR.joinpath('chrome.css').read_text(encoding='utf-8')
    assert chrome._STICKY_CSS_TMPL == _ASSET_DIR.joinpath('sticky.css').read_text(encoding='utf-8')
    assert chrome._RDC_TABLE_CSS == _ASSET_DIR.joinpath('rdc_table.css').read_text(encoding='utf-8')
    assert chrome._COMPONENTS_CSS_BASE == _ASSET_DIR.joinpath('components.css').read_text(encoding='utf-8')
    assert chrome._COMPONENTS_JS_ALL == _ASSET_DIR.joinpath('components.js').read_text(encoding='utf-8')
    assert chrome._RDC_TABLE_JS_TMPL == _ASSET_DIR.joinpath('rdc_table.js').read_text(encoding='utf-8')
    assert chrome._ICON_SPRITE == _ASSET_DIR.joinpath('icon_sprite.html').read_text(encoding='utf-8')
    assert template._PER_DROP_CSS == _ASSET_DIR.joinpath('per_drop.css').read_text(encoding='utf-8')


def test_substitution_complete_after_file_load():
    """${token} / __ROW_H__ placeholders resolve after the file load (the c16x-1 failure mode): the
    composed bundles carry no leftover '$', and the rdc-table row-height marker is substituted."""
    assert '$' not in chrome._compose_css()
    assert '$' not in template._compose_css()
    assert '__ROW_H__' not in chrome._RDC_TABLE_JS              # substituted in the live constant
    assert '__ROW_H__' in chrome._RDC_TABLE_JS_TMPL             # the raw template still carries it
