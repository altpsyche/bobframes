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
    # v0.2.6-1a (ADR-44): chrome neutralized to chroma-0 grayscale (shadcn). bg + accent-primary changed
    # in-commit; --c-other was already neutral gray (kept) so its pin is unchanged.
    assert '  --bg:            light-dark(oklch(100% 0 0), oklch(14.5% 0 0));' in css
    assert '  --accent-primary: light-dark(oklch(20.5% 0 0), oklch(92.2% 0 0));' in css
    assert '  --c-other:       light-dark(oklch(64.0% 0.000 0),   oklch(75.0% 0.000 0));' in css
    assert '  --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px; --sp-4: 16px;' in css  # multi-decl line


# --- H-20: layout literals come from [layout] and land verbatim ---------------

def test_layout_literals_preserved():
    c = chrome._CHROME_CSS
    assert '.bar { display: flex; height: 18px;' in c
    assert 'line-height: 18px;' in c
    assert 'width: 80px; height: 6px;' in c
    assert 'min-height: 88px;' in c
    assert 'minmax(170px, 1fr)' in c  # v0.2.6-1a: kpi_strip_min 150 -> 170 (hero numeral headroom)
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


def test_c16b_chart_block_present():
    """c16b adds the [chart] token block (sizes + var() palette) consumed by reports/charts.py."""
    ch = _tokens.chart()
    assert ch, 'design_tokens.toml missing [chart] block'
    for k in ('width', 'height', 'donut', 'bar_h', 'gap', 'pad', 'series_color', 'palette'):
        assert k in ch, f'[chart] missing {k}'
    assert isinstance(ch['width'], int) and isinstance(ch['palette'], list)
    # [chart] is NOT a :root section -> it must never leak into the substituted CSS tokens.
    assert 'series_color' not in chrome._DESIGN_TOKENS


def test_c16b_chart_css_present():
    """c16b adds the chart wrapper CSS (figure.chart / .chart-svg / details.secondary-metrics)."""
    c = chrome._CHROME_CSS
    assert 'figure.chart {' in c
    assert '.chart-svg {' in c
    assert 'details.secondary-metrics {' in c
    assert '$' not in c


def test_c16c_section_card_css_present():
    """c16c adds section-card framing + table-caption CSS (consumed by chrome.section_card across
    every report) and the dashboard small-multiple subtitle/chart rules."""
    c = chrome._CHROME_CSS
    assert 'section.card {' in c
    assert 'section.card > header {' in c
    assert '.card-subtitle {' in c
    # c16l (ADR-38): the table caption rule moved off the retired table.report onto the unified
    # table.data, which lives in the rdc-table engine CSS.
    assert 'table.data > caption {' in chrome._RDC_TABLE_CSS
    assert 'a.dash-card .dash-sub {' in c
    assert '$' not in c


def test_dashboard_mini_tables_fit_card():
    """Dashboard mini tables are teasers in a fixed-width card; pin table-layout:fixed + width:100% so a
    long label column can't push the table past the card and cut the rightmost column at the narrow grid
    width (regression guard). Numeric columns take a compact fixed width; text columns flex + clip."""
    c = chrome._CHROME_CSS
    assert 'a.dash-card table.data { table-layout: fixed; width: 100%; }' in c
    assert 'a.dash-card table.data th.num, a.dash-card table.data td.num { width: 5.5em; }' in c


def test_c16m_clip_contract_in_rdc_table_css():
    """c16m (ADR-38): controllable cell truncation lives in the one rdc-table engine CSS - tiered
    caps, the inner .clip element, the data-expand release. The DEFAULT td-clip (380px) is KEPT for the
    un-enhanced bare dashboard/preview minis; rdc-table cells opt OUT (truncate via the inner .clip).
    Literal var() (no $-template), ASCII (ellipsis via the CSS keyword)."""
    css = chrome._RDC_TABLE_CSS
    assert '--clip-cap:' in css and '--clip-cap-narrow:' in css and '--clip-cap-wide:' in css
    assert 'table.data .clip {' in css
    assert 'table.data .clip-narrow {' in css and 'table.data .clip-wide {' in css
    assert 'rdc-table[data-expand="true"] table.data .clip' in css
    assert 'max-width: 380px' in css                              # default td-clip for bare minis
    assert 'rdc-table table.data tbody td { max-width: none' in css   # rdc-table opts out (inner clip)
    assert '$' not in css and css.isascii()


def test_c16n_dashboard_mini_print_fullwrap():
    """c16n (ADR-38 tail): the bare dashboard/preview minis (table.data with NO rdc-table host) print
    CLIPPED on paper (the 380px td-clip + dash-card overflow:hidden, no title= hover in print). The print
    rule releases them to wrap in full - the mini analogue of the rdc-table static print full-wrap,
    co-located in the engine CSS with the 380px clip it releases. The .table-wrap > direct-child combinator
    targets the preview mini only (report tables interpose <rdc-table>)."""
    css = chrome._RDC_TABLE_CSS
    assert 'a.dash-card table.data th, a.dash-card table.data td,' in css
    assert '.table-wrap > table.data th, .table-wrap > table.data td {' in css
    assert css.isascii()


def test_c16d_shadow_and_motion_tokens_emitted():
    """c16d adds the [shadow] elevation block + spring/hover-scale motion tokens; they emit :root
    vars and are wired through token_subst (ADR-27/34). v0.2.6-1b RE-TUNES the elevations FLAT
    (reverses ADR-34): surfaces are now border-led, so elev-1 is the hairline contact ring ALONE
    (ambient blur dropped) and elev-2/3 keep only a whisper of drop for the dash-card hover lift."""
    css = chrome._DESIGN_TOKENS
    # exact emitted bytes (drill/root embed this UN-minified, so spacing is parity-significant); the
    # elevations are all-neutral-black for both themes, flat (ring + at most a whisper of drop)
    assert '  --elev-1: 0 0 0 1px oklch(0% 0 0 / 0.04);' in css
    assert '  --elev-2: 0 0 0 1px oklch(0% 0 0 / 0.04), 0 1px 2px oklch(0% 0 0 / 0.08);' in css
    assert '  --elev-3: 0 0 0 1px oklch(0% 0 0 / 0.05), 0 2px 6px oklch(0% 0 0 / 0.12);' in css
    assert '  --motion-spring: 220ms cubic-bezier(0.2, 0.8, 0.2, 1);' in css
    assert '  --hover-scale: 1.01;' in css
    # reduced-motion no-ops the lift: spring -> 0s, hover-scale -> 1 (static jump cannot survive)
    assert '    --motion-spring: 0s;' in css
    assert '    --hover-scale: 1;' in css
    # [shadow] is a :root section -> must be in the substitution map
    for k in ('elev_1', 'elev_2', 'elev_3'):
        assert k in _tokens.token_subst(), k


def test_c16d_depth_over_borders_css():
    """v0.2.6-1b (REVERSES ADR-34/c16d): cards/chrome read by a 1px --border + the --radius scale, NOT
    an elevation shadow. The dash-card is flat at rest and keeps only a whisper of elev on HOVER; the
    elev-1/elev-3 rest+heavy shadows are gone from the chrome bundle. The sticky-h2 ::before marker +
    the callout severity tint are unchanged; print still re-adds a paper border + kills shadow."""
    c = chrome._CHROME_CSS
    # border-led surfaces on the default radius (section.card / details), no rest elevation shadow
    assert 'border: 1px solid var(--border); border-radius: var(--radius);' in c
    assert 'box-shadow: var(--elev-1)' not in c      # the flat rest shadow is gone (border-led)
    assert 'box-shadow: var(--elev-3)' not in c      # the heavy hover shadow is gone
    # dash-card: flat at rest (border + the largest radius), a subtle elev lift only on :hover
    assert 'border: 1px solid var(--border); border-radius: var(--radius-lg);' in c
    assert 'box-shadow: var(--elev-2);' in c         # dash-card:hover keeps a whisper lift
    # severity tints the whole callout box (no border-left rule), keeping the icon accent
    assert 'color-mix(in oklch, var(--status-alarm) 11%, var(--surface-1))' in c
    assert 'border-left-color: var(--status-alarm)' not in c
    base = chrome._COMPONENTS_CSS_BASE
    assert 'rdc-sticky-h2 h2[aria-current="section"]::before' in base
    assert "content: ''" in base
    # print: borderless+shadowless cards would vanish on paper -> thin rule re-added, shadows killed
    assert 'a.dash-card { border: 1px solid #888; }' in chrome._PRINT_CSS
    assert 'box-shadow: none;' in chrome._PRINT_CSS


def test_c16d_micro_interactions_pacing_dimming():
    """c16d-d: card hover lift (reduced-motion-safe via --hover-scale), resting affordance on the
    copy-button, bigger section-card padding, and a .dim utility for secondary data."""
    c = chrome._CHROME_CSS
    base = chrome._COMPONENTS_CSS_BASE
    # hover lift uses the --hover-scale var (reduced-motion -> 1) + spring easing (-> 0s)
    assert 'transform: scale(var(--hover-scale));' in c
    assert 'transform var(--motion-spring)' in c
    # pacing: section card padding bumped to --sp-6
    assert 'padding: var(--sp-6); margin: 0 0 var(--sp-6);' in c
    # secondary-data dim utility
    assert '.dim { color: var(--text-3); font-weight: 400; }' in c
    # resting affordance: copy-button carries a faint tint before hover
    assert 'background: color-mix(in oklch, var(--accent-primary) 7%, transparent);' in base


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
