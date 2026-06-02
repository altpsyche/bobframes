"""c16d-b (ADR-34): the vendored Inter subset is inlined as a deterministic, offline @font-face.

The report contract is "single self-contained HTML, renders + opens with NO network, byte-stable".
A web-font fetch would break all three; a committed woff2 base64-inlined at import does not. These
asserts pin the mechanism (golden HTML proves end-to-end byte-identity)."""

from __future__ import annotations

from importlib.resources import files

from bobframes.reports import chrome


def _woff2_bytes():
    return files('bobframes.reports').joinpath('assets', 'inter-subset.woff2').read_bytes()


def test_subset_woff2_ships_and_is_woff2():
    b = _woff2_bytes()
    assert b[:4] == b'wOF2', 'asset is not a woff2 (magic wOF2)'
    # subset stays small (Latin + tnum, wght 400-600); guard against an accidental full-font swap
    assert 5_000 < len(b) < 80_000, f'unexpected subset size {len(b)} (full Inter would be ~350KB)'


def test_font_face_inlined_offline_and_ascii():
    css = chrome._compose_css()
    assert '@font-face' in css
    assert 'src:url(data:font/woff2;base64,' in css       # inlined, not a network URL
    assert 'http://' not in css and 'https://' not in css  # no CDN fetch anywhere in the CSS
    assert "format('woff2')" in css
    assert "font-weight:400 600" in css                    # variable range we actually use
    assert css.isascii()                                   # base64 alphabet -> page lint stays clean


def test_font_ships_on_both_css_paths():
    # report/dashboard/preview pages (minified) AND drill/root (un-minified via chrome_css())
    assert '@font-face' in chrome._compose_css()
    assert '@font-face' in chrome.chrome_css()
    # design_tokens_css() stays a pure :root block (template.py contract + test_root_block_shape)
    assert '@font-face' not in chrome.design_tokens_css()


def test_base64_is_deterministic():
    import base64
    expect = base64.b64encode(_woff2_bytes()).decode('ascii')
    assert chrome._FONT_WOFF2_B64 == expect       # over fixed committed bytes -> byte-stable
    assert chrome._FONT_WOFF2_B64 == base64.b64encode(_woff2_bytes()).decode('ascii')


def test_kpi_and_headline_use_sans_not_mono():
    c = chrome._CHROME_CSS
    s = chrome._STICKY_CSS
    assert "font: 600 var(--fs-display)/1.05 'Inter', 'Segoe UI', system-ui, sans-serif;" in c
    assert "font: 600 var(--fs-h1)/1.15 'Inter', 'Segoe UI', system-ui, sans-serif;" in s
    # data tables stay monospace (dual-stack hierarchy)
    assert "ui-monospace, 'Cascadia Code', Consolas, monospace" in c
