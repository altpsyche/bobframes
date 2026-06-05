"""c1c (ADR-45): the user theme override -- the chrome compose seam (theme=None byte-identical, a
color override re-hues the :root only), the render-time token guard, the CLI (`--accent` on render/
preview, `export-tokens --theme-template`, `package` flag rejection), and the end-to-end user path
(a `.bobframes.toml` [theme] reaching rendered pages). The config `[theme]` PARSE is in test_config.
"""

from __future__ import annotations

import os
import subprocess
import sys

from bobframes.reports import chrome

from . import _render_util as u

# A blue accent (oklch); the inner per-token form (no comma-adjacent space) survives CSS minify, so it
# is a minify-safe needle for the report-family (<style>) pages.
_ACCENT = 'light-dark(oklch(55% 0.15 264), oklch(72% 0.13 264))'
_NEEDLE = 'oklch(55% 0.15 264)'


def _run_cli(*args):
    env = {k: v for k, v in os.environ.items() if k != 'BOBFRAMES_CONFIG'}
    return subprocess.run([sys.executable, '-m', 'bobframes.cli', *args],
                          capture_output=True, text=True, env=env)


# --- compose seam: theme=None is byte-identical, an override re-hues the :root only ---------------

def test_compose_css_none_is_default_byte_identical():
    assert chrome.compose_css(None) == chrome._compose_css()
    assert chrome.compose_css({}) == chrome._compose_css()
    assert chrome.design_tokens_css(None) == chrome._DESIGN_TOKENS


def test_compose_css_theme_rehues_root_value_only():
    css = chrome.compose_css({'accent_primary': _ACCENT})
    assert css != chrome._compose_css()
    assert _ACCENT.replace(' ', '') in css.replace(' ', '')   # minified: inter-arg spaces dropped
    # we changed a VALUE, not the references -- the var(--accent-primary) ref count is unchanged
    assert css.count('var(--accent-primary)') == chrome._compose_css().count('var(--accent-primary)')


def test_design_tokens_css_theme_rehues_unminified():
    out = chrome.design_tokens_css({'accent_primary': _ACCENT})
    assert _ACCENT in out and '--accent-primary:' in out


# --- the render-time safety guard -----------------------------------------------------------------

def test_theme_guard_catches_undefined_ref():
    """A value that smuggles in an undefined var(--ref) passes config's ASCII/allowlist gate, but the
    render-time guard catches it (render/preview warn non-fatally; this is the hard CI assert)."""
    assert chrome.theme_undefined_tokens(None) == set()
    assert chrome.theme_undefined_tokens({}) == set()
    bad = chrome.theme_undefined_tokens({'accent_primary': 'var(--totally-bogus)'})
    assert 'totally-bogus' in bad


# --- end-to-end: a .bobframes.toml [theme] reaches the rendered report pages ----------------------

def test_render_with_theme_config_rehues_pages(tmp_path):
    root = u.render_fresh(str(tmp_path / 'root'))           # default render first (no theme)
    summary = os.path.join(root, '_reports', 'summary.html')
    assert _NEEDLE not in open(summary, encoding='utf-8').read()   # neutral by default
    with open(os.path.join(root, '.bobframes.toml'), 'w', encoding='utf-8') as f:
        f.write(f"[theme]\naccent_primary = '{_ACCENT}'\n")
    u.render(root)                                          # re-render reads <root>/.bobframes.toml
    assert _NEEDLE in open(summary, encoding='utf-8').read()


# --- CLI: preview --accent, export-tokens --theme-template, package rejects the flag --------------

def test_preview_accent_flag_rehues_gallery(tmp_path):
    r = _run_cli('preview', str(tmp_path), '--accent', _ACCENT)
    assert r.returncode == 0, r.stderr
    html = open(os.path.join(tmp_path, '_reports', '_chrome_preview.html'), encoding='utf-8').read()
    assert _NEEDLE in html


def test_export_theme_template_is_ascii_and_color_only():
    r = _run_cli('export-tokens', '--theme-template')
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert '[theme]' in out
    assert '# accent_primary' in out and '# accent_data' in out and '# c_opaque' in out
    # only the color knobs are listed -- never a layout/spacing/radius knob line
    assert '# sp_4' not in out and '# radius_sm' not in out and '# kpi_strip_min' not in out
    out.encode('ascii')   # ASCII discipline (no em-dash / smart quote in shipped text)


def test_package_rejects_accent_flag(tmp_path):
    """`package` is a PRESENTATION verb (ADR-40/45): it has no --accent, so argparse rejects it."""
    r = _run_cli('package', str(tmp_path), '--accent', 'oklch(50% 0 0)')
    assert r.returncode != 0
    assert 'accent' in (r.stderr + r.stdout).lower()
