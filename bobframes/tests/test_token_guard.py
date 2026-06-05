"""c16x-3: the token-validity guard (chrome.undefined_tokens / _undefined_token_refs; ADR-42, G-30).

A typo'd var(--sp-5) makes the property invalid -> it computes to nothing, silently zeroing (e.g.) the
chip padding until a human notices. The guard flags any var(--NAME) whose NAME is neither a declared
design token NOR a `--x:` custom property defined in the composed CSS. These pin: no false-positive on
the live report + catalog/drill bundles (incl. in-CSS-defined props and JS-referenced tokens), and that
a planted bad token is caught in CSS / an emitted style= / the JS.
"""
from __future__ import annotations

from bobframes.reports import chrome, _tokens
from bobframes.html import template


def test_report_bundle_has_no_undefined_tokens():
    """The healthy report bundle (CSS + JS) references no undefined token."""
    assert chrome.undefined_tokens() == set()


def test_catalog_drill_bundle_has_no_undefined_tokens():
    """The catalog/drill family composes its own bundle (tokens + chrome + rdc-table + per_drop)."""
    assert chrome._undefined_token_refs(template._compose_css(), chrome._compose_js()) == set()


def test_in_css_defined_props_not_false_flagged():
    """--crumb-h/--hdr-offset (sticky) + --clip-cap* (rdc-table) are defined inside CSS rule bodies, not
    the TOML scale; the guard's declared set is the union, so they are NOT flagged."""
    css = chrome._compose_css()
    declared = {k.replace('_', '-') for k in _tokens.token_subst()} | set(chrome._TOKEN_DEF_RE.findall(css))
    for name in ('crumb-h', 'hdr-offset', 'clip-cap', 'clip-cap-narrow', 'clip-cap-wide'):
        assert name in declared, name


def test_planted_undefined_in_css_is_caught():
    css = chrome._compose_css()
    assert chrome._undefined_token_refs(css + '\n.x { color: var(--sp-5); }') == {'sp-5'}


def test_planted_undefined_in_emitted_style_is_caught():
    css = chrome._compose_css()
    assert 'nope' in chrome._undefined_token_refs(css, '<div style="background: var(--nope)"></div>')


def test_planted_undefined_in_js_is_caught():
    css = chrome._compose_css()
    assert 'ghost' in chrome._undefined_token_refs(css, "el.style.color = 'var(--ghost)';")
