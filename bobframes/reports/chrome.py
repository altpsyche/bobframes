"""Page chrome: CSS tokens, page open/close, header, KPI strip, section card, legend, footer."""

from __future__ import annotations

import base64 as _base64
import html as _html
import string as _string
from importlib.resources import files as _files

from . import formatters as _f
from . import _tokens
from ..derives import classifier as _classifier


# Vendored Inter subset (c16d, ADR-34): a Latin + tabular-figures subset of the Inter variable font
# (wght 400-600), baked into the wheel and inlined as a base64 @font-face data URI. Reports stay a
# single self-contained HTML file that renders identically on every OS with NO network (a CDN fetch
# would break offline + byte-determinism). The woff2 bytes are committed; base64 over fixed bytes is
# byte-stable on any machine. ASCII-only output (base64 alphabet) keeps the page lint clean. See
# reports/assets/README.md for provenance + the subset command, and Inter-OFL.txt for the licence.
_FONT_WOFF2_B64 = _base64.b64encode(
    _files('bobframes.reports').joinpath('assets', 'inter-subset.woff2').read_bytes()
).decode('ascii')
_FONT_FACE_CSS = (
    "\n@font-face{font-family:'Inter';"
    "src:url(data:font/woff2;base64," + _FONT_WOFF2_B64 + ") format('woff2');"
    "font-weight:400 600;font-style:normal;font-display:swap}\n"
)


# Design-token VALUES live in reports/design_tokens.toml (c08, H-15); this skeleton owns only the
# CSS var NAMES + layout/alignment. string.Template substitutes $key -> value (CSS uses no '$', so
# only our placeholders match). The @media reduced-motion reset (0s) is a fixed a11y behavior, not a
# designer token, so it stays literal. design_tokens_css() returns this UN-minified (template.py
# embeds it raw on the drill/root pages), so the inter-arg spacing here is parity-significant.
_DESIGN_TOKENS_TMPL = """
:root {
  color-scheme: light dark;

  --sp-1: ${sp_1};  --sp-2: ${sp_2};  --sp-3: ${sp_3}; --sp-4: ${sp_4};
  --sp-6: ${sp_6}; --sp-8: ${sp_8}; --sp-12: ${sp_12};

  --fs-display: ${fs_display};
  --fs-h1: ${fs_h1};  --fs-h2: ${fs_h2};  --fs-h3: ${fs_h3};
  --fs-body: ${fs_body};  --fs-mono: ${fs_mono};  --fs-small: ${fs_small};

  --motion-hover: ${motion_hover};
  --motion-focus: ${motion_focus};
  --motion-vt: ${motion_vt};
  --motion-disclosure: ${motion_disclosure};
  --motion-spring: ${motion_spring};
  --hover-scale: ${hover_scale};

  --elev-1: ${elev_1};
  --elev-2: ${elev_2};
  --elev-3: ${elev_3};

  --bg:            ${bg};
  --surface-0:     ${surface_0};
  --surface-1:     ${surface_1};
  --surface-2:     ${surface_2};
  --code-bg:       ${code_bg};

  --fg:            ${fg};
  --text-1:        ${text_1};
  --muted:         ${muted};
  --text-2:        ${text_2};
  --text-3:        ${text_3};

  --border:        ${border};
  --border-1:      ${border_1};
  --border-strong: ${border_strong};
  --border-2:      ${border_2};

  --row-alt:       ${row_alt};
  --row-hover:     ${row_hover};

  --accent-primary: ${accent_primary};
  --accent-data:    ${accent_data};
  --accent:         ${accent};

  --status-alarm: ${status_alarm};
  --status-warn:  ${status_warn};
  --status-ok:    ${status_ok};
  --status-info:  ${status_info};

  --c-opaque:      ${c_opaque};
  --c-prepass:     ${c_prepass};
  --c-translucent: ${c_translucent};
  --c-additive:    ${c_additive};
  --c-decal:       ${c_decal};
  --c-shadow:      ${c_shadow};
  --c-ui:          ${c_ui};
  --c-postprocess: ${c_postprocess};
  --c-other:       ${c_other};

  --pos:     ${pos};
  --neg:     ${neg};
  --neutral: ${neutral};
}
@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-hover: 0s;
    --motion-focus: 0s;
    --motion-vt: 0s;
    --motion-disclosure: 0s;
    --motion-spring: 0s;
    --hover-scale: 1;
  }
}
"""

_DESIGN_TOKENS = _string.Template(_DESIGN_TOKENS_TMPL).substitute(_tokens.token_subst())


_CHROME_CSS_TMPL = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--surface-0); color: var(--text-1); }
body {
  padding: var(--sp-6) var(--sp-6) var(--sp-12);
  font: var(--fs-body)/1.5 'Inter', 'Segoe UI', system-ui, sans-serif;
  max-width: 1600px;
  margin: 0 auto;
}

h1 {
  font-size: var(--fs-h1); font-weight: 600; color: var(--accent);
  margin: 0 0 var(--sp-2); padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--border-2);
  letter-spacing: -0.01em;
}
h2 {
  font-size: var(--fs-h2); font-weight: 600; color: var(--text-1);
  margin: var(--sp-6) 0 var(--sp-3);
  position: relative;
  line-height: 1.4;
  scroll-margin-top: 64px;
}
h2:first-of-type { margin-top: 0; }
section[id], h2[id] { scroll-margin-top: 64px; }
h2[id]:target { color: var(--accent); }
h3 {
  font-size: var(--fs-h3); font-weight: 500; color: var(--text-2);
  margin: var(--sp-3) 0 var(--sp-2);
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; text-decoration-thickness: 2px; }
a:visited { color: var(--text-2); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

header.strip {
  display: flex; flex-wrap: wrap; gap: var(--sp-3) var(--sp-6);
  align-items: baseline;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--border-2);
  margin: 0 0 var(--sp-4);
}
header.strip span { color: var(--text-2); font-size: var(--fs-small); }
header.strip span strong { color: var(--text-1); font-weight: 600; }

nav.crumb {
  font-size: var(--fs-small);
  color: var(--text-2);
  margin: 0 0 var(--sp-3);
  display: flex; flex-wrap: wrap; gap: var(--sp-2);
  align-items: center;
}
nav.crumb a, nav.crumb a[data-link-kind] {
  display: inline-flex; align-items: center; gap: 4px;
  color: var(--accent-primary);
  text-decoration: none;
  padding: 2px 8px;
  border: 1px solid var(--border-1);
  border-radius: 2px;
  background: var(--surface-1);
  transition: border-color var(--motion-hover), background var(--motion-hover);
}
nav.crumb a:hover, nav.crumb a[data-link-kind]:hover {
  border-color: var(--accent-primary);
  background: var(--row-hover);
  text-decoration: none;
}
nav.crumb a + a::before { content: ''; }

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(${kpi_strip_min}, 1fr));
  gap: var(--sp-3);
  margin: 0 0 var(--sp-8);
}
.kpi-chip {
  background: var(--surface-1);
  box-shadow: var(--elev-1);
  border-radius: 4px;
  padding: var(--sp-3) var(--sp-4);
  display: flex; flex-direction: column; gap: var(--sp-1);
  min-height: ${kpi_min_height};
}
.kpi-chip .kpi-label {
  font: var(--fs-small) ui-monospace, monospace;
  color: var(--text-3);
  text-transform: lowercase;
  letter-spacing: 0.04em;
}
.kpi-chip .kpi-value {
  font: 600 var(--fs-display)/1.05 'Inter', 'Segoe UI', system-ui, sans-serif;
  color: var(--text-1);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.kpi-chip .kpi-delta {
  font: var(--fs-small) ui-monospace, monospace;
  font-variant-numeric: tabular-nums;
  color: var(--text-3);
}
.kpi-chip.tone-pos .kpi-value, .kpi-chip.tone-pos .kpi-delta { color: var(--pos); }
.kpi-chip.tone-neg .kpi-value, .kpi-chip.tone-neg .kpi-delta { color: var(--neg); }

.table-wrap {
  overflow-x: auto;
  margin: 0 0 var(--sp-6);
}
.table-wrap > rdc-table > table.data { border: 0; margin: 0; }

nav.toc {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(${toc_min}, 1fr));
  gap: var(--sp-1) var(--sp-3);
  font: var(--fs-mono) ui-monospace, monospace;
  margin: 0 0 var(--sp-6);
  padding: var(--sp-2) var(--sp-3);
  background: var(--surface-2);
  border: 1px solid var(--border-1);
}
nav.toc a { display: inline-block; padding: 2px 0; }

.bar-row {
  display: grid;
  grid-template-columns: ${bar_row_cols};
  gap: var(--sp-3);
  align-items: center;
  padding: 4px 0;
  font: var(--fs-mono) ui-monospace, 'Cascadia Code', Consolas, monospace;
}
.bar-row .key { white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
                font-weight: 600; color: var(--text-1); }
.bar-row .total { text-align: right; font-variant-numeric: tabular-nums;
                  color: var(--text-2); }
.bar { display: flex; height: ${bar_height}; background: var(--surface-2);
       border: 1px solid var(--border-1); overflow: hidden; }
.bar .seg { flex: 0 0 auto; color: #fff; font-size: 10px; line-height: ${bar_height};
            text-align: center; overflow: hidden; white-space: nowrap; }

/* Inline-SVG charts (c16b, ADR-33): flagship viz above each report table. */
figure.chart { margin: 0 0 var(--sp-4); max-width: 720px; }
figure.chart figcaption { font-size: var(--fs-small); color: var(--text-2);
                          margin: 0 0 var(--sp-2); }
.chart-svg { display: block; width: 100%; height: auto;
             background: var(--surface-1);
             border-radius: 4px; }
.chart-svg text { font: var(--fs-small) ui-monospace, monospace; fill: var(--text-2); }
details.secondary-metrics { margin: var(--sp-2) 0 var(--sp-4); }
details.secondary-metrics > summary { cursor: pointer; color: var(--text-2);
                                      font-size: var(--fs-small); padding: var(--sp-1) 0; }

/* Section cards (c16c/c16d): each report section is ONE card raised off the page by surface +
   elevation shadow (depth over borders, ADR-34). The card is the SINGLE frame - inner table-wraps
   go borderless/flush so we never stack box-in-box. The leading h2 no longer carries an --accent
   left-rule; the sticky-h2 in-view highlight is now a ::before marker (see _COMPONENTS_CSS_BASE). */
section.card {
  background: var(--surface-1);
  box-shadow: var(--elev-1); border-radius: 4px;
  padding: var(--sp-6); margin: 0 0 var(--sp-6);
}
section.card > header {
  display: flex; align-items: baseline; gap: var(--sp-3);
  margin: 0 0 var(--sp-4);
}
section.card > header > h2 { margin: 0; }
section.card > :last-child { margin-bottom: 0; }
section.card .table-wrap { border: 0; border-radius: 0; margin: 0; }
.card-count {
  font: 600 var(--fs-small) ui-monospace, monospace; color: var(--text-2);
  background: var(--surface-2); padding: 1px 8px; border-radius: 3px;
}
.card-subtitle { margin: 0 0 var(--sp-4); color: var(--text-2); font-size: var(--fs-small); }

.ibar {
  display: inline-block; width: ${ibar_width}; height: ${ibar_height};
  background: var(--surface-2); border: 1px solid var(--border-1);
  vertical-align: middle; margin-left: 6px;
}
.ibar > div { height: 100%; background: var(--accent); }

.delta { font-variant-numeric: tabular-nums; padding: 2px var(--sp-2);
         text-align: right; }
.delta-pill {
  display: inline-block; padding: 1px 6px; border-radius: 2px;
  background: var(--surface-2);
  font: 600 var(--fs-small) ui-monospace, monospace;
}
.delta.pos, .delta-pill.pos { color: var(--pos); font-weight: 600; }
.delta.neg, .delta-pill.neg { color: var(--neg); font-weight: 600; }
.delta.flat, .delta-pill.flat { color: var(--text-3); }
.delta.new, .delta-pill.new { color: var(--text-3); font-style: italic; }
.delta.alarm { background: color-mix(in oklch, var(--status-alarm) 14%, transparent);
               border-radius: 2px; }
.delta-latest { border-left: 2px solid var(--border-2); }

.legend { display: flex; flex-wrap: wrap; gap: var(--sp-2) var(--sp-4);
          margin: 0 0 var(--sp-3);
          font-size: var(--fs-small); color: var(--text-2); }
.legend .chip { display: inline-flex; align-items: center; gap: 6px; }
.legend .swatch { display: inline-block; width: 12px; height: 12px;
                  border-radius: 2px; }

.device-strip {
  font: var(--fs-small) ui-monospace, monospace;
  color: var(--text-2);
  background: var(--surface-2);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--border-1);
  margin: 0 0 var(--sp-4);
}
.ab-strip {
  font: var(--fs-small) ui-monospace, monospace;
  color: var(--text-2);
  background: var(--surface-2);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--border-2);
  margin: 0 0 var(--sp-4);
}

.rank {
  display: inline-block; width: 1.4em; text-align: center;
  font: 600 var(--fs-small) ui-monospace, monospace;
  margin-right: var(--sp-1);
  color: var(--text-3);
}
.rank.rank-1 { color: var(--accent); }
.rank.rank-2 { color: var(--text-1); }
.rank.rank-3 { color: var(--text-2); }

details.matrix, details.category {
  margin: 0 0 var(--sp-4);
  background: var(--surface-1);
  box-shadow: var(--elev-1); border-radius: 4px;
}
details.matrix > summary, details.category > summary {
  cursor: pointer; list-style: none; user-select: none;
  padding: var(--sp-3) var(--sp-4);
  font: 600 var(--fs-body) 'Inter', system-ui, sans-serif;
  color: var(--accent);
  border-bottom: 1px solid transparent;
  display: flex; justify-content: space-between; align-items: baseline;
  gap: var(--sp-3);
}
details.matrix[open] > summary, details.category[open] > summary {
  border-bottom-color: var(--border-1);
}
details > summary::-webkit-details-marker { display: none; }
details.matrix > summary::before, details.category > summary::before {
  content: '+'; margin-right: var(--sp-2);
  font-family: ui-monospace, monospace; color: var(--text-3);
  display: inline-block; width: 0.8em;
}
details[open] > summary::before { content: '-'; }
details.matrix > .matrix-body, details.category > .cat-body {
  padding: var(--sp-4);
}
.cat-meta { font: var(--fs-small) ui-monospace, monospace;
            color: var(--text-3); font-variant-numeric: tabular-nums; }
.spark { display: inline-block; vertical-align: middle; color: var(--text-2); }

.note { font-size: var(--fs-small); color: var(--text-2);
        margin-top: var(--sp-2); }
/* Secondary data (c16d): dim drop-keys / dates / raw counts to the tertiary tone so the actionable
   columns (cost proxy, wasted indices, reject %) carry the eye. Overrides an accent-coloured th. */
.dim { color: var(--text-3); font-weight: 400; }

.callout {
  display: flex; align-items: flex-start; gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4); margin: 0 0 var(--sp-4);
  background: var(--surface-1); border-radius: 4px;
  font-size: var(--fs-small);
}
.callout .icon { flex: 0 0 auto; margin-top: 2px; color: var(--text-3); }
.callout .co-body { display: flex; flex-direction: column; gap: 2px; }
.callout .co-title { font-weight: 600; color: var(--text-1); }
.callout .co-detail { color: var(--text-2); }
.callout a { color: var(--accent-primary); }
.callout.sev-ok { background: color-mix(in oklch, var(--status-ok) 9%, var(--surface-1)); }
.callout.sev-ok .icon { color: var(--status-ok); }
.callout.sev-warn { background: color-mix(in oklch, var(--status-warn) 9%, var(--surface-1)); }
.callout.sev-warn .icon { color: var(--status-warn); }
.callout.sev-alarm { background: color-mix(in oklch, var(--status-alarm) 11%, var(--surface-1)); }
.callout.sev-alarm .icon { color: var(--status-alarm); }

.empty-state {
  display: flex; align-items: center; gap: var(--sp-2);
  padding: var(--sp-4); margin: 0 0 var(--sp-4);
  color: var(--text-2); font-size: var(--fs-small);
  background: var(--surface-1); border: 1px dashed var(--border-1);
}
.empty-state .icon { flex: 0 0 auto; color: var(--text-3); }

.dash-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(${dash_grid_min}, 1fr));
  gap: var(--sp-6);
  margin: 0 0 var(--sp-6);
}
a.dash-card { background: var(--surface-1); box-shadow: var(--elev-2); border-radius: 4px;
              padding: var(--sp-4); display: flex; flex-direction: column;
              gap: var(--sp-3); text-decoration: none; color: inherit;
              transition: box-shadow var(--motion-hover), background var(--motion-hover),
                          transform var(--motion-spring); }
a.dash-card:hover { background: var(--surface-2); box-shadow: var(--elev-3);
                    transform: scale(var(--hover-scale)); text-decoration: none; }
a.dash-card:visited { color: inherit; }
a.dash-card h3 { margin: 0; color: var(--accent); font-size: var(--fs-h2); }
a.dash-card table.data { font-size: var(--fs-small); }
a.dash-card table.data a { pointer-events: none; }
/* Dashboard mini tables are teasers inside a fixed-width card; the default `width:max-content` lets a
   long label column push the table past the card (cutting the rightmost column at the narrow 3-up grid
   width). Pin the layout to the card: table-layout:fixed + width:100% so it never overflows; the numeric
   columns take a compact fixed width and the text/label columns flex to fill the rest (roomy when the
   card is wide, clean ellipsis when narrow). Both th + td clip so a long header/value never spills. */
a.dash-card table.data { table-layout: fixed; width: 100%; }
a.dash-card table.data th, a.dash-card table.data td {
  overflow: hidden; text-overflow: ellipsis;
}
a.dash-card table.data th.num, a.dash-card table.data td.num { width: 5.5em; }
a.dash-card .dash-sub { margin: 0; color: var(--text-2); font-size: var(--fs-small); }
/* dashboard small-multiple: the card is the frame, so the mini chart blends in (no boxed panel,
   no box-in-box against the borderless summary table below it) - c16c. */
a.dash-card figure.chart { margin: 0; max-width: none; }
a.dash-card .chart-svg { background: transparent; border: 0; border-radius: 0; }
"""

_CHROME_CSS = _string.Template(_CHROME_CSS_TMPL).substitute(_tokens.layout_subst())


_STICKY_CSS_TMPL = """
/* Sticky stack: crumb (top:0) -> summary-bar (top:crumb-h) -> thead (top:hdr-offset).
   --hdr-offset is the combined height of crumb + summary-bar (pages set per page).
   --crumb-h is the crumb height alone. Defaults work for most pages.
   h2 is NOT sticky: the cascading sticky h2 + thead + summary-bar over-stacks
   on long multi-section pages. Sticky thead is sufficient for table reading. */
body { --hdr-offset: ${hdr_offset}; --crumb-h: ${crumb_height}; }
nav.crumb {
  position: sticky; top: 0; z-index: 3;
  background: var(--bg);
  padding-top: var(--sp-1); padding-bottom: var(--sp-1);
}
.summary-bar {
  position: sticky; top: var(--crumb-h); z-index: 3;
  display: grid;
  grid-template-columns: ${summary_bar_cols};
  gap: var(--sp-2) var(--sp-6);
  align-items: center;
  background: var(--surface-1);
  box-shadow: var(--elev-2);
  border-top: 2px solid var(--accent-data);
  border-radius: 4px;
  padding: var(--sp-3) var(--sp-4);
  margin: 0 0 var(--sp-4);
}
.summary-bar .sb-label {
  font: var(--fs-small) ui-monospace, monospace;
  color: var(--text-2);
  text-transform: lowercase;
  letter-spacing: 0.04em;
}
.summary-bar .sb-headline {
  font: 600 var(--fs-h1)/1.15 'Inter', 'Segoe UI', system-ui, sans-serif;
  color: var(--text-1);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}
.summary-bar .sb-sub {
  font: var(--fs-small) ui-monospace, monospace;
  color: var(--text-2);
  grid-column: 2;
  font-variant-numeric: tabular-nums;
}
.summary-bar .sb-link { align-self: center; grid-row: 1 / span 2; grid-column: 3; }
.summary-bar.tone-alarm { border-top-color: var(--status-alarm); }
.summary-bar.tone-ok { border-top-color: var(--status-ok); }
.summary-bar.tone-warn { border-top-color: var(--status-warn); }
.summary-bar.tone-info { border-top-color: var(--status-info); }
"""

_STICKY_CSS = _string.Template(_STICKY_CSS_TMPL).substitute(_tokens.layout_subst())


_LINK_KIND_CSS = """
a[data-link-kind="primary"] {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 6px 12px;
  background: var(--surface-1);
  border: 1px solid var(--border-2);
  color: var(--accent-primary);
  text-decoration: none;
  transition: background var(--motion-hover), border-color var(--motion-hover);
}
a[data-link-kind="primary"]:hover {
  background: var(--row-hover);
  border-color: var(--accent-primary);
  text-decoration: none;
}
a[data-link-kind="primary"]:visited { color: var(--accent-primary); }

a[data-link-kind="inline"] {
  color: var(--accent-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
  text-decoration-thickness: 1px;
}
a[data-link-kind="inline"]:hover { text-decoration-thickness: 2px; }
a[data-link-kind="inline"] .icon {
  margin-left: 3px;
  color: var(--text-2);
}

a[data-link-kind="drill"] {
  color: var(--text-1);
  text-decoration: underline;
  text-decoration-color: var(--border-2);
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}
a[data-link-kind="drill"]:hover {
  color: var(--accent-primary);
  text-decoration-color: var(--accent-primary);
  text-decoration-thickness: 2px;
}
tr:has(a[data-link-kind="drill"]):hover td { background: var(--row-hover); }

a[data-link-kind="copy"] {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px; height: 24px;
  color: var(--text-2);
  text-decoration: none;
  border-radius: 2px;
  transition: color var(--motion-hover), background var(--motion-hover);
}
a[data-link-kind="copy"]:hover {
  color: var(--accent-primary);
  background: var(--row-hover);
}

a[data-link-kind="crumb"] {
  color: var(--text-2);
  text-decoration: none;
}
a[data-link-kind="crumb"]:hover {
  color: var(--accent-primary);
  text-decoration: underline;
}

.icon {
  width: 11px; height: 11px;
  display: inline-block;
  vertical-align: -1px;
  fill: currentColor;
}
"""


_ICON_SPRITE = """
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <defs>
    <symbol id="icon-link-out" viewBox="0 0 16 16">
      <path d="M4 4h5v1H5v6h6V8h1v3.5a.5.5 0 0 1-.5.5h-7a.5.5 0 0 1-.5-.5v-7a.5.5 0 0 1 .5-.5z"/>
      <path d="M11 5L7.5 8.5M11 5h-3M11 5v3" stroke="currentColor" fill="none" stroke-width="1"/>
    </symbol>
    <symbol id="icon-file" viewBox="0 0 16 16">
      <path d="M4 2h5l3 3v9H4z" stroke="currentColor" fill="none" stroke-width="1"/>
      <path d="M9 2v3h3" stroke="currentColor" fill="none" stroke-width="1"/>
    </symbol>
    <symbol id="icon-arrow-right" viewBox="0 0 16 16">
      <path d="M4 8h8M9 5l3 3-3 3" stroke="currentColor" fill="none" stroke-width="1.5"/>
    </symbol>
    <symbol id="icon-copy" viewBox="0 0 16 16">
      <path d="M5 5h7v8H5z" stroke="currentColor" fill="none" stroke-width="1"/>
      <path d="M3 3h7v2" stroke="currentColor" fill="none" stroke-width="1"/>
    </symbol>
    <symbol id="icon-search" viewBox="0 0 16 16">
      <circle cx="7" cy="7" r="4" stroke="currentColor" fill="none" stroke-width="1.5"/>
      <path d="M10 10l3 3" stroke="currentColor" stroke-width="1.5"/>
    </symbol>
    <symbol id="icon-warn" viewBox="0 0 16 16">
      <path d="M8 2l6 11H2L8 2zM8 7v3M8 11.5v.5" stroke="currentColor" fill="none" stroke-width="1"/>
    </symbol>
  </defs>
</svg>
"""


_CONTAINER_CSS = """
body { container-type: inline-size; container-name: page; }

@container page (max-width: 1100px) {
  nav.toc { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
}

@container page (max-width: 860px) {
  .dash-grid { grid-template-columns: 1fr; }
  .summary-bar { grid-template-columns: 1fr auto; }
  .summary-bar .sb-sub { grid-column: 1; }
  .summary-bar .sb-link { grid-row: auto; grid-column: 2; }
  .summary-bar .sb-headline { font-size: var(--fs-h1); }
}

@container page (max-width: 768px) {
  .bar-row {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
    gap: var(--sp-1);
  }
  .bar-row .total { text-align: left; }
  .kpi-strip { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
  .kpi-chip .kpi-value { font-size: var(--fs-h1); }
  body { padding: var(--sp-3); }
  .summary-bar .sb-headline { font-size: var(--fs-h2); }
}
"""


_PRINT_CSS = """
@media print {
  @page { size: A4; margin: 12mm; }
  :root { color-scheme: light; }
  html, body { background: #fff; color: #000; }
  body { max-width: none; padding: 0; }

  nav.crumb, .device-strip, .ab-strip,
  rdc-copy-button, rdc-search-cards, rdc-ab-picker { display: none; }

  .summary-bar {
    position: static;
    background: #fff;
    border: 1px solid #888;
    border-top-width: 3px;
    break-inside: avoid;
    break-after: avoid;
    print-color-adjust: exact;
  }
  .summary-bar .sb-headline { color: #000; }
  .summary-bar .sb-link { display: none; }

  /* Depth -> paper (c16d): screen depth is shadow-only and borderless; on white paper that is
     invisible, so re-add a thin rule and kill shadows for every carded element. */
  section.card, .callout, .kpi-chip, .pair-group,
  details.matrix, details.category, a.dash-card { border: 1px solid #888; }
  section.card, .callout, .kpi-chip, .pair-group, details.matrix, details.category,
  a.dash-card, .summary-bar, .chart-svg { box-shadow: none; }

  h1, h2 { color: #000; }
  h2[id] { position: static; background: transparent; break-after: avoid; }

  .kpi-strip { break-inside: avoid; grid-template-columns: repeat(4, 1fr); }
  .kpi-chip { background: #fff; }
  .kpi-chip .kpi-value { color: #000; }

  .dash-grid { grid-template-columns: repeat(2, 1fr); }
  a.dash-card { break-inside: avoid; }

  .bar, .bar .seg, .ibar, .ibar > div,
  .legend .swatch, .delta.pos, .delta.neg, .delta-pill {
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }

  details, details > summary { display: block; }
  details > .matrix-body, details > .cat-body { display: block; }

  a[data-link-kind="primary"] {
    background: transparent;
    border: 1px solid #888;
    color: #000;
  }
  a[data-link-kind="inline"] { color: #000; }
  a[data-link-kind="inline"] .icon { display: none; }

  /* Multi-section trend_table: page break before each h2 section after the first */
  body[data-multi-section="true"] h2[id] ~ h2[id] { break-before: page; }

  /* Per-drop browser: too large for print; show fallback message */
  body[data-page-kind="drop-browser"] > * { display: none; }
  body[data-page-kind="drop-browser"]::before {
    content: "Per-drop browser is not designed for print. See the cumulative reports.";
    display: block;
    padding: 20mm;
    font: bold 1.2rem system-ui, sans-serif;
    color: #000;
  }
}
"""


_COMPONENTS_CSS_BASE = """
rdc-copy-button {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 28px; padding: 0 6px; height: 22px;
  color: var(--text-2);
  cursor: pointer;
  /* resting affordance (c16d): a faint tint so it reads as clickable before hover */
  background: color-mix(in oklch, var(--accent-primary) 7%, transparent);
  border: 1px solid transparent;
  border-radius: 2px;
  font: var(--fs-small) ui-monospace, monospace;
  margin-left: 4px;
  transition: color var(--motion-hover), background var(--motion-hover), border-color var(--motion-hover);
}
rdc-copy-button:hover {
  color: var(--accent-primary);
  background: var(--row-hover);
  border-color: var(--border-1);
}
rdc-copy-button:focus-visible { outline: 2px solid var(--accent-primary); outline-offset: 1px; }
rdc-copy-button::before { content: 'copy'; }
rdc-copy-button.copied { color: var(--status-ok); border-color: var(--status-ok); }
rdc-copy-button.copied::before { content: 'ok'; }

rdc-heatmap-cell {
  display: inline-block;
  padding: 1px 4px;
  border-radius: 2px;
  font-variant-numeric: tabular-nums;
}

rdc-sticky-h2 { display: contents; }
/* In-view cue (c16d): the h2 lost its --accent left-rule, so the active section is marked by a
   leading accent bar that appears only while the section's h2 sits in the viewport mid-band. The JS
   (RdcStickyH2) toggles aria-current="section"; content:'' is ASCII (lint-safe). */
rdc-sticky-h2 h2[aria-current="section"]::before {
  content: ''; position: absolute;
  left: calc(-1 * var(--sp-3)); top: 0.2em; bottom: 0.2em;
  width: 3px; border-radius: 2px; background: var(--accent-data);
}

rdc-row-drill { display: contents; }
rdc-row-drill > tr { cursor: pointer; }
rdc-row-drill > tr:hover td { background: var(--row-hover); }

rdc-search-cards {
  display: flex; align-items: center; gap: var(--sp-3);
  margin: 0 0 var(--sp-4);
  font: var(--fs-small) ui-monospace, monospace;
}
rdc-search-cards input[type="search"] {
  font: inherit;
  padding: 6px 10px;
  border: 1px solid var(--border-1);
  background: var(--surface-0);
  color: var(--text-1);
  border-radius: 2px;
  min-width: 280px;
}
rdc-search-cards input[type="search"]:focus {
  outline: 2px solid var(--accent-primary);
  outline-offset: 1px;
}
rdc-search-cards .rdc-count {
  color: var(--text-2);
  font-variant-numeric: tabular-nums;
}

rdc-ab-picker {
  display: inline-flex; align-items: center; gap: var(--sp-2);
  margin: 0 0 var(--sp-4);
  font: var(--fs-small) ui-monospace, monospace;
}
rdc-ab-picker label { color: var(--text-2); }
rdc-ab-picker select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--border-1);
  background: var(--surface-0);
  color: var(--text-1);
  border-radius: 2px;
}

rdc-alarm-banner { display: contents; }

/* Chip cluster: wrap N primary chips in flex row, no table abuse */
.chip-cluster {
  display: flex; flex-wrap: wrap; gap: var(--sp-2);
  margin: 0 0 var(--sp-4);
}
.chip-cluster a[data-link-kind="primary"] { padding: 4px 10px; font-size: var(--fs-small); }

/* Pair list: grouped variant chips per A/B pair */
.pair-list { display: flex; flex-direction: column; gap: var(--sp-4); margin: 0 0 var(--sp-6); }
.pair-group { box-shadow: var(--elev-1); border-radius: 4px; padding: var(--sp-3) var(--sp-4); background: var(--surface-1); }
.pair-group > h3 {
  margin: 0 0 var(--sp-3); padding: 0;
  font: var(--fs-mono) ui-monospace, monospace;
  color: var(--text-2);
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
}

/* Catalog grid: flex-wrap chip area for report shortcuts */
.catalog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--sp-2);
  margin: 0 0 var(--sp-6);
}
.catalog-grid a[data-link-kind="primary"] { justify-content: flex-start; }
"""


_COMPONENTS_JS_ALL = """
(function(){
  if (typeof customElements === 'undefined') return;

  class RdcBase extends HTMLElement {
    connectedCallback(){
      if (this._rdcUp) return;
      this._rdcUp = true;
      try { this.init(); } catch(e) { console.error('rdc init error', this.tagName, e); }
    }
    init(){}
  }

  class RdcCopyButton extends RdcBase {
    init(){
      const value = this.dataset.value || '';
      const label = this.dataset.label || ('copy ' + value);
      this.setAttribute('role', 'button');
      this.setAttribute('tabindex', '0');
      this.setAttribute('aria-label', label);
      const handler = async () => {
        try {
          await navigator.clipboard.writeText(value);
        } catch (e) {
          const ta = document.createElement('textarea');
          ta.value = value;
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand('copy'); } catch(e2){}
          ta.remove();
        }
        this.classList.add('copied');
        setTimeout(() => this.classList.remove('copied'), 1000);
      };
      this.addEventListener('click', handler);
      this.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' '){
          e.preventDefault();
          handler();
        }
      });
    }
  }
  customElements.define('rdc-copy-button', RdcCopyButton);

  class RdcStickyH2 extends RdcBase {
    init(){
      const h2 = this.querySelector('h2');
      if (!h2) return;
      const io = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting){
            h2.setAttribute('aria-current', 'section');
          } else {
            h2.removeAttribute('aria-current');
          }
        });
      }, { rootMargin: '-50% 0px -50% 0px', threshold: 0 });
      io.observe(h2);
    }
  }
  customElements.define('rdc-sticky-h2', RdcStickyH2);

  class RdcHeatmapCell extends RdcBase {
    init(){
      const v = parseFloat(this.dataset.value);
      const lo = parseFloat(this.dataset.min);
      const hi = parseFloat(this.dataset.max);
      const dir = this.dataset.direction || 'hot';
      if (isNaN(v) || isNaN(lo) || isNaN(hi) || hi <= lo) return;
      let t = (v - lo) / (hi - lo);
      if (dir === 'cold') t = 1 - t;
      t = Math.max(0, Math.min(1, t));
      const pct = Math.round(t * 25);
      this.style.background = 'color-mix(in oklch, var(--accent-data) ' + pct + '%, transparent)';
      if (t >= 0.72){
        this.style.color = 'light-dark(black, white)';
      }
      this.setAttribute('aria-label', v + ' (relative ' + Math.round(t * 100) + '%)');
    }
  }
  customElements.define('rdc-heatmap-cell', RdcHeatmapCell);

  class RdcRowDrill extends RdcBase {
    init(){
      const href = this.dataset.href;
      if (!href) return;
      this.setAttribute('role', 'link');
      this.setAttribute('tabindex', '0');
      this.style.cursor = 'pointer';
      const go = (ev) => {
        if (ev.target && ev.target.closest('a')) return;
        if (ev.target && ev.target.closest('rdc-copy-button')) return;
        window.location.href = href;
      };
      this.addEventListener('click', go);
      this.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter'){
          ev.preventDefault();
          window.location.href = href;
        }
      });
    }
  }
  customElements.define('rdc-row-drill', RdcRowDrill);

  class RdcSearchCards extends RdcBase {
    init(){
      const target = this.dataset.target || '.dash-grid';
      const cards = document.querySelectorAll(target + ' > *');
      const input = this.querySelector('input');
      if (!input || !cards.length) return;
      const counter = this.querySelector('.rdc-count');
      const update = () => {
        const q = input.value.trim().toLowerCase();
        let shown = 0;
        cards.forEach(c => {
          const text = (c.textContent || '').toLowerCase();
          const match = !q || text.indexOf(q) >= 0;
          c.style.display = match ? '' : 'none';
          if (match) shown++;
        });
        if (counter) counter.textContent = shown + ' / ' + cards.length;
      };
      input.addEventListener('input', update);
      update();
    }
  }
  customElements.define('rdc-search-cards', RdcSearchCards);

  class RdcAlarmBanner extends RdcBase {
    init(){
      const sev = this.dataset.severity || 'high';
      const role = sev === 'high' ? 'alert' : 'status';
      this.setAttribute('role', role);
      this.setAttribute('aria-live', sev === 'high' ? 'assertive' : 'polite');
    }
  }
  customElements.define('rdc-alarm-banner', RdcAlarmBanner);

  class RdcAbPicker extends RdcBase {
    init(){
      const select = this.querySelector('select');
      if (!select) return;
      this.setAttribute('role', 'combobox');
      select.addEventListener('change', () => {
        const url = select.value;
        if (url) window.location.href = url;
      });
    }
  }
  customElements.define('rdc-ab-picker', RdcAbPicker);

  // Whole-row drill: any <tr> containing <a data-link-kind="drill"> becomes clickable.
  function _wireRowDrill(){
    const seen = new WeakSet();
    document.querySelectorAll('a[data-link-kind="drill"]').forEach(a => {
      const tr = a.closest('tr');
      if (!tr || seen.has(tr)) return;
      seen.add(tr);
      tr.addEventListener('click', (ev) => {
        if (ev.target.closest('a')) return;
        if (ev.target.closest('rdc-copy-button')) return;
        a.click();
      });
      tr.style.cursor = 'pointer';
    });
  }
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', _wireRowDrill);
  } else {
    _wireRowDrill();
  }
})();
"""


_TOKENS_CSS = _DESIGN_TOKENS
# The @font-face leads the primitives so it ships on BOTH CSS paths: chrome page_open's _compose_css
# AND template.py's chrome_css() (drill/root). design_tokens_css() stays pure :root (test contract).
_PRIMITIVES_CSS = _FONT_FACE_CSS + _CHROME_CSS + _LINK_KIND_CSS + _STICKY_CSS + _CONTAINER_CSS + _PRINT_CSS
_COMPONENTS_CSS = _COMPONENTS_CSS_BASE
_COMPONENTS_JS = _COMPONENTS_JS_ALL


# Inline 16x16 SVG favicon (3-bar stack pattern) as data URL.
# Uses single quotes inside SVG so the data URL can be enclosed in
# href="..." without breaking the HTML attribute.
_FAVICON_HREF = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<rect x='2' y='3' width='12' height='2' fill='%23888'/>"
    "<rect x='2' y='7' width='12' height='2' fill='%234a8'/>"
    "<rect x='2' y='11' width='12' height='2' fill='%23d54'/>"
    "</svg>"
)


def _minify_css(s: str) -> str:
    """Strip CSS comments + collapse whitespace + drop blank lines.
    Conservative: preserves selectors and rule structure."""
    import re as _re
    s = _re.sub(r'/\*.*?\*/', '', s, flags=_re.DOTALL)
    s = _re.sub(r'\n\s*\n', '\n', s)
    s = _re.sub(r'^\s+', '', s, flags=_re.MULTILINE)
    s = _re.sub(r'\s*([{};:,])\s*', r'\1', s)
    s = _re.sub(r';}', '}', s)
    return s.strip()


def _minify_js(s: str) -> str:
    """Strip JS line comments + block comments + collapse leading whitespace.
    Conservative: preserves string literals (does not strip inside them naively)."""
    import re as _re
    # Strip block comments (greedy minimal)
    s = _re.sub(r'/\*.*?\*/', '', s, flags=_re.DOTALL)
    # Strip line comments (// to end of line) - careful with URLs (// in strings)
    # Use a heuristic: only strip lines whose // is preceded by whitespace at start of statement
    lines = []
    for line in s.split('\n'):
        # Drop line comments that begin a line (after whitespace)
        stripped = line.lstrip()
        if stripped.startswith('//'):
            continue
        lines.append(line.rstrip())
    s = '\n'.join(ln for ln in lines if ln)
    return s


def _compose_css() -> str:
    # c16l (ADR-38): the rdc-table engine is now ALWAYS-ON in the report bundle (was opt-in via
    # report_page(rdc_table=True) in c16k). Every report/dashboard/A-B/per-run page hosts a STATIC
    # rdc-table, so the engine CSS ships unconditionally. template.py composes its own bundle for
    # catalog/drill (it adds rdc_table_css() explicitly), so this fold does NOT double-include there.
    return _minify_css(_TOKENS_CSS + _PRIMITIVES_CSS + _COMPONENTS_CSS + _RDC_TABLE_CSS)


def _compose_js() -> str:
    return _minify_js(_COMPONENTS_JS + _RDC_TABLE_JS)


def design_tokens_css() -> str:
    """Return :root tokens CSS for reuse in template.py."""
    return _TOKENS_CSS


def chrome_css() -> str:
    """Return primitives + components CSS (without tokens). Used by template.py."""
    return _PRIMITIVES_CSS + _COMPONENTS_CSS


def components_js() -> str:
    """Return Web Components JS blob. Used by template.py."""
    return _COMPONENTS_JS


# ---------------------------------------------------------------------------
# rdc-table: the ONE bespoke table engine (c16k build + c16l rollout, ADR-38). It SUBSUMED both the
# old catalog/drill VTable and the reports' rdc-sortable-table (now deleted - G-23 fully resolved).
# Progressive-enhancement, two data-delivery modes picked by data-mode:
#   - virtual: rows stream from window.__data_<key> (_pagedata/*.js); the DOM is windowed (VTable).
#   - static : rows are SERVER-BAKED into <table class="data">; JS only enhances IN PLACE (sort
#              reorders existing <tr> nodes, heatmap tints existing <td>s, column-groups toggle
#              display) so JS-off / print / Ctrl-F all see every row (ADR-37 preserved).
# Bootstrapped from a single DOMContentLoaded pass (NOT customElements) so it dodges the parse-time
# connectedCallback footgun and matches today's VTable timing. Offline, byte-deterministic (NO
# random/Date/fetch in the rendered output), ASCII (the runtime ' ▲'/' ▼' textContent is tolerated,
# as in the old VTable). c16l folded the engine into the ALWAYS-ON shared bundle (_compose_css/
# _compose_js): every report/dashboard/A-B/per-run page hosts a STATIC rdc-table, so the opt-in is
# gone. template.py composes its own bundle for catalog/drill (it adds rdc_table_css()/rdc_table_js()
# explicitly), so the fold does not double-include there.
# ---------------------------------------------------------------------------

# Single-source virtual-scroll row height (c16i): the JS `const ROW_H` (via the __ROW_H__ sentinel)
# and the CSS cell padding are tuned together so a row never overflows ROW_H (14px x 1.3 + 12 + 1).
_RDC_ROW_H = 32

# Engine CSS. The `table.data` rules + `.col-groups` toggles + the type-split, lifted from the old
# template._PER_DROP_CSS so BOTH the catalog/drill (virtual) and a static report render through one
# class. Carries the custom-prop defs `table.data` depends on (--th-bg/--th-bg-active/--label) so the
# report context (which never loaded _PER_DROP_CSS) styles headers + labels correctly.
_RDC_TABLE_CSS = """
:root { --th-bg: var(--surface-2); --th-bg-active: var(--row-hover); --label: #4a6a3a; }
@media (prefers-color-scheme: dark) { :root { --label: #a3d39c; } }
rdc-table { display: block; }
/* Collapsible column groups (c16i). Real <button> toggles; no transition -> reduced-motion safe. */
.col-groups { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin: 0 0 var(--sp-2); }
.col-groups .col-group-toggle {
  font: var(--fs-small) 'Inter', 'Segoe UI', system-ui, sans-serif;
  padding: 4px 10px; cursor: pointer; color: var(--text-2);
  background: var(--surface-1); border: 1px solid var(--border-2); border-radius: 2px;
}
.col-groups .col-group-toggle[aria-pressed="true"] {
  color: var(--accent); border-color: var(--accent); background: var(--surface-2);
}
.col-groups .col-group-toggle:hover { background: var(--row-hover); }
table.data {
  border-collapse: separate; border-spacing: 0;
  font: var(--fs-body)/1.3 'Inter', 'Segoe UI', system-ui, sans-serif;
  width: max-content; min-width: 100%; table-layout: auto;
}
table.data thead th {
  position: sticky; top: 0; z-index: 2;
  background: var(--th-bg);
  text-align: left; cursor: pointer; user-select: none;
  color: var(--accent); font-weight: 600;
  padding: 6px 8px;
  border-bottom: 1px solid var(--border-2);
  white-space: nowrap;
}
table.data thead th:hover { background: var(--th-bg-active); }
table.data thead th .sort-arrow { display: inline-block; width: 10px; color: var(--text-3); }
table.data thead th.numeric, table.data tbody td.numeric {
  text-align: right; font-variant-numeric: tabular-nums;
}
/* Type split (c16i): mono+tabular only for numeric/mono BODY cells; headers stay Inter sans.
   Longhands (not the `font` shorthand) so the inherited line-height 1.3 is preserved. */
table.data tbody td.numeric, table.data tbody td.mono {
  font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
  font-size: var(--fs-mono);
}
table.data tbody td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border-1);
  vertical-align: top; white-space: nowrap;
  max-width: 380px; overflow: hidden; text-overflow: ellipsis;
  background: var(--surface-0);
}
/* Cell truncation (c16m). DEFAULT: every table.data <td> clips at 380px - this is what the un-enhanced
   bare dashboard/preview minis rely on (they have NO rdc-table host + NO inner .clip, so the td-level
   clip is their only truncation; without it a long mesh/marker name overflows the card). rdc-table cells
   OPT OUT below and truncate via an INNER element instead (an in-cell <a> or a <span class="clip">), so a
   trailing copy-button / sparkline / heatmap-cell / .lbl label rides OUTSIDE the clip and stays visible +
   clickable. Three width tiers; the full value is recoverable via a server-set title= (static) / JS-set
   title (virtual) + the real DOM text (Ctrl-F / selection-copy). ASCII ellipsis via the CSS keyword (no
   literal U+2026). One inner-clip contract, both rdc-table modes - VTable.cellNode wraps client cells,
   the report builders wrap server cells. */
rdc-table table.data tbody td { max-width: none; overflow: visible; text-overflow: clip; }
table.data { --clip-cap: 320px; --clip-cap-narrow: 200px; --clip-cap-wide: 560px; }
table.data .clip {
  display: inline-block; max-width: var(--clip-cap);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: top;
}
table.data .clip-narrow { max-width: var(--clip-cap-narrow); }
table.data .clip-wide { max-width: var(--clip-cap-wide); }
table.data tbody tr.alt td { background: var(--surface-1); }
table.data tbody tr:hover td { background: var(--row-hover); }
table.data tbody td .lbl {
  color: var(--label); margin-left: 6px;
  font-style: italic; opacity: .85;
}
table.data tbody td a {
  color: inherit; text-decoration: none;
  border-bottom: 1px dotted var(--accent);
}
table.data tbody td a:hover { color: var(--accent); border-bottom-style: solid; }
.spacer td { padding: 0; border: 0; background: var(--surface-0); }
/* Report markup bakes class="num" on numeric cells (the old report-table convention) while the
   VTable adds class="numeric"; alias .num to the table.data numeric treatment so a STATIC report
   styles correctly JS-off WITHOUT re-classing every cell (and without touching the shared delta/
   heatmap/sparkline cell helpers). Inert on catalog/drill (they never use .num). Kept as its own rule
   so the c16i type-split guard's exact `.numeric, ...td.mono` substrings stay intact. */
table.data thead th.num, table.data tbody td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.data tbody td.num { font-family: ui-monospace, 'Cascadia Code', Consolas, monospace; font-size: var(--fs-mono); }
/* Static mode has no .alt class (rows are server-baked) so zebra rides nth-child, which follows the
   visible row position after an in-place sort reorder. Scoped to static so virtual (windowed, where
   nth-child is unreliable) keeps using .alt above. */
rdc-table[data-mode="static"] table.data tbody tr:nth-child(even) td { background: var(--surface-1); }
/* Sticky-in-card guard: table.data thead is position:sticky;top:0, which inside a report section.card
   (no scroll container) would detach and float over the card (the c16c bug). Pin it static there;
   catalog tables live in their own <section> / drill in section.table-section, so this matches only
   the report context. */
section.card table.data thead th, a.dash-card table.data thead th { position: static; }
/* c16l (ADR-38): a STATIC report table replaces the retired table.report. Restore the report-table
   semantics table.data didn't carry - styled <caption>, an emphasized label (first) column - and OPT
   OUT of the 380px cell clip (report cells hold copy-buttons / sparklines / links that must stay
   visible + clickable; c16m owns controllable truncation). Scoped to static so the catalog/drill
   virtual tables stay byte-stable. Also re-home the table.report print + narrow-viewport rules here. */
/* caption: global (not static-scoped) so the bare dashboard/preview minis - table.data WITHOUT an
   rdc-table host - also get it. Catalog/drill build rows at runtime and emit no <caption>, so this is
   inert there + golden-safe. */
table.data > caption {
  caption-side: top; text-align: left; color: var(--text-2);
  font-size: var(--fs-small); padding: 0 0 var(--sp-2);
}
rdc-table[data-mode="static"] table.data tbody td:first-child { font-weight: 600; color: var(--text-1); }
/* Expand/wrap toggle (c16m): flip data-expand on the host -> release the clip. SINGLE line in both modes
   (max-width:none, still nowrap) so the VTable's fixed ROW_H stays valid; static ALSO wraps to multi-line
   (static rows auto-size - virtual must NOT, windowing locks row height). The toggle button + the
   .rdc-controls bar are built in JS (enhancement); JS-off keeps clip + title= + Ctrl-F, nothing hidden. */
rdc-table[data-expand="true"] table.data .clip { max-width: none; overflow: visible; text-overflow: clip; }
rdc-table[data-mode="static"][data-expand="true"] table.data .clip,
rdc-table[data-mode="static"][data-expand="true"] table.data tbody td { white-space: normal; overflow-wrap: anywhere; }
.rdc-controls { display: flex; gap: var(--sp-2); align-items: center; margin: 0 0 var(--sp-2); }
.rdc-controls .rdc-expand-toggle {
  font: var(--fs-small) 'Inter', 'Segoe UI', system-ui, sans-serif;
  padding: 4px 10px; cursor: pointer; color: var(--text-2);
  background: var(--surface-1); border: 1px solid var(--border-2); border-radius: 2px;
}
.rdc-controls .rdc-expand-toggle[aria-pressed="true"] {
  color: var(--accent); border-color: var(--accent); background: var(--surface-2);
}
.rdc-controls .rdc-expand-toggle:hover { background: var(--row-hover); }
@media (max-width: 720px) {
  rdc-table[data-mode="static"] table.data thead th,
  rdc-table[data-mode="static"] table.data tbody td { padding: var(--sp-1) var(--sp-2); }
}
@media print {
  rdc-table[data-mode="static"] table.data thead th {
    position: static; background: #f0f0f0; color: #000; print-color-adjust: exact;
  }
  rdc-table[data-mode="static"] table.data thead { display: table-header-group; }
  rdc-table[data-mode="static"] table.data tbody tr { break-inside: avoid; }
  /* c16m: full-wrap on paper - nothing hidden (no title= tooltips in print). Static only; virtual pages
     are windowed and never print-complete (ADR-37). Constrain the table to the page (it is width:
     max-content on screen, which would overflow + clip the paper edge) and let every clip cell flow
     inline so long unbroken paths wrap instead of running off the page. */
  rdc-table[data-mode="static"] table.data { width: 100%; max-width: 100%; }
  rdc-table[data-mode="static"] table.data .clip,
  rdc-table[data-mode="static"] table.data .clip-narrow,
  rdc-table[data-mode="static"] table.data .clip-wide {
    display: inline; max-width: none; overflow: visible; white-space: normal; text-overflow: clip; overflow-wrap: anywhere;
  }
  /* c16n: the bare dashboard/preview minis (table.data with NO rdc-table host) are clipped by the global
     380px td-clip + (dashboard) table-layout:fixed overflow:hidden, with no title= hover in print, so on
     PAPER they print CLIPPED. Release them to wrap in full - the mini analogue of the static rdc-table
     rule above (which is rdc-table[data-mode=static]-scoped, so it cannot reach the bare minis). Covers
     cells AND headers. Keep table-layout:fixed (the 2-up print grid bounds each card; auto could overflow
     it) - white-space:normal + overflow-wrap:anywhere is enough that nothing stays hidden. The preview
     mini is a DIRECT child of .table-wrap; report tables interpose <rdc-table>, so they are excluded. */
  a.dash-card table.data th, a.dash-card table.data td,
  .table-wrap > table.data th, .table-wrap > table.data td {
    max-width: none; overflow: visible; white-space: normal; overflow-wrap: anywhere;
  }
}
"""

# Engine JS. One IIFE; shared cmpVals (natural-numeric, ADR-24) + tintImage (uniform-tint heatmap);
# VTable = the windowed virtual engine; StaticTable = the in-place static enhancer.
_RDC_TABLE_JS_TMPL = r"""
(function(){
  const ROW_H = __ROW_H__;
  const BUFFER = 8;

  // For ID kinds: where to jump when an ID cell is clicked (virtual mode).
  const LINK_TARGET = {
    shader: { table: 'shaders', col: 'shader_id' },
    program: { table: 'programs', col: 'program_id' },
    texture: { table: 'textures', col: 'tex_id' },
    sampler: { table: 'samplers', col: 'sampler_id' },
    buffer: { table: 'buffers', col: 'buffer_id' },
    fbo: { table: 'fbos', col: 'fbo_id' },
  };

  function isNumeric(v){
    return v != null && (typeof v === 'number' || (typeof v === 'string' && /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v)));
  }
  function fmt(v){
    if (v == null) return '';
    if (typeof v === 'number'){
      if (v === 0) return '0';
      if (Math.abs(v) < 1e-4 || Math.abs(v) >= 1e7) return v.toExponential(4);
      return (Math.round(v * 1e6) / 1e6).toString();
    }
    return String(v);
  }

  // SHARED comparator (ADR-24 natural-numeric). The comma-strip makes the numeric branch correct for
  // BOTH raw JSON numbers (virtual) and comma-formatted display text (static); the {numeric:true}
  // localeCompare natural-sorts mixed alphanumerics ("Mali-G78" < "Mali-G710"). Nulls sort last.
  function cmpVals(aa, bb, isNum, dir){
    if (aa == null && bb == null) return 0;
    if (aa == null) return 1;
    if (bb == null) return -1;
    if (isNum){
      const na = Number(String(aa).replace(/,/g, '')), nb = Number(String(bb).replace(/,/g, ''));
      const aok = na === na, bok = nb === nb;
      if (!aok && !bok) return 0;
      if (!aok) return 1;
      if (!bok) return -1;
      return (na - nb) * dir;
    }
    return String(aa).localeCompare(String(bb), undefined, {numeric: true}) * dir;
  }

  // SHARED heatmap tint: a UNIFORM color-mix shade as a background-IMAGE (so the class-driven
  // background-COLOR zebra/hover still shows through). tt is a pre-clamped magnitude in [0,1].
  function tintImage(tt){
    const c = 'color-mix(in oklch, var(--accent-data) ' + Math.round(tt * 30) + '%, transparent)';
    return 'linear-gradient(' + c + ', ' + c + ')';
  }

  // SHARED sort-header wiring (c16o, ADR-38 a11y tail). One contract for BOTH modes: the sortable
  // <th> (implicit role columnheader - where aria-sort belongs) is made keyboard-operable
  // (tabindex 0 + Enter/Space) on top of its click. cursor:pointer already comes from the
  // `table.data thead th` CSS rule, so it is not re-set here. onSort(ci) is the mode's own sort.
  function wireSortHeader(th, ci, onSort){
    th.setAttribute('tabindex', '0');
    th.addEventListener('click', () => onSort(ci));
    th.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); onSort(ci); }
    });
  }

  function lookupLabel(labels, kind, id){
    if (!labels || !kind || id == null || id === '' || id === 0 || id === '0') return '';
    const k = String(id);
    const cap = labels.capture;
    if (!cap || !labels.by_capture || !labels.by_capture[cap]) return '';
    const buckets = labels.by_capture[cap];
    if (kind === 'auto_by_slot_kind' || kind === 'auto_by_kind') return '';
    if (kind === 'texture_list') return '';
    return (buckets[kind] && buckets[kind][k]) || '';
  }

  function autoKindForSlot(slotKind){
    if (slotKind === 'texture') return 'texture';
    if (slotKind === 'sampler') return 'sampler';
    if (slotKind === 'ubo' || slotKind === 'ssbo') return 'buffer';
    return '';
  }
  function autoKindForDescriptor(descriptorKind){
    if (descriptorKind === 'ReadOnlyResource' || descriptorKind === 'ImageSampler' || descriptorKind === 'TypedBuffer') return 'texture';
    if (descriptorKind === 'Sampler') return 'sampler';
    if (descriptorKind === 'ConstantBuffer' || descriptorKind === 'ReadWriteResource' || descriptorKind === 'ReadWriteBuffer') return 'buffer';
    return '';
  }

  // ---- VTable: virtual mode (windowed; rows come from the externalized _pagedata payload) ----
  class VTable {
    constructor(host, payload, labels, groups){
      this.host = host;
      this.cols = payload.cols;
      this.rows = payload.rows;
      this.labelCols = payload.labelCols || {};
      this.labels = labels;
      this.groups = groups || null;  // catalog-only column groups (c16i); null elsewhere
      this.view = this.rows.slice();
      this.sortCol = -1;
      this.sortDir = 1;

      // detect numeric columns from first 50 non-null cells
      this.numericCols = new Set();
      for (let ci = 0; ci < this.cols.length; ci++){
        let count = 0, num = 0;
        for (let ri = 0; ri < this.rows.length && count < 50; ri++){
          const v = this.rows[ri][ci];
          if (v == null || v === '') continue;
          count++;
          if (typeof v === 'number' || (typeof v === 'string' && /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v))) num++;
        }
        if (count > 0 && num / count > 0.7) this.numericCols.add(ci);
      }

      // Type split (c16i): non-numeric ID/hash/path columns render mono. Decided by column NAME.
      this.monoCols = new Set();
      const MONO_RE = /(_id|_hash|_hex)$|^stable_key$|.*_path$|^capture$/;
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci) && MONO_RE.test(this.cols[ci])) this.monoCols.add(ci);
      }
      // c16m: known-long non-numeric columns get the WIDE clip tier (src paths, hashes, stable_keys);
      // other non-numeric columns get the default clip tier. Numeric cells are never clipped.
      this.wideCols = new Set();
      const WIDE_RE = /(_hash|_hex)$|^stable_key$|.*_path$/;
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci) && WIDE_RE.test(this.cols[ci])) this.wideCols.add(ci);
      }

      // Heatmap (c16i): per-column min/max for numeric MAGNITUDE columns. Exclude ID/reference cols
      // and cross-link label cols. Scanned over ALL rows so the scale is stable across sort/filter.
      const ID_RE = /_id$|^event_id$/;
      this.colStats = {};
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci)) continue;
        if (ID_RE.test(this.cols[ci]) || this.labelCols[this.cols[ci]]) continue;
        let lo = Infinity, hi = -Infinity, seen = 0;
        for (let ri = 0; ri < this.rows.length; ri++){
          const v = this.rows[ri][ci];
          if (v == null || v === '') continue;
          const n = +v;
          if (n !== n) continue;  // NaN guard
          if (n < lo) lo = n;
          if (n > hi) hi = n;
          seen++;
        }
        if (seen > 0 && hi > lo) this.colStats[ci] = {lo: lo, hi: hi};
      }

      // Collapsible column groups (c16i, catalog only).
      this.hiddenCols = new Set();
      this.colByName = {};
      for (let i = 0; i < this.cols.length; i++) this.colByName[this.cols[i]] = i;
      if (this.groups){
        this.groups.forEach(g => {
          if (!g.open){
            g.cols.forEach(c => {
              const ci = (typeof c === 'number') ? c : this.colByName[c];
              if (ci != null) this.hiddenCols.add(ci);
            });
          }
        });
      }

      this.slotKindCol = this.cols.indexOf('slot_kind');
      this.descriptorKindCol = this.cols.indexOf('descriptor_kind');

      this.build();
    }

    buildHead(){
      const tr = this.headRow;
      while (tr.firstChild) tr.removeChild(tr.firstChild);
      for (let i = 0; i < this.cols.length; i++){
        if (this.hiddenCols.has(i)) continue;
        const th = document.createElement('th');
        th.dataset.ci = i;
        th.appendChild(document.createTextNode(this.cols[i]));
        if (this.numericCols.has(i)) th.classList.add('numeric');
        const arrow = document.createElement('span');
        arrow.className = 'sort-arrow';
        if (i === this.sortCol) arrow.textContent = this.sortDir > 0 ? ' ▲' : ' ▼';
        th.appendChild(arrow);
        // a11y (c16o): announce sort state + keep it correct across group-toggle rebuilds.
        th.setAttribute('aria-sort', (i === this.sortCol) ? (this.sortDir > 0 ? 'ascending' : 'descending') : 'none');
        wireSortHeader(th, i, (ci) => this.sort(ci));
        tr.appendChild(th);
      }
    }

    buildGroupBar(){
      if (!this.groups) return;
      const section = this.host.closest('section');
      const bar = section ? section.querySelector('.col-groups') : null;
      if (!bar) return;
      this.groups.forEach(g => {
        const cis = g.cols.map(c => (typeof c === 'number') ? c : this.colByName[c]).filter(x => x != null);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'col-group-toggle';
        btn.dataset.group = g.name;
        btn.textContent = g.name;
        btn.setAttribute('aria-pressed', g.open ? 'true' : 'false');
        btn.addEventListener('click', () => {
          const next = btn.getAttribute('aria-pressed') !== 'true';
          btn.setAttribute('aria-pressed', next ? 'true' : 'false');
          cis.forEach(ci => { if (next) this.hiddenCols.delete(ci); else this.hiddenCols.add(ci); });
          this.buildHead();
          this.render();
        });
        bar.appendChild(btn);
      });
    }

    build(){
      const table = document.createElement('table');
      table.className = 'data';
      const thead = table.createTHead();
      this.headRow = thead.insertRow();
      this.buildHead();
      const tbody = document.createElement('tbody');
      const sTop = document.createElement('tr');
      const sBot = document.createElement('tr');
      sTop.className = 'spacer'; sBot.className = 'spacer';
      const tdTop = document.createElement('td');
      const tdBot = document.createElement('td');
      tdTop.colSpan = this.cols.length;
      tdBot.colSpan = this.cols.length;
      sTop.appendChild(tdTop); sBot.appendChild(tdBot);
      tbody.appendChild(sTop); tbody.appendChild(sBot);
      table.appendChild(tbody);
      this.host.appendChild(table);

      this.tbody = tbody;
      this.sTop = sTop;
      this.sBot = sBot;
      this.tdTop = tdTop;
      this.tdBot = tdBot;

      this.buildGroupBar();

      this.host.addEventListener('scroll', () => this.render());
      window.addEventListener('resize', () => this.render());
      const detailsEl = this.host.closest('details');
      if (detailsEl){
        detailsEl.addEventListener('toggle', () => {
          if (detailsEl.open){
            requestAnimationFrame(() => this.render());
            setTimeout(() => this.render(), 50);
          }
        });
      }
      this.render();
      requestAnimationFrame(() => this.render());
      setTimeout(() => this.render(), 50);
    }

    sort(ci){
      if (this.sortCol === ci) this.sortDir = -this.sortDir;
      else { this.sortCol = ci; this.sortDir = 1; }
      const dir = this.sortDir;
      const isNum = this.numericCols.has(ci);
      this.view.sort((a, b) => cmpVals(a[ci], b[ci], isNum, dir));
      const headers = this.host.querySelectorAll('thead th');
      for (let k = 0; k < headers.length; k++){
        const match = (+headers[k].dataset.ci === ci);
        const a = headers[k].querySelector('.sort-arrow');
        if (a) a.textContent = match ? (dir > 0 ? ' ▲' : ' ▼') : '';
        headers[k].setAttribute('aria-sort', match ? (dir > 0 ? 'ascending' : 'descending') : 'none');  // a11y (c16o)
      }
      this.host.scrollTop = 0;
      this.render();
    }

    filter(query){
      const q = (query || '').trim().toLowerCase();
      if (!q){
        this.view = this.rows.slice();
      } else {
        const labels = this.labels;
        const labelCols = this.labelCols;
        const cols = this.cols;
        const slotKindCol = this.slotKindCol;
        const descriptorKindCol = this.descriptorKindCol;
        this.view = this.rows.filter(r => {
          for (let i = 0; i < r.length; i++){
            const v = r[i];
            if (v == null) continue;
            if (String(v).toLowerCase().indexOf(q) >= 0) return true;
            const lc = labelCols[cols[i]];
            if (!lc || v === 0 || v === '0' || v === '') continue;
            let kind = lc;
            if (kind === 'auto_by_slot_kind' && slotKindCol >= 0) kind = autoKindForSlot(r[slotKindCol]);
            else if (kind === 'auto_by_kind' && descriptorKindCol >= 0) kind = autoKindForDescriptor(r[descriptorKindCol]);
            if (kind === 'texture_list'){
              const ids = String(v).split(';').filter(x => x);
              for (const id of ids){
                const lbl = lookupLabel(labels, 'texture', id);
                if (lbl && lbl.toLowerCase().indexOf(q) >= 0) return true;
              }
            } else if (kind){
              const lbl = lookupLabel(labels, kind, v);
              if (lbl && lbl.toLowerCase().indexOf(q) >= 0) return true;
            }
          }
          return false;
        });
      }
      if (this.sortCol >= 0){
        const ci = this.sortCol, dir = this.sortDir;
        const isNum = this.numericCols.has(ci);
        this.view.sort((a, b) => cmpVals(a[ci], b[ci], isNum, dir));
      }
      this.host.scrollTop = 0;
      this.render();
    }

    cellNode(value, ri, ci){
      const td = document.createElement('td');
      if (this.numericCols.has(ci)) td.classList.add('numeric');
      else if (this.monoCols.has(ci)) td.classList.add('mono');

      const colName = this.cols[ci];
      const lc = this.labelCols[colName];
      let kind = lc;
      if (kind === 'auto_by_slot_kind' && this.slotKindCol >= 0){
        kind = autoKindForSlot(this.view[ri][this.slotKindCol]);
      } else if (kind === 'auto_by_kind' && this.descriptorKindCol >= 0){
        kind = autoKindForDescriptor(this.view[ri][this.descriptorKindCol]);
      }

      const formatted = fmt(value);
      // c16m: clip non-numeric cells on an inner element (the <a>, or a <span class="clip">) so the
      // .lbl label + heatmap background (set on the td below) ride OUTSIDE the clip and stay visible.
      // Numeric cells are never clipped. Re-applied every windowed render() (cellNode rebuilds nodes).
      const clipCls = this.numericCols.has(ci) ? '' : (this.wideCols.has(ci) ? 'clip clip-wide' : 'clip');
      const link = LINK_TARGET[kind];
      if (link && value != null && value !== '' && value !== 0 && value !== '0' && kind !== 'texture_list'){
        const a = document.createElement('a');
        a.href = '#' + link.table;
        a.textContent = formatted;
        a.title = 'jump to ' + link.table + ' filtered to ' + link.col + '=' + value;
        if (clipCls) a.className = clipCls;   // truncate long link text; keep the nav title
        a.addEventListener('click', (ev) => {
          ev.preventDefault();
          jumpToTable(link.table, String(value));
        });
        td.appendChild(a);
      } else if (clipCls){
        const span = document.createElement('span');
        span.className = clipCls;
        span.textContent = formatted;
        if (formatted && formatted.length > (this.wideCols.has(ci) ? 64 : 40)) span.title = formatted;
        td.appendChild(span);
      } else {
        td.textContent = formatted;
      }

      const stat = this.colStats[ci];
      if (stat != null && value != null && value !== ''){
        const n = +value;
        if (n === n){
          let tt = (n - stat.lo) / (stat.hi - stat.lo);
          tt = tt < 0 ? 0 : (tt > 1 ? 1 : tt);
          const pct = Math.round(tt * 100);
          td.style.backgroundImage = tintImage(tt);
          td.setAttribute('aria-label', formatted + ' (' + pct + '% of column max)');
        }
      }

      if (lc && value != null && value !== '' && value !== 0 && value !== '0'){
        if (kind === 'texture_list'){
          const ids = String(value).split(';').filter(x => x);
          const labels = ids.map(id => lookupLabel(this.labels, 'texture', id))
                            .filter(x => x);
          if (labels.length){
            const span = document.createElement('span');
            span.className = 'lbl';
            span.textContent = labels.join(', ');
            td.appendChild(span);
          }
        } else if (kind){
          const label = lookupLabel(this.labels, kind, value);
          if (label){
            const span = document.createElement('span');
            span.className = 'lbl';
            span.textContent = label;
            td.appendChild(span);
          }
        }
      }
      return td;
    }

    render(){
      const scrollTop = this.host.scrollTop;
      const height = this.host.clientHeight || 600;
      const len = this.view.length;
      const start = Math.max(0, Math.floor(scrollTop / ROW_H) - BUFFER);
      const end = Math.min(len, Math.ceil((scrollTop + height) / ROW_H) + BUFFER);

      while (this.sTop.nextSibling !== this.sBot){
        this.tbody.removeChild(this.sTop.nextSibling);
      }
      const visible = this.cols.length - this.hiddenCols.size;
      this.tdTop.colSpan = visible;
      this.tdBot.colSpan = visible;
      this.sTop.style.height = (start * ROW_H) + 'px';
      this.sBot.style.height = ((len - end) * ROW_H) + 'px';
      this.tdTop.style.height = (start * ROW_H) + 'px';
      this.tdBot.style.height = ((len - end) * ROW_H) + 'px';

      const frag = document.createDocumentFragment();
      for (let i = start; i < end; i++){
        const tr = document.createElement('tr');
        tr.style.height = ROW_H + 'px';
        if (i % 2 === 1) tr.className = 'alt';
        const row = this.view[i];
        for (let ci = 0; ci < this.cols.length; ci++){
          if (this.hiddenCols.has(ci)) continue;
          tr.appendChild(this.cellNode(row[ci], i, ci));
        }
        frag.appendChild(tr);
      }
      this.tbody.insertBefore(frag, this.sBot);
    }
  }

  // ---- StaticTable: static mode (in-place; rows are server-baked) ----
  // Enhances an existing server-baked table.data WITHOUT removing rows from the DOM, so JS-off / print /
  // Ctrl-F keep every row (ADR-37). Sort reorders the live <tr> nodes (nested components ride along);
  // heatmap tints existing numeric <td>s; column-groups toggle display. Numeric cols are read from
  // the header class (no value-sniff); column groups come from window.__colgroups_<data-table> and
  // may key by column INDEX (reports, where header text can repeat) or NAME (the catalog path).
  class StaticTable {
    constructor(host){
      this.host = host;
      const table = host.querySelector('table');
      if (!table) return;
      this.table = table;
      const thead = table.tHead;
      this.ths = (thead && thead.rows[0]) ? Array.prototype.slice.call(thead.rows[0].cells) : [];
      this.cols = this.ths.map(th => th.textContent.trim());
      this.colByName = {};
      for (let i = 0; i < this.cols.length; i++) this.colByName[this.cols[i]] = i;
      this.tbody = table.tBodies[0];
      if (!this.tbody) return;
      this.trNodes = Array.prototype.slice.call(this.tbody.rows);
      this.sortCol = -1; this.sortDir = 1;
      this.hiddenCols = new Set();

      // numeric columns from header class (.numeric, or legacy .num from report markup)
      this.numericCols = new Set();
      this.ths.forEach((th, ci) => {
        if (th.classList.contains('numeric') || th.classList.contains('num')) this.numericCols.add(ci);
      });

      // colStats for the auto-heatmap (comma-stripped values). Skip a column whose cells already
      // carry an <rdc-heatmap-cell> (already shaded) so we never double-tint.
      this.colStats = {};
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci)) continue;
        const first = this.trNodes.length ? this.trNodes[0].cells[ci] : null;
        if (first && first.querySelector('rdc-heatmap-cell')) continue;
        let lo = Infinity, hi = -Infinity, seen = 0;
        for (let ri = 0; ri < this.trNodes.length; ri++){
          const cell = this.trNodes[ri].cells[ci];
          if (!cell) continue;
          const t = cell.textContent.trim();
          if (t === '') continue;
          const n = Number(t.replace(/,/g, ''));
          if (n !== n) continue;
          if (n < lo) lo = n;
          if (n > hi) hi = n;
          seen++;
        }
        if (seen > 0 && hi > lo) this.colStats[ci] = {lo: lo, hi: hi};
      }

      this._wireHeaders();
      this._applyHeatmap();
      this._buildGroups();

      // default sort (data-default-sort = header text; data-default-dir = asc|desc, default desc)
      const def = host.dataset.defaultSort;
      if (def){
        let idx = -1;
        for (let i = 0; i < this.cols.length; i++){
          if (this.cols[i].toLowerCase() === def.toLowerCase()){ idx = i; break; }
        }
        if (idx >= 0){
          this.sortCol = idx;
          this.sortDir = (host.dataset.defaultDir === 'asc') ? 1 : -1;
          this._paintSort(idx);
        }
      }
    }

    _wireHeaders(){
      this.ths.forEach((th, ci) => {
        th.setAttribute('aria-sort', 'none');   // a11y: report sort state (c16l - was on rdc-sortable-table)
        let arrow = th.querySelector('.sort-arrow');
        if (!arrow){ arrow = document.createElement('span'); arrow.className = 'sort-arrow'; th.appendChild(arrow); }
        wireSortHeader(th, ci, (i) => this.sort(i));   // a11y (c16o): keyboard-operable (shared with VTable)
      });
    }

    sort(ci){
      if (this.sortCol === ci) this.sortDir = -this.sortDir;
      else { this.sortCol = ci; this.sortDir = 1; }
      this._paintSort(ci);
    }

    _paintSort(ci){
      const dir = this.sortDir, isNum = this.numericCols.has(ci);
      const getv = (tr) => { const c = tr.cells[ci]; const t = c ? c.textContent.trim() : ''; return t === '' ? null : t; };
      this.trNodes.sort((ra, rb) => cmpVals(getv(ra), getv(rb), isNum, dir));
      const frag = document.createDocumentFragment();
      this.trNodes.forEach(tr => frag.appendChild(tr));
      this.tbody.appendChild(frag);
      this.ths.forEach((th, k) => {
        const a = th.querySelector('.sort-arrow');
        if (a) a.textContent = (k === ci) ? (dir > 0 ? ' ▲' : ' ▼') : '';
        th.setAttribute('aria-sort', (k === ci) ? (dir > 0 ? 'ascending' : 'descending') : 'none');
      });
    }

    _applyHeatmap(){
      for (const k in this.colStats){
        const ci = +k, stat = this.colStats[ci];
        this.trNodes.forEach(tr => {
          const td = tr.cells[ci];
          if (!td) return;
          const t = td.textContent.trim();
          if (t === '') return;
          const n = Number(t.replace(/,/g, ''));
          if (n !== n) return;
          let tt = (n - stat.lo) / (stat.hi - stat.lo);
          tt = tt < 0 ? 0 : (tt > 1 ? 1 : tt);
          td.style.backgroundImage = tintImage(tt);
          td.setAttribute('aria-label', t + ' (' + Math.round(tt * 100) + '% of column max)');
        });
      }
    }

    _buildGroups(){
      const groups = window['__colgroups_' + (this.host.dataset.table || '')];
      if (!groups) return;
      const section = this.host.closest('section');
      const bar = section ? section.querySelector('.col-groups') : null;
      if (!bar) return;
      const idx = (c) => (typeof c === 'number') ? c : this.colByName[c];
      groups.forEach(g => {
        if (!g.open) g.cols.forEach(c => { const ci = idx(c); if (ci != null) this.hiddenCols.add(ci); });
      });
      this._applyVisibility();
      groups.forEach(g => {
        const cis = g.cols.map(idx).filter(x => x != null);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'col-group-toggle';
        btn.dataset.group = g.name;
        btn.textContent = g.name;
        btn.setAttribute('aria-pressed', g.open ? 'true' : 'false');
        btn.addEventListener('click', () => {
          const next = btn.getAttribute('aria-pressed') !== 'true';
          btn.setAttribute('aria-pressed', next ? 'true' : 'false');
          cis.forEach(ci => { if (next) this.hiddenCols.delete(ci); else this.hiddenCols.add(ci); });
          this._applyVisibility();
        });
        bar.appendChild(btn);
      });
    }

    _applyVisibility(){
      this.ths.forEach((th, ci) => { th.style.display = this.hiddenCols.has(ci) ? 'none' : ''; });
      this.trNodes.forEach(tr => {
        for (let ci = 0; ci < tr.cells.length; ci++){
          tr.cells[ci].style.display = this.hiddenCols.has(ci) ? 'none' : '';
        }
      });
    }
  }

  function jumpToTable(tableName, idValue){
    const host = document.querySelector('rdc-table[data-table="' + tableName + '"]');
    if (!host || !host._vt) return;
    const section = host.closest('section');
    const input = section ? section.querySelector('input[type=search]') : null;
    if (input){
      input.value = idValue;
      host._vt.filter(idValue);
      const counter = section.querySelector('.ct.visible-count');
      if (counter){
        const v = host._vt.view.length, t = host._vt.rows.length;
        counter.textContent = v.toLocaleString() + ' / ' + t.toLocaleString() + ' visible';
      }
    }
    if (section) section.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  window.__jumpToTable = jumpToTable;

  // c16m: global expand/wrap toggle. Built in JS (enhancement) only when the table actually carries
  // clippable cells (no dead button on simple tables). Inserted before the host so it sits above the
  // table (static) / scroll box (virtual). Click flips data-expand on the host; the CSS does the rest
  // (full-width single line in both modes; static also wraps - virtual keeps one line so the windowed
  // ROW_H stays valid). JS-off: no toggle, but clip + title= + Ctrl-F keep nothing hidden.
  function buildExpandToggle(host){
    if (host._expandWired || !host.querySelector('.clip')) return;
    host._expandWired = true;
    const bar = document.createElement('div');
    bar.className = 'rdc-controls';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'rdc-expand-toggle';
    btn.textContent = 'Expand cells';
    btn.setAttribute('aria-pressed', 'false');
    btn.addEventListener('click', () => {
      const next = btn.getAttribute('aria-pressed') !== 'true';
      btn.setAttribute('aria-pressed', next ? 'true' : 'false');
      if (next) host.dataset.expand = 'true'; else host.removeAttribute('data-expand');
    });
    bar.appendChild(btn);
    if (host.parentNode) host.parentNode.insertBefore(bar, host);
  }

  window.addEventListener('DOMContentLoaded', () => {
    const labels = window.__labels || {};
    document.querySelectorAll('rdc-table[data-mode]').forEach(host => {
      if (host.dataset.mode === 'static'){
        host._vt = new StaticTable(host);
        buildExpandToggle(host);
        return;
      }
      // virtual
      const name = host.dataset.table;
      const payload = window['__data_' + name];
      if (!payload){ return; }
      const labelsForTable = Object.assign({}, labels);
      labelsForTable.capture = host.dataset.capture || (payload.rows[0] ? payload.rows[0][3] : '');
      const groups = window['__colgroups_' + name];
      const vt = new VTable(host, payload, labelsForTable, groups);
      host._vt = vt;
      buildExpandToggle(host);

      const section = host.closest('section');
      const input = section ? section.querySelector('input[type=search]') : null;
      const counter = section ? section.querySelector('.ct.visible-count') : null;
      if (counter){
        function updateCounter(){
          const v = vt.view.length, t = vt.rows.length;
          counter.textContent = v.toLocaleString() + ' / ' + t.toLocaleString() + ' visible';
        }
        updateCounter();
        if (input){
          let timer = null;
          input.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => { vt.filter(input.value); updateCounter(); }, 80);
          });
        }
      }
    });
  });
})();
"""

_RDC_TABLE_JS = _RDC_TABLE_JS_TMPL.replace('__ROW_H__', str(_RDC_ROW_H))


def rdc_table_css() -> str:
    """Engine CSS for the unified rdc-table (c16k). Used by template.py (catalog/drill), emitted
    verbatim (un-minified) so the c16i substring guards over the catalog/drill output stay green. The
    report bundle folds it in via _compose_css() (c16l, ADR-38 — always-on, no longer opt-in)."""
    return _RDC_TABLE_CSS


def rdc_table_js() -> str:
    """Engine JS for the unified rdc-table (c16k). Used verbatim by template.py (catalog/drill); the
    report bundle folds it into _compose_js() (c16l)."""
    return _RDC_TABLE_JS


def h(s) -> str:
    return _html.escape(str(s if s is not None else ''))


# c16m: per-tier char thresholds for emitting a title= on a truncating cell. A deterministic proxy for
# "will visually clip" (matches the pass_gpu title-gating precedent); short values skip title= to avoid
# screen-reader double-read. Tier '' = default (--clip-cap 320px), 'narrow' (200px), 'wide' (560px).
_CLIP_TITLE_THRESH = {'': 40, 'narrow': 24, 'wide': 64}


def clip_attrs(full_value, *, tier: str = '') -> str:
    """The ` class="clip…"` + length-gated ` title="…"` for a truncating cell element (c16m).

    Splice onto an existing in-cell `<a>`/element whose visible text is the (possibly long) value; the
    clip is CSS-only so the real DOM text + the title= keep the FULL value (Ctrl-F / hover / copy). Use
    on cells that already build their own inner element (e.g. a linked src path). `tier` in
    {'', 'narrow', 'wide'}; the full value lives in title= when longer than the tier threshold.
    """
    s = '' if full_value is None else str(full_value)
    cls = 'clip' if not tier else f'clip clip-{tier}'
    title = f' title="{_f.safe_chrome_text(s)}"' if len(s) > _CLIP_TITLE_THRESH.get(tier, 40) else ''
    return f' class="{cls}"{title}'


def clip_span(value, *, tier: str = '') -> str:
    """Wrap a plain-text cell value in a truncating `<span class="clip…">` (c16m).

    For long text cells that have no inner element of their own (RT label, areas, area name, …). The
    value is HTML-escaped for display and (when long) carried verbatim in title= via `clip_attrs`.
    Copy-button / link payloads are built separately by the caller and stay the FULL value.
    """
    s = '' if value is None else str(value)
    return f'<span{clip_attrs(s, tier=tier)}>{_html.escape(s)}</span>'


# Canonical class order + colors. Reports use this order in stacks. Single source = the active
# classifier preset's class_order (H-5); the UE default reproduces the former literal byte-for-byte
# (pinned by tests/test_classifier). The hand-aligned --c-<name> CSS tokens live in the design-token
# skeleton above and are asserted to cover every class here.
DRAW_CLASSES = list(_classifier.class_order())


def class_color_var(cls: str) -> str:
    return f'var(--c-{cls})' if cls in DRAW_CLASSES else 'var(--c-other)'


def page_open(title: str, *, hdr_offset_px: int | None = None,
              body_attrs: dict | None = None) -> str:
    """Open a self-contained HTML page. hdr_offset_px sets --hdr-offset on <body>.

    Use 48 for dashboard / single-section reports, 84 for multi-section reports
    that carry ab_strip / device_strip / toc above the first sticky h2.
    body_attrs: extra attributes on <body> (e.g. {'data-multi-section': 'true'}).

    The rdc-table engine CSS+JS ship in the shared bundle (_compose_css/_compose_js) for EVERY page
    (c16l, ADR-38 — every report now hosts a STATIC <rdc-table>); the c16k opt-in is gone.
    """
    js = _compose_js()
    script = f'<script>{js}</script>' if js else ''
    attrs: list[str] = []
    if hdr_offset_px is not None:
        attrs.append(f'style="--hdr-offset: {int(hdr_offset_px)}px"')
    for k, v in (body_attrs or {}).items():
        attrs.append(f'{_html.escape(k)}="{_html.escape(str(v))}"')
    body_attr_str = (' ' + ' '.join(attrs)) if attrs else ''
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>{_html.escape(title)}</title>'
            f'<link rel="icon" href="{_FAVICON_HREF}">'
            f'<style>{_compose_css()}</style>'
            f'{script}</head><body{body_attr_str}>'
            f'{_ICON_SPRITE}')


def icon(name: str) -> str:
    """Return inline SVG referencing the icon sprite."""
    return f'<svg class="icon" aria-hidden="true"><use href="#icon-{_html.escape(name)}"/></svg>'


def summary_bar(label: str, headline: str, *,
                sub: str | None = None,
                link_href: str | None = None,
                link_text: str = 'view',
                tone: str = 'neutral') -> str:
    """Render the per-page summary-bar primitive.

    label: short caption (e.g. "worst gpu area")
    headline: 5-second number / phrase (rendered at --fs-display)
    sub: optional sub-line (e.g. "rank 1 of 7 areas")
    link_href: optional primary-action link rendered as button chip
    tone: neutral | alarm | warn | ok | info (controls top border color)
    """
    wrap_open = ''
    wrap_close = ''
    if tone == 'alarm':
        wrap_open = '<rdc-alarm-banner data-severity="high">'
        wrap_close = '</rdc-alarm-banner>'
    parts = [wrap_open]
    parts.append(f'<aside class="summary-bar tone-{_html.escape(tone)}" aria-label="page summary">')
    parts.append(f'<div class="sb-label">{_html.escape(label)}</div>')
    parts.append(f'<div class="sb-headline">{_html.escape(headline)}</div>')
    if sub:
        parts.append(f'<div class="sb-sub">{_html.escape(sub)}</div>')
    if link_href:
        parts.append(f'<a class="sb-link" href="{_html.escape(link_href)}" '
                     f'data-link-kind="primary">{_html.escape(link_text)}</a>')
    parts.append('</aside>')
    parts.append(wrap_close)
    return ''.join(parts)


def empty_state(message: str, *, icon_name: str = 'warn') -> str:
    """Friendly empty-state card (icon + message) for a report/section with no rows (c16). Replaces a
    bare `<p class="note">` / blank `<tbody>` so a sparse drop reads as 'no data', not 'broken'."""
    return f'<div class="empty-state">{icon(icon_name)}<span>{h(message)}</span></div>'


def callout(severity: str, title: str, detail: str = '', *,
            href: str | None = None, link_text: str = 'view',
            icon_name: str | None = None) -> str:
    """Render a ranked-finding callout — the report's 'so what' (c16).

    severity in {ok, warn, alarm, info, neutral}; controls the left-border + icon color. warn/alarm
    wrap in <rdc-alarm-banner> so the finding is announced to assistive tech (role/aria-live set by
    the component). ``detail`` is a sub-line; ``href``/``link_text`` an optional primary action.
    """
    sev = severity if severity in ('ok', 'warn', 'alarm', 'info') else 'neutral'
    ic = icon_name or ('warn' if sev in ('alarm', 'warn') else 'arrow-right')
    wrap_open = wrap_close = ''
    if sev in ('alarm', 'warn'):
        wrap_open = f'<rdc-alarm-banner data-severity="{"high" if sev == "alarm" else "low"}">'
        wrap_close = '</rdc-alarm-banner>'
    body = [f'<div class="co-body"><div class="co-title">{h(title)}</div>']
    if detail:
        body.append(f'<div class="co-detail">{h(detail)}</div>')
    if href:
        body.append(f'<a href="{h(href)}" data-link-kind="inline">{h(link_text)}</a>')
    body.append('</div>')
    return f'{wrap_open}<div class="callout sev-{sev}">{icon(ic)}{"".join(body)}</div>{wrap_close}'


def heatmap_cell(value, lo, hi, *, direction: str = 'hot', text: str | None = None) -> str:
    """Inline data-shaded cell via the rdc-heatmap-cell web-component (c16). The server emits
    value+min+max; the component shades client-side, so the emitted HTML stays deterministic. Returns
    the element only — wrap it in a `<td class="num">`. ``direction`` 'hot' = high values are intense."""
    disp = text if text is not None else value
    return (f'<rdc-heatmap-cell data-value="{h(value)}" data-min="{h(lo)}" data-max="{h(hi)}" '
            f'data-direction="{h(direction)}">{h(disp)}</rdc-heatmap-cell>')


def provenance_strip(host_info: dict | None, tool_versions: dict | None) -> str:
    """Capture-context strip: GPU/driver/CPU/OS + external tool versions (G-6/G-7) recorded at ingest.

    Renders the .device-strip primitive under the page header so every report shows the machine + tool
    versions the data came from. Omits the bobframes version on purpose (a release bump must not churn
    the golden). Returns '' when no provenance was recorded (older manifests).
    """
    host_info = host_info or {}
    tool_versions = tool_versions or {}
    fields = []
    for key, label in (('gpu', 'gpu'), ('gpu_driver', 'driver'), ('cpu', 'cpu'), ('os', 'os')):
        v = host_info.get(key)
        if v:
            fields.append(f'{label} <strong>{h(v)}</strong>')
    for tool in ('renderdoccmd', 'qrenderdoc'):
        v = tool_versions.get(tool)
        if v:
            fields.append(f'{tool} <strong>{h(v)}</strong>')
    if not fields:
        return ''
    return f'<div class="device-strip">{" | ".join(fields)}</div>'


def ab_picker(options: list, current_href: str | None = None) -> str:
    """Render A/B picker dropdown.

    options: list of (label, href) tuples.
    current_href: optional href to mark selected.
    """
    if not options:
        return ''
    parts = ['<rdc-ab-picker><label for="rdc-ab-select">compare</label>',
             '<select id="rdc-ab-select">',
             '<option value="">none</option>']
    for label, href in options:
        sel = ' selected' if current_href == href else ''
        parts.append(f'<option value="{_html.escape(href)}"{sel}>'
                     f'{_html.escape(label)}</option>')
    parts.append('</select></rdc-ab-picker>')
    return ''.join(parts)


def ab_picker_for(root: str, report_name: str, *, ab=None) -> str:
    """Discover A/B pairs under <root>/_reports/ab and emit picker for given report.

    Suppresses output when ab is non-None (caller is already on an A/B page).
    Emits relative URLs from <root>/_reports/<report>.html.
    """
    import os as _os
    from .. import paths as _paths
    if ab is not None:
        return ''
    ab_dir = _os.path.join(_paths.reports_dir(root), _paths.AB_DIR)
    if not _os.path.isdir(ab_dir):
        return ''
    pairs = sorted(d for d in _os.listdir(ab_dir)
                   if _os.path.isdir(_os.path.join(ab_dir, d)))
    if not pairs:
        return ''
    options = [(p, f'ab/{p}/{report_name}.html') for p in pairs]
    return ab_picker(options)


def run_picker(options: list, current_href: str | None = None) -> str:
    """Run selector (c16f): a static <select> of per-run page links, reusing the rdc-ab-picker web
    component (it navigates to select.value on change - no new JS). Distinct select id from the A/B
    picker so both can coexist on one page; no 'none' option (a report is always for some run)."""
    if not options:
        return ''
    parts = ['<rdc-ab-picker><label for="rdc-run-select">run</label>',
             '<select id="rdc-run-select">']
    for label, href in options:
        sel = ' selected' if current_href == href else ''
        parts.append(f'<option value="{_html.escape(href)}"{sel}>'
                     f'{_html.escape(label)}</option>')
    parts.append('</select></rdc-ab-picker>')
    return ''.join(parts)


def run_picker_for(run, report_name: str, *, reports_up: str = '',
                   max_older: int = 10) -> str:
    """Emit the run selector for `report_name` from a RunContext (c16f). '' when <=1 run.

    Lists the pre-rendered runs (newest + the `max_older` most-recent older) as links: the newest is
    the top-level `<report>.html`, older runs are `run/<key>/<report>.html`, each prefixed by
    `reports_up` ('' from a top-level page, '../../' from a per-run page) so links resolve from both
    locations. The current run's own option is marked selected. Labels via safe_chrome_text.
    """
    from .discovery import prerendered_runs as _prerendered
    from .. import paths as _paths
    if run is None or getattr(run, 'n_runs', 0) <= 1:
        return ''
    shown = {d.key for d in _prerendered(run.drops, max_older)}
    newest_key = run.drops[-1].key
    cur_key = run.current.key if getattr(run, 'current', None) else newest_key
    n = run.n_runs
    options = []
    current_href = None
    for i, d in enumerate(run.drops):
        if d.key not in shown:
            continue
        is_new = d.key == newest_key
        label = _f.safe_chrome_text(
            f'run {i + 1}/{n}: {d.key}' + (' (newest)' if is_new else ''))
        href = (f'{reports_up}{report_name}.html' if is_new
                else f'{reports_up}{_paths.RUN_DIR}/{d.key}/{report_name}.html')
        options.append((label, href))
        if d.key == cur_key:
            current_href = href
    return run_picker(options, current_href)


def run_compare_banner(current, baseline) -> str:
    """The 'current <x> vs baseline <y>' banner (c16f). '' when there is no baseline.

    Reuses the .ab-strip chrome; the baseline key is dimmed (--text-3 via .dim). Keys are
    data-derived -> routed through safe_chrome_text.
    """
    if current is None or baseline is None:
        return ''
    return (f'<div class="ab-strip">current: {_f.safe_chrome_text(current.key)} '
            f'| baseline: <span class="dim">{_f.safe_chrome_text(baseline.key)}</span></div>')


def link(href: str, text: str, *, kind: str = 'inline',
         icon_name: str | None = None, target_blank: bool = False) -> str:
    """Render <a data-link-kind=...> with optional trailing icon.

    kind: primary | inline | drill | copy | crumb
    icon_name: matches a symbol id in _ICON_SPRITE (link-out, file, arrow-right, copy, search, warn)
    """
    target_attr = ' target="_blank" rel="noopener"' if target_blank else ''
    icon_html = icon(icon_name) if icon_name else ''
    return (f'<a href="{_html.escape(href)}" data-link-kind="{_html.escape(kind)}"'
            f'{target_attr}>{_html.escape(text)}{icon_html}</a>')


def page_close() -> str:
    return '</body></html>'


def report_page(title: str, body, *, drops: int = 0, captures: int = 0,
                build_ts: str = '', crumb_depth: int = 1, kpis: list | None = None,
                current_page: str | None = None, hdr_offset_px: int | None = 120,
                body_attrs: dict | None = None, ab=None, root: str | None = None,
                report_key: str | None = None, device: str = '', run=None,
                run_nav_key: str | None = None) -> str:
    """Assemble a standard Layer-2 report page, deduping the open/header/strip/close shared by every
    report (Q-6). ``body`` is an HTML string or a list of fragments (the report's summary_bar +
    sections, in order). The fragments are '\\n'-joined exactly as write_report joins a parts list, so
    routing a report through this helper is byte-identical to the old inline boilerplate.

    The A/B strip + picker are emitted right after the header only when ``report_key`` and ``root``
    are both given (the cumulative-vs-A/B reports); both self-suppress to '' when ``ab`` is None.
    Reports with a bespoke strip (trend_table's capture-count suffixes) pass report_key=None and place
    their strip at the head of ``body`` instead.

    ``run`` is the report's RunContext (c16e, ADR-35); when it has a current run the header names it
    ("run 2 of 2: <key>"). c16f layers the navigation UX on the same object: an "older run" cue when
    not viewing the newest, a run selector, and a "current vs baseline" banner. ``run_nav_key`` is the
    page's own file stem for the run-selector hrefs (defaults to ``report_key``; the dashboard passes
    'index' since it carries no report_key).
    """
    parts = [page_open(title, hdr_offset_px=hdr_offset_px, body_attrs=body_attrs),
             header(title, drops=drops, captures=captures, build_ts=build_ts,
                    kpis=kpis, crumb_depth=crumb_depth, current_page=current_page,
                    run=run)]
    if device:
        parts.append(device)
    nav_key = run_nav_key or report_key
    reports_up = '../' * (crumb_depth - 1)   # '' from a top-level page, '../../' from a per-run page
    # "older run" cue: viewing a non-newest run is easy to misread as current (c16f).
    if run is not None and nav_key and getattr(run, 'current', None) is not None \
            and not run.is_newest:
        parts.append(callout(
            'warn', 'viewing an older run',
            f'this is run {run.ordinal} ({run.run_label}); the newest run is {run.drops[-1].key}',
            href=f'{reports_up}{nav_key}.html', link_text='go to newest'))
    # A/B strip + picker: only on top-level (newest) pages - per-run pages omit it (a per-run snapshot
    # is single-run; A/B comparison lives on the top-level pages, and its links are _reports-relative).
    if report_key is not None and root is not None and (run is None or run.is_newest):
        parts.append(ab_strip(ab))
        parts.append(ab_picker_for(root, report_key, ab=ab))
    # Run selector + "current vs baseline" banner (every page with >1 run, except A/B pages).
    if ab is None and run is not None and nav_key:
        parts.append(run_picker_for(run, nav_key, reports_up=reports_up,
                                    max_older=_report_max_prerendered_runs()))
        parts.append(run_compare_banner(run.current, getattr(run, 'baseline', None)))
    parts.extend(body if isinstance(body, (list, tuple)) else [body])
    parts.append(page_close())
    return '\n'.join(parts)


def _report_max_prerendered_runs() -> int:
    """The [report] max_prerendered_runs cap (c16f); defensive default for no-config contexts."""
    try:
        from ..config import get_config
        return int(get_config().report.max_prerendered_runs)
    except Exception:
        return 10


def header(title: str, *, drops: int = 0, captures: int = 0,
           build_ts: str = '', kpis: list | None = None,
           crumb_depth: int = 1, current_page: str | None = None, run=None) -> str:
    """Render top page header: h1 + data strip + crumb + optional kpi strip.

    crumb_depth = number of '../' segments to root index.html.
    Chronological reports under _reports/ use 1. A/B under _reports/ab/<pair>/ use 3.

    current_page: if 'dashboard', drops the dashboard self-link from crumb.
                  if 'root', drops the root-catalog self-link.

    run: a RunContext (c16e, ADR-35). When it carries a current run, a "run <ordinal>: <key>" fact
         span is added so the reported run is visible (data-derived key via safe_chrome_text).
    """
    up = '../' * crumb_depth
    crumb_links = []
    if current_page != 'root':
        crumb_links.append(f'<a href="{up}index.html" data-link-kind="crumb">root catalog</a>')
    if current_page != 'dashboard':
        crumb_links.append(f'<a href="{up}_reports/index.html" data-link-kind="crumb">dashboard</a>')
    fact_spans = [f'<span>built <strong>{_html.escape(build_ts)}</strong></span>']
    if drops > 1:
        fact_spans.append(f'<span>drops <strong>{drops}</strong></span>')
    if run is not None and getattr(run, 'current', None):
        fact_spans.append(
            f'<span>run <strong>{_f.safe_chrome_text(run.ordinal)}</strong>: '
            f'<strong>{_f.safe_chrome_text(run.run_label)}</strong></span>')
    parts = [
        f'<h1>{_html.escape(title)}</h1>',
        '<header class="strip">',
        *fact_spans,
        '</header>',
        f'<nav class="crumb">{"".join(crumb_links)}</nav>',
    ]
    if kpis:
        parts.append(kpi_strip(kpis))
    return '\n'.join(parts)


def legend(classes: list[str] | None = None) -> str:
    out = ['<div class="legend">']
    for c in (classes or DRAW_CLASSES):
        out.append(f'<span class="chip"><span class="swatch" '
                   f'style="background: {class_color_var(c)}"></span>{_html.escape(c)}</span>')
    out.append('</div>')
    return '\n'.join(out)


def kpi_chip(label: str, value, *, delta: str | None = None,
             tone: str = 'neutral') -> str:
    """Render one KPI chip. tone in {pos, neg, neutral}."""
    parts = [f'<div class="kpi-chip tone-{h(tone)}">']
    parts.append(f'<div class="kpi-label">{h(label)}</div>')
    parts.append(f'<div class="kpi-value">{h(value)}</div>')
    if delta:
        parts.append(f'<div class="kpi-delta">{h(delta)}</div>')
    parts.append('</div>')
    return ''.join(parts)


def kpi_strip(kpis: list) -> str:
    """Render hero KPI strip below page header."""
    if not kpis:
        return ''
    parts = ['<div class="kpi-strip">']
    for k in kpis:
        parts.append(kpi_chip(
            k.get('label', ''), k.get('value', ''),
            delta=k.get('delta'), tone=k.get('tone', 'neutral'),
        ))
    parts.append('</div>')
    return ''.join(parts)


def section_card(section_id: str, title: str, body: str, *,
                 count: str | int | None = None,
                 subtitle: str | None = None,
                 level: str = 'h2') -> str:
    head_parts = [f'<{level}>{h(title)}</{level}>']
    if count is not None:
        if isinstance(count, int):
            count_str = _f.fmt_int(count)
        else:
            count_str = str(count)
        head_parts.append(f'<span class="card-count">{h(count_str)}</span>')
    sub = (f'<p class="card-subtitle">{h(subtitle)}</p>'
           if subtitle else '')
    return (f'<section class="card" id="{h(section_id)}">'
            f'<header>{"".join(head_parts)}</header>'
            f'{sub}'
            f'{body}'
            f'</section>')


def ab_strip(ab, *, baseline_suffix: str = '', compare_suffix: str = '') -> str:
    """Render the A/B header strip. Empty string when ab is None."""
    if ab is None:
        return ''
    baseline, compare = ab
    return (f'<div class="ab-strip">baseline: {h(baseline.key)}{baseline_suffix} '
            f'| compare: {h(compare.key)}{compare_suffix}</div>')
