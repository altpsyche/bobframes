"""Standalone chrome preview gallery (c08, DESIGNER Track A).

`bobframes preview` renders every visual primitive with NO data dependency, so a designer can edit
reports/design_tokens.toml and reload the page in well under a second. The output is deterministic
(no build timestamp) so it can be golden-gated like the data reports.
"""

from __future__ import annotations

import os

from . import base
from .. import paths as _paths

_PREVIEW_NAME = '_chrome_preview.html'

# Color tokens grouped for the swatch wall (var stems; the page reads them live from :root).
_SWATCH_GROUPS = [
    ('surfaces', ['bg', 'surface-1', 'surface-2', 'code-bg']),
    ('text', ['fg', 'muted', 'text-3']),
    ('borders', ['border', 'border-strong']),
    ('rows', ['row-alt', 'row-hover']),
    ('accents', ['accent-primary', 'accent-data']),
    ('status', ['status-alarm', 'status-warn', 'status-ok', 'status-info']),
]
_TYPE_STEPS = ['fs-display', 'fs-h1', 'fs-h2', 'fs-h3', 'fs-body', 'fs-mono', 'fs-small']
_SPACE_STEPS = ['sp-1', 'sp-2', 'sp-3', 'sp-4', 'sp-6', 'sp-8', 'sp-12']


def _swatch_wall() -> str:
    rows = []
    for gname, stems in _SWATCH_GROUPS:
        chips = ''.join(
            f'<span class="chip"><span class="swatch" '
            f'style="background: var(--{s}); border: 1px solid var(--border-1)"></span>'
            f'{base.h(s)}</span>'
            for s in stems)
        rows.append(f'<div class="legend"><span class="cat-meta">{base.h(gname)}</span>{chips}</div>')
    rows.append('<div class="cat-meta">draw classes</div>')
    rows.append(base.legend())
    return ''.join(rows)


def _type_scale() -> str:
    return ''.join(
        f'<p style="font-size: var(--{s}); margin: var(--sp-1) 0">{base.h(s)} 0123 sample</p>'
        for s in _TYPE_STEPS)


def _spacing_scale() -> str:
    bars = []
    for s in _SPACE_STEPS:
        bars.append(
            f'<div style="display: flex; align-items: center; gap: var(--sp-2); '
            f'margin: var(--sp-1) 0">'
            f'<span style="display: inline-block; width: var(--{s}); height: 12px; '
            f'background: var(--accent-data)"></span>'
            f'<span class="cat-meta">{base.h(s)}</span></div>')
    return ''.join(bars)


def _bars_block() -> str:
    weights = {c: (i + 1) * 12 for i, c in enumerate(base.DRAW_CLASSES)}
    total = sum(weights.values())
    out = ['<div class="table-wrap">', base.legend(),
           '<div class="bar-row">',
           '<span class="key">sample area / drop</span>',
           base.class_segments_bar(weights, total),
           f'<span class="total">{base.fmt_int(total)}</span>',
           '</div></div>',
           f'<p class="note">inline bar at 60 percent: {base.inline_bar(60, 100)}</p>']
    return ''.join(out)


def _deltas_block() -> str:
    pills = [
        ('drop', base.delta_pill(80, 100)),
        ('rise', base.delta_pill(120, 100)),
        ('flat', base.delta_pill(100, 100)),
        ('new', base.delta_pill(50, None)),
    ]
    chips = ''.join(f'<span class="chip">{base.h(lbl)} {pill}</span>' for lbl, pill in pills)
    ranks = ''.join(base.rank_pill(n) for n in (1, 2, 3, 4))
    return f'<div class="legend">{chips}</div><p class="note">ranks: {ranks}</p>'


def _sparkline_block() -> str:
    full = base.sparkline_svg([3, 5, 4, 8, 6, 9, 7])
    gapped = base.sparkline_svg([3, 5, None, 8, 6, None, 7])
    return (f'<p class="note">trend <span class="spark">{full}</span> '
            f'with gaps <span class="spark">{gapped}</span></p>')


def _table_block() -> str:
    # c16l (ADR-38): table.report is retired; the gallery demos the unified `table.data` (bare, like a
    # dashboard mini - no <rdc-table> wrapper needed for a static 3-row sample).
    head = ('<div class="table-wrap"><table class="data"><thead><tr>'
            '<th>name</th><th class="num">draws</th><th class="num">gpu ms</th>'
            '</tr></thead><tbody>')
    rows = []
    for name, draws, gpu in [('opaque pass', 1820, 4.2), ('shadow pass', 940, 2.1),
                             ('ui pass', 120, 0.4)]:
        rows.append(f'<tr><td>{base.h(name)}</td>'
                    f'<td class="num">{base.fmt_int(draws)}</td>'
                    f'<td class="num">{base.fmt_float(gpu, 1)}</td></tr>')
    return head + ''.join(rows) + '</tbody></table></div>'


def _links_block() -> str:
    return ('<div class="chip-cluster">'
            + base.link('#', 'primary action', kind='primary')
            + base.link('#', 'inline link', kind='inline', icon_name='link-out')
            + base.link('#', 'drill row', kind='drill')
            + '</div>')


# c16x-5: the build-health one-pager components (kpi_card / trendline / status_badge / movement) are
# [data-page-kind="summary"]-scoped, so each demo is wrapped in a matching <div> for the gallery.

def _kpi_cards_block() -> str:
    cards = [
        base.kpi_card('avg draws / frame', base.fmt_int(28410),
                      delta_html='<span class="delta-pill neg">+4%</span>',
                      trend=base.trendline([3, 5, 4, 8, 6, 9, 7], tone='neg'),
                      note='5 areas - 142,050 total', tone='neg'),
        base.kpi_card('avg gpu / frame', base.fmt_float(12.8, 4),
                      delta_html='<span class="delta-pill pos">-1%</span>',
                      trend=base.trendline([9, 7, 8, 6, 6, 5, 5], tone='pos'),
                      note='0.064 s total', tone='pos'),
    ]
    return ('<div data-page-kind="summary"><div class="kpi-strip">'
            + ''.join(cards) + '</div></div>')


def _trendline_block() -> str:
    return ('<div data-page-kind="summary">'
            + base.trendline([3, 5, 4, 8, 6, 9, 7], tone='neg') + '</div>')


def _status_badges_block() -> str:
    badges = ''.join(base.status_badge(s, s.replace('_', ' '))
                     for s in ('OK', 'AT_RISK', 'ALARM', 'UNKNOWN'))
    return f'<div data-page-kind="summary" class="chip-cluster">{badges}</div>'


def _movement_block() -> str:
    imp = '<ul class="change-list"><li>draw calls <span class="delta-pill pos">-12%</span></li></ul>'
    reg = '<ul class="change-list"><li>worst shader <span class="delta-pill neg">+30%</span></li></ul>'
    body = base.movement(
        [('Improvements', imp), ('Regressions', reg)],
        rollup_html='<p class="note dim mv-rollup">1 resolved / 1 newly un-instanced</p>')
    return f'<div data-page-kind="summary">{body}</div>'


def _callouts_block() -> str:
    return ''.join(base.callout(sev, f'{sev} callout',
                                'one-line detail for the callout primitive.')
                   for sev in ('ok', 'warn', 'alarm', 'info'))


def _empty_state_block() -> str:
    return base.empty_state('no rendered run data yet')


def build(root: str, *, theme: dict | None = None) -> str:
    """Write the chrome preview gallery to <root>/_reports/_chrome_preview.html; return the path.

    ``theme`` (v0.2.6-1c/ADR-45): an allowlisted color-override map (`--accent`/`[theme]`) so a designer
    previews their accent without rendered data. None -> byte-identical to the golden preview gallery."""
    out_dir = _paths.reports_dir(root)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, _PREVIEW_NAME)

    bad = base.theme_undefined_tokens(theme)
    if bad:
        import logging
        logging.getLogger('bobframes').warning(
            'theme override introduces undefined token ref(s): %s', sorted(bad))

    kpis = [
        {'label': 'total draws', 'value': base.fmt_int(28410), 'delta': '+4.2%', 'tone': 'neg'},
        {'label': 'gpu ms', 'value': base.fmt_float(12.8, 1), 'delta': '-1.1%', 'tone': 'pos'},
        {'label': 'shaders', 'value': base.fmt_int(512), 'delta': '0', 'tone': 'neutral'},
    ]

    # Self-contained gallery: page_open/page_close directly (no header crumb or build strip), so the
    # page is deterministic and has no link dependency on the catalog/dashboard pages.
    parts = [
        base.page_open('chrome preview', hdr_offset_px=120, theme=theme),
        '<h1>chrome preview</h1>',
        '<p class="note">every primitive from design_tokens.toml + chrome, no data needed. '
        'edit reports/design_tokens.toml and rerun to see your changes.</p>',
        base.kpi_strip(kpis),
        base.summary_bar('sample headline', 'opaque 62.0%',
                         sub='across 5 areas; next: shadow 18.0%, ui 9.0%',
                         link_href='#', link_text='detail', tone='neutral'),
        base.section_card('colors', 'colors', _swatch_wall()),
        base.section_card('type', 'type scale', _type_scale()),
        base.section_card('spacing', 'spacing scale', _spacing_scale()),
        base.section_card('bars', 'bars', _bars_block()),
        base.section_card('deltas', 'delta pills + ranks', _deltas_block()),
        base.section_card('spark', 'sparklines', _sparkline_block()),
        base.section_card('table', 'table rows', _table_block()),
        base.section_card('links', 'link kinds', _links_block()),
        base.section_card('kpi_cards', 'kpi cards', _kpi_cards_block()),
        base.section_card('trendline', 'trendline', _trendline_block()),
        base.section_card('status', 'status badges', _status_badges_block()),
        base.section_card('movement', 'movement', _movement_block()),
        base.section_card('callouts', 'callouts', _callouts_block()),
        base.section_card('empty', 'empty state', _empty_state_block()),
        base.page_close(),
    ]
    html = '\n'.join(parts)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    base._lint_or_raise(out_path)
    # c16x-3 (ADR-42, G-30): warn (non-fatal) in the designer's own loop if a token reference is
    # undefined - the typo that silently zeroed the chip padding. CI hard-gates this (test_token_guard);
    # here it is a heads-up, never a crash (a styling typo must not break `preview`/`render`).
    undefined = base.undefined_tokens()
    if undefined:
        import sys
        print('warning: design tokens referenced but not defined: '
              + ', '.join('--' + t for t in sorted(undefined))
              + ' (typo? add to design_tokens.toml or define --NAME in a CSS rule)', file=sys.stderr)
    return out_path
