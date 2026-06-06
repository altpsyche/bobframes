"""Top fragment shaders by complexity * uses.

Reads _reports/_cache/shader_summary_per_drop.parquet when present; falls
back to live scan of **/shaders.parquet.
"""

from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as papq

from . import base
from .. import aggregates as _agg
from ..config import get_config


_SHADER_COLS = [
    'area', 'drop_date', 'drop_label', 'capture', 'shader_id', 'stable_key',
    'shader_type', 'src_len', 'complexity_score', 'total_branches',
    'total_loops', 'total_discards', 'total_dfdx_dfdy',
    'total_texture_samples', 'used_by_draw_count', 'src_file_path',
    'fb_fetch', 'uses_cubemap',
]


def _iter_shaders(root: str, drops: list):
    t = base.load_cached(root, 'shader_summary')  # validates sha256 sidecar; None -> live scan (R-13)
    if t is not None:
        cols = base._to_dict_of_lists(t)
        wanted = {(d.date, d.label) for d in drops}
        for i in range(t.num_rows):
            if (cols['drop_date'][i], cols['drop_label'][i]) not in wanted:
                continue
            yield {c: cols[c][i] for c in cols}
        return
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'shaders.parquet')
            if not os.path.exists(p):
                continue
            schema_cols = set(papq.read_schema(p).names)
            want = [c for c in _SHADER_COLS if c in schema_cols]
            try:
                t = papq.read_table(p, columns=want)
            except Exception:
                continue
            cols = base._to_dict_of_lists(t)   # Q-7
            for i in range(t.num_rows):
                row = {c: cols[c][i] for c in cols}
                row['drop_date'] = r.drop_date
                row['drop_label'] = r.drop_label
                yield row


def _drop_dir_first(drops: list, drop_date, drop_label) -> str:
    for d in drops:
        if d.date == drop_date and d.label == drop_label and d.rows:
            return d.rows[0].drop_dir
    return ''


def build(root: str, *, drops: list | None = None, ab=None,
          stage: str = 'fragment', run_label=None, run_date=None,
          sink: base.AssetSink = base.AssetSink.INLINE,
          build_ts: str | None = None, redact: bool = False, theme: dict | None = None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    # Run model (ADR-35): the hotlist ranks the CURRENT run's shaders; prior runs feed the per-drop
    # comparison columns + the resolved-since section, never the cost ranking.
    rc = base.run_context(drops, run_label=run_label, run_date=run_date)
    cur = rc.current
    bl = rc.baseline
    ck = cur.key if cur else None
    out_path = base.output_path(root, 'shader_hotlist', ab, run=rc)
    out_dir = os.path.dirname(out_path)

    drop_keys = [d.key for d in drops]

    per_key: dict = defaultdict(lambda: {
        'uses_by_drop': Counter(),
        'complexity': 0.0,
        'branches': 0,
        'loops': 0,
        'discards': 0,
        'dfdx_dfdy': 0,
        'tex_samples': 0,
        'src_len': 0,
        'shader_type': '',
        'rep_drop_date': None,
        'rep_drop_label': None,
        'rep_shader_id': 0,
        'rep_src_path': '',
        'rep_capture': '',
        'fb_fetch': False,
        'uses_cubemap': False,
    })

    for row in _iter_shaders(root, drops):
        stype = row.get('shader_type') or ''
        if stage and stype != stage:
            continue
        sk = row.get('stable_key') or ''
        if not sk:
            continue
        p = per_key[sk]
        p['complexity'] = max(p['complexity'], float(row.get('complexity_score') or 0))
        p['branches'] = max(p['branches'], int(row.get('total_branches') or 0))
        p['loops'] = max(p['loops'], int(row.get('total_loops') or 0))
        p['discards'] = max(p['discards'], int(row.get('total_discards') or 0))
        p['dfdx_dfdy'] = max(p['dfdx_dfdy'], int(row.get('total_dfdx_dfdy') or 0))
        p['tex_samples'] = max(p['tex_samples'], int(row.get('total_texture_samples') or 0))
        p['src_len'] = max(p['src_len'], int(row.get('src_len') or 0))
        p['shader_type'] = stype
        if row.get('fb_fetch'):
            p['fb_fetch'] = True
        if row.get('uses_cubemap'):
            p['uses_cubemap'] = True
        if p['rep_shader_id'] == 0 and row.get('shader_id'):
            p['rep_drop_date'] = row['drop_date']
            p['rep_drop_label'] = row['drop_label']
            p['rep_shader_id'] = row.get('shader_id') or 0
            p['rep_src_path'] = row.get('src_file_path') or ''
            p['rep_capture'] = row.get('capture') or ''

    # Single-source the uses atom (G-26, aggregates): used_by_draw_count summed per (drop, area, sk),
    # collapsed across areas into the cross-area per-(sk, drop) Counter this report displays. Same stage
    # filter + cache as the metadata loop, so byte-for-byte the old inline `uses_by_drop` - including the
    # presence semantics (a 0-uses row still seeds its drop_key via Counter += 0). c16v normalizes uses
    # per frame here (cost = complexity x per-frame-uses; complexity stays a per-shader max).
    _sa = _agg.shader_aggregates(root, drops, stage=stage)
    _uses_by_key: dict = defaultdict(Counter)
    for (dk, area, sk2), u in _sa.uses.items():
        _uses_by_key[sk2][dk] += base.per_frame(u, _sa.frames(dk, area))   # c16v: uses per frame, per-area summed
    for sk, p in per_key.items():
        p['uses_by_drop'] = _uses_by_key.get(sk, Counter())

    # Run model (ADR-35): rank the shaders PRESENT in the current run (a shader appears in a drop iff
    # ck is a key in its uses_by_drop), ordered by current-run cost proxy. Presence - not uses>0 - is
    # the scope so the report still lists shaders when used_by_draw_count is unpopulated; a shader
    # present only in an older run drops out (it surfaces in resolved-since instead).
    present = [(sk, p) for sk, p in per_key.items() if ck in p['uses_by_drop']]
    ranked = []
    for sk, p in present:
        cur_uses = p['uses_by_drop'].get(ck, 0)
        cost = p['complexity'] * cur_uses
        ranked.append((sk, p, cur_uses, cost))
    ranked.sort(key=lambda x: x[3], reverse=True)
    ranked = ranked[:50]

    max_cost = max((c for _, _, _, c in ranked), default=0.0)

    parts = []
    rcfg = get_config().report

    # Hero KPIs + over-budget count, over the shaders present in the CURRENT run (not the top 50).
    live_cplx = [p['complexity'] for _, p in present]
    max_cplx = max(live_cplx, default=0.0)
    n_over = sum(1 for c in live_cplx if c >= rcfg.shader_complexity_high)
    kpis = [
        {'label': f'{stage} shaders', 'value': base.fmt_int(len(present))},
        {'label': 'max complexity', 'value': base.fmt_float(max_cplx, 1),
         'tone': 'neg' if max_cplx >= rcfg.shader_complexity_high else 'neutral'},
        {'label': f'>= cplx {base.fmt_float(rcfg.shader_complexity_high, 0)}',
         'value': base.fmt_int(n_over)},
    ]

    # Summary bar: top shader by cost proxy
    if ranked:
        sk, p, total_uses, cost = ranked[0]
        label_top = f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}'
        parts.append(base.summary_bar(
            'top shader',
            f'{label_top}',
            sub=f'{base.fmt_int(total_uses)} uses in the current run',
            link_href='#shaders',
            link_text='table',
            tone='neutral',
        ))
        # Insight: shaders above the complexity budget are the optimization targets.
        if n_over > 0:
            sev = 'warn' if max_cplx >= rcfg.shader_complexity_high * 1.25 else 'info'
            parts.append(base.callout(
                sev,
                f'{n_over} {stage} shader(s) exceed complexity {base.fmt_float(rcfg.shader_complexity_high, 0)}',
                f'highest is {base.fmt_float(max_cplx, 1)} - review instruction count / variants on the '
                f'hot shaders (cost = complexity x uses).',
                href='#shaders', link_text='shader table'))

    # c16c: the single shader section is framed in a sticky-highlighted card.
    sbody = []
    if not ranked:
        sbody.append(base.empty_state(f'no {stage} shaders found'))
    else:
        single = len(drop_keys) == 1

        # Flagship: complexity x cost scatter (bubble = src bytes) + complexity histogram (c16b).
        scatter_pts = [
            (p['complexity'], cost, p['src_len'],
             f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}')
            for sk, p, total_uses, cost in ranked
        ]
        sbody.append(base.figure(
            base.scatter(scatter_pts, x_label='complexity', y_label='cost', bubble=True,
                         title='complexity vs cost',
                         desc='each point is a shader; x complexity, y cost proxy, bubble src bytes',
                         chart_id='shader-sc'),
            'shader complexity vs cost (bubble = src bytes)'))
        sbody.append(base.figure(
            base.histogram(live_cplx, bins=12, title='complexity distribution',
                           desc=f'distribution of complexity across {len(live_cplx)} current-run shaders',
                           chart_id='shader-hist'),
            'complexity distribution (current run)'))

        # Primary (diet) table -> the c16k STATIC-mode rdc-table proof (ADR-38): rows stay SERVER-BAKED
        # (golden-visible, readable JS-off, printable, Ctrl-F-able); JS only enhances IN PLACE (client
        # sort, .num/.mono type-split, uniform-tint heatmap, collapsible column groups).
        # v0.2.6-4: adopt the data_table component (ADR-43; golden absorbs the normalization). Per-drop
        # header text repeats, so the col-groups still key by INDEX -- colgroups_from derives those from
        # each Column's `group` tag by position. identity (shader + src) + cost open; the per-drop
        # history wall (per-drop uses + delta + trend) collapsed, dropped when single-drop.
        cols = [base.Column('shader', 'shader', group='identity', render=lambda value, row: value),
                base.Column('complexity', 'complexity', numeric=True, group='cost',
                            title='shader complexity score (weighted instruction proxy)',
                            render=lambda value, row: base.heatmap_cell(
                                value, 0, row['_maxc'], text=base.fmt_float(value, 2))),
                base.Column('uses_cur', 'uses (current)', numeric=True, group='cost',
                            title='used-by-draw count in the current run')]
        for i, k in enumerate(drop_keys):
            head = 'uses' if single else base.raw(f'uses<span class="dim">@{base.h(k)}</span>')
            cols.append(base.Column(f'u{i}', head, numeric=True,
                                    group='cost' if single else 'history'))
            if i > 0:
                cols.append(base.delta_column(f'd{i}', latest=(i == len(drop_keys) - 1),
                                              group='history'))
        if len(drop_keys) >= 3:
            cols.append(base.Column('trend', 'trend', numeric=True, group='history',
                                    render=lambda value, row: base.sparkline_svg(value)))
        cols.append(base.Column('cost', 'cost proxy', numeric=True, group='cost',
                                title='cost proxy = complexity x total uses',
                                render=lambda value, row: base.heatmap_cell(
                                    value, 0, row['_maxcost'], text=base.fmt_float(value, 1))))
        cols.append(base.Column('flags', 'flags', group='cost'))
        cols.append(base.Column('src', 'src', mono=True, group='identity',
                                render=lambda value, row: value))

        rows = []
        for rank_i, (sk, p, total_uses, cost) in enumerate(ranked, 1):
            rp = base.rank_pill(rank_i) if rank_i <= 3 else ''
            shader_label = f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}'
            drop_dir = _drop_dir_first(drops, p['rep_drop_date'], p['rep_drop_label'])
            src_link = base.rel_path_to_drop_file(out_dir, drop_dir, p['rep_src_path'])
            copy_id = (f'<rdc-copy-button data-value="{base.safe_chrome_text(sk)}" '
                       f'data-label="copy shader id"></rdc-copy-button>')
            if src_link:
                shader_html = (f'{rp}<a href="{base.h(src_link)}" data-link-kind="inline" target="_blank" '
                               f'rel="noopener">{base.h(shader_label)}{base.icon("link-out")}</a>{copy_id}')
                # c16m: clip the path text (wide tier) on an inner span so the file icon + the copy
                # button ride OUTSIDE the clip; the copy data-value keeps the FULL path (c16c).
                src_html = (f'<a href="{base.h(src_link)}" data-link-kind="inline" target="_blank" '
                            f'rel="noopener">{base.clip_span(p["rep_src_path"], tier="wide")}'
                            f'{base.icon("file")}</a>'
                            f'<rdc-copy-button data-value="{base.safe_chrome_text(p["rep_src_path"])}" '
                            f'data-label="copy src path"></rdc-copy-button>')
            else:
                shader_html = f'{rp}{base.h(shader_label)}{copy_id}'
                src_html = ''
            flags = []
            if p['fb_fetch']:
                flags.append('fb_fetch')
            if p['uses_cubemap']:
                flags.append('cubemap')
            row = {'shader': shader_html, 'complexity': p['complexity'], '_maxc': max_cplx,
                   'uses_cur': base.fmt_int(total_uses), 'cost': cost, '_maxcost': max_cost,
                   'flags': ','.join(flags), 'src': src_html}
            prev = None
            series = []
            for i, k in enumerate(drop_keys):
                v = p['uses_by_drop'].get(k, 0)
                series.append(v)
                row[f'u{i}'] = base.fmt_int(v)
                if i > 0:
                    row[f'd{i}'] = base.delta_parts(v, prev, lower_is_better=None,
                                                   fmt='{:+,.0f}', regression_threshold_pct=None)
                prev = v
            if len(drop_keys) >= 3:
                row['trend'] = series
            rows.append(row)

        colgroups = base.colgroups_from(cols, {'identity': True, 'cost': True, 'history': False})
        sbody.append(str(base.data_table(cols, rows, table_key='shader_hotlist',
                                         default_sort='cost proxy', default_dir='desc',
                                         caption=f'top {stage} shaders ranked by cost proxy',
                                         colgroups=colgroups)))

        # Secondary metrics (collapsed): per-shader instruction-mix detail (c16b column diet). The
        # <details>/<summary> wrapper stays hand-written (a structural leaf for the -5 el long-tail).
        scols = [base.Column('shader', 'shader'),
                 base.Column('branches', 'branches', numeric=True),
                 base.Column('loops', 'loops', numeric=True),
                 base.Column('discards', 'discards', numeric=True),
                 base.Column('dfdx', 'dfdx/dfdy', numeric=True),
                 base.Column('tex', 'tex samples', numeric=True),
                 base.Column('srcb', 'src bytes', numeric=True)]
        srows = [{'shader': f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}',
                  'branches': base.fmt_int(p['branches']), 'loops': base.fmt_int(p['loops']),
                  'discards': base.fmt_int(p['discards']), 'dfdx': base.fmt_int(p['dfdx_dfdy']),
                  'tex': base.fmt_int(p['tex_samples']), 'srcb': base.fmt_int(p['src_len'])}
                 for sk, p, total_uses, cost in ranked]
        sbody.append(base.el('details', {'class': 'secondary-metrics'},
                             base.el('summary', None, 'secondary metrics'),
                             base.data_table(scols, srows, table_key='shader_secondary',
                                             caption='per-shader instruction-mix detail')))

    parts.append('<rdc-sticky-h2>'
                 + base.section_card('shaders', f'top {stage} shaders by cost',
                                     ''.join(sbody), count=len(ranked))
                 + '</rdc-sticky-h2>')

    # Resolved since baseline (ADR-35): shaders used in the baseline run but unused in the current run
    # - a win, surfaced separately (fill-or-hide) so it never inflates the live hotlist.
    if bl is not None:
        resolved = sorted(
            ((sk, p) for sk, p in per_key.items()
             if bl.key in p['uses_by_drop'] and ck not in p['uses_by_drop']),
            key=lambda kv: (kv[1]['uses_by_drop'].get(bl.key, 0), kv[1]['complexity']),
            reverse=True)
        if resolved:
            rcols = [base.Column('shader', 'shader'),
                     base.Column('complexity', 'complexity', numeric=True),
                     base.Column('uses', f'uses@{bl.key}', numeric=True)]
            rrows = [{'shader': f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}',
                      'complexity': base.fmt_float(p['complexity'], 2),
                      'uses': base.fmt_int(p['uses_by_drop'].get(bl.key, 0))}
                     for sk, p in resolved[:30]]
            rbody = base.data_table(rcols, rrows, table_key='shader_resolved',
                                    caption=f'{stage} shaders present in {bl.key} but gone in {ck} '
                                            '- removed or retired')
            parts.append('<rdc-sticky-h2>'
                         + base.section_card('resolved', f'resolved since {bl.key}',
                                             str(rbody), count=len(resolved))
                         + '</rdc-sticky-h2>')

    return base.write_report(out_path, [base.report_page(
        f'shader hotlist ({stage})', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=build_ts or base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
        ab=ab, root=root, report_key='shader_hotlist', sink=sink, theme=theme,
        kpis=kpis, run=rc,
        device=base.provenance_strip(*base.newest_drop_provenance(root, [cur] if cur else []), redact=redact))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='shader_hotlist'))
