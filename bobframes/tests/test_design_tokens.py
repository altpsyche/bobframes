"""c08: design-tokens TOML layer (H-15/H-20) + preview/export-tokens verbs.

The golden HTML gate (test_parity) proves end-to-end byte-identity of the emitted CSS. These asserts
pin the MECHANISM and give a focused failure when a bundled token value drifts from today's emitted
form (ADR-6 / QUALITY_GATES §21.1c), independent of the full-page golden.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

from bobframes.reports import chrome, delta, _tokens

from . import _render_util as u


# --- H-15: token substitution is complete and byte-exact ----------------------

def test_substitution_leaves_no_placeholder():
    """Every ${...} resolved: the assembled CSS strings carry no leftover '$'."""
    for blob in (chrome._DESIGN_TOKENS, chrome._CHROME_CSS, chrome._STICKY_CSS):
        assert '$' not in blob


def test_root_block_shape():
    css = chrome.design_tokens_css()
    assert css is chrome._DESIGN_TOKENS
    assert css.startswith('\n:root {')
    assert 'color-scheme: light dark;' in css
    # the reduced-motion reset is a fixed a11y behavior, kept literal (not a token)
    assert '@media (prefers-reduced-motion: reduce) {' in css
    assert css.count('--motion-hover: 0s;') == 1


def test_exact_color_lines_preserved():
    """Spot-check hand-aligned lines, incl. the 3-space alignment, to prove value spacing is verbatim
    (the drill/root pages embed this block UN-minified, so the spacing is parity-significant)."""
    css = chrome._DESIGN_TOKENS
    assert '  --bg:            light-dark(oklch(97.2% 0.012 80),  oklch(16.4% 0.012 260));' in css
    assert '  --accent-primary: light-dark(oklch(38.0% 0.020 260), oklch(78.0% 0.015 260));' in css
    assert '  --c-other:       light-dark(oklch(64.0% 0.000 0),   oklch(75.0% 0.000 0));' in css
    assert '  --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px; --sp-4: 16px;' in css  # multi-decl line


# --- H-20: layout literals come from [layout] and land verbatim ---------------

def test_layout_literals_preserved():
    c = chrome._CHROME_CSS
    assert '.bar { display: flex; height: 18px;' in c
    assert 'line-height: 18px;' in c
    assert 'width: 80px; height: 6px;' in c
    assert 'min-height: 88px;' in c
    assert 'minmax(150px, 1fr)' in c
    assert 'minmax(180px, 1fr)' in c
    assert 'grid-template-columns: minmax(240px, 1fr) 2fr 90px;' in c
    assert 'minmax(360px, 1fr)' in c
    s = chrome._STICKY_CSS
    assert 'body { --hdr-offset: 120px; --crumb-h: 36px; }' in s
    assert 'grid-template-columns: minmax(140px, max-content) 1fr auto;' in s


def test_c16_polish_css_present():
    """c16 adds the insight-callout + empty-state primitives + a token-only ruleset (no $ left)."""
    c = chrome._CHROME_CSS
    assert '.callout {' in c and '.callout.sev-alarm {' in c
    assert '.empty-state {' in c
    assert 'footer.legend' not in c          # D-11b dead rule removed
    assert '$' not in c


def test_sparkline_defaults_from_tokens():
    assert delta.sparkline_svg.__defaults__ == (60, 14)
    assert _tokens.layout()['sparkline_w'] == 60
    assert _tokens.layout()['sparkline_h'] == 14


# --- loader contract ----------------------------------------------------------

def test_subst_keys_are_identifiers_and_cover_every_placeholder():
    subst = _tokens.token_subst()
    for k in subst:
        assert k.isidentifier(), k
    placeholders = set(re.findall(r'\$\{(\w+)\}', chrome._DESIGN_TOKENS_TMPL))
    assert placeholders <= set(subst)
    layout_ph = set(re.findall(r'\$\{(\w+)\}', chrome._CHROME_CSS_TMPL + chrome._STICKY_CSS_TMPL))
    assert layout_ph <= set(_tokens.layout_subst())


def test_toml_is_ascii_and_self_describing():
    text = _tokens.tokens_toml_text()
    assert text.startswith('# BobFrames design tokens')
    text.encode('ascii')  # project discipline: no em-dash / smart quote in shipped text


# --- export-tokens verb (DESIGNER Track A) ------------------------------------

def _run_cli(*args):
    env = {k: v for k, v in os.environ.items() if k != 'BOBFRAMES_CONFIG'}
    return subprocess.run([sys.executable, '-m', 'bobframes.cli', *args],
                          capture_output=True, text=True, env=env)


def test_export_tokens_json_round_trips():
    r = _run_cli('export-tokens', '--format', 'json')
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == _tokens.load_tokens()


def test_export_tokens_css_matches_emitted_root():
    r = _run_cli('export-tokens', '--format', 'css')
    assert r.returncode == 0, r.stderr
    assert r.stdout.replace('\r\n', '\n').strip() == chrome.design_tokens_css().strip()


def test_export_tokens_toml_is_verbatim():
    r = _run_cli('export-tokens', '--format', 'toml')
    assert r.returncode == 0, r.stderr
    assert r.stdout.replace('\r\n', '\n') == _tokens.tokens_toml_text()


# --- preview verb -------------------------------------------------------------

def test_preview_matches_golden(tmp_path):
    out = u.render_preview(str(tmp_path / 'root'))
    with open(out, encoding='utf-8') as f:
        actual = f.read()
    with open(u.GOLDEN_PREVIEW, encoding='utf-8') as f:
        golden = f.read()
    assert actual == golden, 'preview drifted from golden (refresh: python -m bobframes.tests.make_preview_golden)'


def test_preview_is_deterministic(tmp_path):
    a = open(u.render_preview(str(tmp_path / 'a')), encoding='utf-8').read()
    b = open(u.render_preview(str(tmp_path / 'b')), encoding='utf-8').read()
    assert a == b  # no build timestamp / nondeterminism
    for marker in ('chrome preview', 'kpi-strip', 'bar-row', 'class="spark"'):
        assert marker in a
