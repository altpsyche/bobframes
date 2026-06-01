"""Page chrome: CSS tokens, page open/close, header, KPI strip, section card, legend, footer."""

from __future__ import annotations

import html as _html
import string as _string

from . import formatters as _f
from . import _tokens
from ..derives import classifier as _classifier


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
  padding: 0 0 0 var(--sp-3);
  border-left: 3px solid var(--accent);
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
table.report a { text-decoration: underline; text-decoration-thickness: 1px;
                 text-underline-offset: 2px; }
table.report a:visited { color: var(--text-3); }

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
  border: 1px solid var(--border-1);
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
  font: 600 var(--fs-display)/1.05 ui-monospace, monospace;
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
  border: 1px solid var(--border-1);
  border-radius: 4px;
  margin: 0 0 var(--sp-6);
}
.table-wrap > table.report { border: 0; margin: 0; }

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

table.report {
  width: 100%;
  border-collapse: collapse;
  font: var(--fs-mono) ui-monospace, 'Cascadia Code', Consolas, monospace;
  margin-top: var(--sp-1);
}
table.report thead th {
  position: sticky;
  top: var(--hdr-offset);
  background: var(--surface-2); color: var(--accent);
  text-align: left; font-weight: 600;
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-2);
  white-space: nowrap;
  z-index: 1;
}
table.report thead th.num { text-align: right; }
table.report tbody td {
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border-1);
  vertical-align: top;
}
table.report tbody td:first-child {
  font-weight: 600; color: var(--text-1);
}
table.report td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.report tbody tr:nth-child(even) td { background: var(--surface-2); }
table.report tbody tr:hover td { background: var(--row-hover); }
table.report tbody td .lbl {
  color: var(--text-2);
  margin-left: 6px;
  font-style: italic;
  opacity: .85;
}
table.report tr.area-break td { border-top: 2px solid var(--border-2); }
table.report td.area-cell { color: var(--text-2); }

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
             background: var(--surface-1); border: 1px solid var(--border-1);
             border-radius: 2px; }
.chart-svg text { font: var(--fs-small) ui-monospace, monospace; fill: var(--text-2); }
details.secondary-metrics { margin: var(--sp-2) 0 var(--sp-4); }
details.secondary-metrics > summary { cursor: pointer; color: var(--text-2);
                                      font-size: var(--fs-small); padding: var(--sp-1) 0; }

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
.delta.alarm { border-left: 3px solid var(--status-alarm); padding-left: 6px; }
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
  border: 1px solid var(--border-1);
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

.callout {
  display: flex; align-items: flex-start; gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4); margin: 0 0 var(--sp-4);
  background: var(--surface-1); border: 1px solid var(--border-1);
  border-left: 3px solid var(--text-3); font-size: var(--fs-small);
}
.callout .icon { flex: 0 0 auto; margin-top: 2px; color: var(--text-3); }
.callout .co-body { display: flex; flex-direction: column; gap: 2px; }
.callout .co-title { font-weight: 600; color: var(--text-1); }
.callout .co-detail { color: var(--text-2); }
.callout a { color: var(--accent-primary); }
.callout.sev-ok { border-left-color: var(--status-ok); }
.callout.sev-ok .icon { color: var(--status-ok); }
.callout.sev-warn { border-left-color: var(--status-warn); }
.callout.sev-warn .icon { color: var(--status-warn); }
.callout.sev-alarm { border-left-color: var(--status-alarm); }
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
a.dash-card { border: 1px solid var(--border-1);
              padding: var(--sp-4); display: flex; flex-direction: column;
              gap: var(--sp-3); text-decoration: none; color: inherit;
              transition: border-color 0.1s, background 0.1s; }
a.dash-card:hover { background: var(--surface-1); border-color: var(--border-2);
                    text-decoration: none; }
a.dash-card:visited { color: inherit; }
a.dash-card h3 { margin: 0; color: var(--accent); font-size: var(--fs-h2);
                 border-left: 3px solid var(--accent); padding-left: var(--sp-3); }
a.dash-card table.report { font-size: var(--fs-small); }
a.dash-card table.report a { pointer-events: none; }
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
  border: 1px solid var(--border-1);
  border-top: 2px solid var(--accent-data);
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
  font: 600 var(--fs-h1)/1.15 ui-monospace, monospace;
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
  table.report thead th,
  table.report tbody td { padding: var(--sp-1) var(--sp-2); }
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
    border-color: #888;
    border-top-width: 3px;
    break-inside: avoid;
    break-after: avoid;
    print-color-adjust: exact;
  }
  .summary-bar .sb-headline { color: #000; }
  .summary-bar .sb-link { display: none; }

  h1, h2 { color: #000; }
  h2[id] { position: static; background: transparent; break-after: avoid; }
  table.report thead th {
    position: static;
    background: #f0f0f0;
    color: #000;
    print-color-adjust: exact;
  }
  table.report thead { display: table-header-group; }
  table.report tbody tr { break-inside: avoid; }

  .kpi-strip { break-inside: avoid; grid-template-columns: repeat(4, 1fr); }
  .kpi-chip { background: #fff; border-color: #888; }
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
rdc-sortable-table { display: block; }
rdc-sortable-table table.report thead th { cursor: pointer; user-select: none; }
rdc-sortable-table table.report thead th[aria-sort="ascending"]::after {
  content: ' \\25B4'; color: var(--text-3);
}
rdc-sortable-table table.report thead th[aria-sort="descending"]::after {
  content: ' \\25BE'; color: var(--text-3);
}

rdc-copy-button {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 28px; padding: 0 6px; height: 22px;
  color: var(--text-2);
  cursor: pointer;
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
rdc-sticky-h2 h2[aria-current="section"] {
  border-left-color: var(--accent-data);
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
.pair-group { border: 1px solid var(--border-1); padding: var(--sp-3) var(--sp-4); background: var(--surface-1); }
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

  class RdcSortableTable extends RdcBase {
    init(){
      const table = this.querySelector('table');
      if (!table) return;
      this._table = table;
      const ths = table.querySelectorAll('thead th');
      this._ths = ths;
      ths.forEach((th, ci) => {
        const isNum = th.classList.contains('num');
        th.setAttribute('aria-sort', 'none');
        th.addEventListener('click', () => this.sort(ci, isNum));
      });
      const liveId = 'rdc-live-' + Math.random().toString(36).slice(2, 8);
      const live = document.createElement('div');
      live.id = liveId;
      live.setAttribute('aria-live', 'polite');
      live.setAttribute('aria-atomic', 'true');
      live.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)';
      this.appendChild(live);
      this._live = live;
      const def = this.dataset.defaultSort;
      const dir = this.dataset.defaultDir || 'desc';
      if (def){
        const cols = Array.from(ths).map(th => th.textContent.trim().toLowerCase());
        const idx = cols.indexOf(def.toLowerCase());
        if (idx >= 0){
          const isNum = ths[idx].classList.contains('num');
          this._applySort(idx, isNum, dir === 'asc' ? 'ascending' : 'descending');
        }
      }
    }
    sort(ci, isNum){
      const cur = this._ths[ci].getAttribute('aria-sort') || 'none';
      const dir = cur === 'ascending' ? 'descending' : 'ascending';
      this._applySort(ci, isNum, dir);
    }
    _applySort(ci, isNum, dir){
      const tbody = this._table.tBodies[0];
      if (!tbody) return;
      const rows = Array.from(tbody.rows);
      rows.sort((a, b) => {
        const av = (a.cells[ci] ? a.cells[ci].textContent : '').trim();
        const bv = (b.cells[ci] ? b.cells[ci].textContent : '').trim();
        if (isNum){
          const an = parseFloat(av.replace(/,/g, ''));
          const bn = parseFloat(bv.replace(/,/g, ''));
          const aok = !isNaN(an), bok = !isNaN(bn);
          if (!aok && !bok) return 0;
          if (!aok) return 1;
          if (!bok) return -1;
          return dir === 'ascending' ? an - bn : bn - an;
        }
        return dir === 'ascending' ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(r => tbody.appendChild(r));
      this._ths.forEach(th => th.setAttribute('aria-sort', 'none'));
      this._ths[ci].setAttribute('aria-sort', dir);
      if (this._live) {
        const colName = (this._ths[ci].textContent || '').trim();
        this._live.textContent = 'sorted by ' + colName + ' ' + dir;
      }
    }
  }
  customElements.define('rdc-sortable-table', RdcSortableTable);

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
      const h2 = this.querySelector('h2[id]');
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
_PRIMITIVES_CSS = _CHROME_CSS + _LINK_KIND_CSS + _STICKY_CSS + _CONTAINER_CSS + _PRINT_CSS
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
    return _minify_css(_TOKENS_CSS + _PRIMITIVES_CSS + _COMPONENTS_CSS)


def _compose_js() -> str:
    return _minify_js(_COMPONENTS_JS)


_CSS = _compose_css()


def design_tokens_css() -> str:
    """Return :root tokens CSS for reuse in template.py."""
    return _TOKENS_CSS


def chrome_css() -> str:
    """Return primitives + components CSS (without tokens). Used by template.py."""
    return _PRIMITIVES_CSS + _COMPONENTS_CSS


def components_js() -> str:
    """Return Web Components JS blob. Used by template.py."""
    return _COMPONENTS_JS


def h(s) -> str:
    return _html.escape(str(s if s is not None else ''))


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
                report_key: str | None = None, device: str = '') -> str:
    """Assemble a standard Layer-2 report page, deduping the open/header/strip/close shared by every
    report (Q-6). ``body`` is an HTML string or a list of fragments (the report's summary_bar +
    sections, in order). The fragments are '\\n'-joined exactly as write_report joins a parts list, so
    routing a report through this helper is byte-identical to the old inline boilerplate.

    The A/B strip + picker are emitted right after the header only when ``report_key`` and ``root``
    are both given (the cumulative-vs-A/B reports); both self-suppress to '' when ``ab`` is None.
    Reports with a bespoke strip (trend_table's capture-count suffixes) pass report_key=None and place
    their strip at the head of ``body`` instead.
    """
    parts = [page_open(title, hdr_offset_px=hdr_offset_px, body_attrs=body_attrs),
             header(title, drops=drops, captures=captures, build_ts=build_ts,
                    kpis=kpis, crumb_depth=crumb_depth, current_page=current_page)]
    if device:
        parts.append(device)
    if report_key is not None and root is not None:
        parts.append(ab_strip(ab))
        parts.append(ab_picker_for(root, report_key, ab=ab))
    parts.extend(body if isinstance(body, (list, tuple)) else [body])
    parts.append(page_close())
    return '\n'.join(parts)


def header(title: str, *, drops: int = 0, captures: int = 0,
           build_ts: str = '', kpis: list | None = None,
           crumb_depth: int = 1, current_page: str | None = None) -> str:
    """Render top page header: h1 + data strip + crumb + optional kpi strip.

    crumb_depth = number of '../' segments to root index.html.
    Chronological reports under _reports/ use 1. A/B under _reports/ab/<pair>/ use 3.

    current_page: if 'dashboard', drops the dashboard self-link from crumb.
                  if 'root', drops the root-catalog self-link.
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
