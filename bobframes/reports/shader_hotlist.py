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
          stage: str = 'fragment', run_label=None, run_date=None) -> str:
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
        drop_key = f"{row['drop_date']}_{row['drop_label']}"
        p = per_key[sk]
        p['uses_by_drop'][drop_key] += int(row.get('used_by_draw_count') or 0)
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

        # Primary (diet) table: shader / complexity / uses / cost / flags / src (c16b column diet).
        sec = ['<div class="table-wrap">'
               '<rdc-sortable-table data-default-sort="cost proxy" data-default-dir="desc">',
               '<table class="report">',
               f'<caption>top {stage} shaders ranked by cost proxy</caption>',
               '<thead><tr>', '<th scope="col">shader</th>',
               '<th class="num" scope="col" title="shader complexity score (weighted instruction proxy)">complexity</th>',
               '<th class="num" scope="col" title="used-by-draw count in the current run">uses (current)</th>']
        for i, k in enumerate(drop_keys):
            head = 'uses' if single else f'uses<span class="dim">@{base.h(k)}</span>'
            sec.append(f'<th class="num" scope="col">{head}</th>')
            if i > 0:
                latest = ' delta-latest' if i == len(drop_keys) - 1 else ''
                sec.append(f'<th class="num{latest}" scope="col">delta</th>')
        if len(drop_keys) >= 3:
            sec.append('<th class="num" scope="col">trend</th>')
        sec.extend([
            '<th class="num" scope="col" title="cost proxy = complexity x total uses">cost proxy</th>',
            '<th scope="col">flags</th>',
            '<th scope="col">src</th>',
            '</tr></thead><tbody>',
        ])

        for rank_i, (sk, p, total_uses, cost) in enumerate(ranked, 1):
            sec.append('<tr>')
            rp = base.rank_pill(rank_i) if rank_i <= 3 else ''
            shader_label = f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}'
            drop_dir = _drop_dir_first(drops, p['rep_drop_date'], p['rep_drop_label'])
            src_link = base.rel_path_to_drop_file(out_dir, drop_dir, p['rep_src_path'])
            copy_id = (f'<rdc-copy-button data-value="{base.safe_chrome_text(sk)}" '
                       f'data-label="copy shader id"></rdc-copy-button>')
            if src_link:
                sec.append(f'<td>{rp}<a href="{base.h(src_link)}" data-link-kind="inline" target="_blank" rel="noopener">{base.h(shader_label)}{base.icon("link-out")}</a>{copy_id}</td>')
            else:
                sec.append(f'<td>{rp}{base.h(shader_label)}{copy_id}</td>')
            sec.append(f'<td class="num">{base.heatmap_cell(p["complexity"], 0, max_cplx, text=base.fmt_float(p["complexity"], 2))}</td>')
            sec.append(f'<td class="num">{base.fmt_int(total_uses)}</td>')
            prev = None
            series = []
            for i, k in enumerate(drop_keys):
                v = p['uses_by_drop'].get(k, 0)
                series.append(v)
                sec.append(f'<td class="num">{base.fmt_int(v)}</td>')
                if i > 0:
                    sec.append(base.delta_cell(v, prev,
                        lower_is_better=None, fmt='{:+,.0f}',
                        regression_threshold_pct=None))
                prev = v
            if len(drop_keys) >= 3:
                sec.append(f'<td class="num">{base.sparkline_svg(series)}</td>')

            sec.append(f'<td class="num">{base.heatmap_cell(cost, 0, max_cost, text=base.fmt_float(cost, 1))}</td>')

            flags = []
            if p['fb_fetch']:
                flags.append('fb_fetch')
            if p['uses_cubemap']:
                flags.append('cubemap')
            sec.append(f'<td>{base.h(",".join(flags))}</td>')

            if src_link:
                sec.append(f'<td><a href="{base.h(src_link)}" data-link-kind="inline" target="_blank" rel="noopener">{base.h(p["rep_src_path"])}{base.icon("file")}</a>'
                           f'<rdc-copy-button data-value="{base.safe_chrome_text(p["rep_src_path"])}" data-label="copy src path"></rdc-copy-button></td>')
            else:
                sec.append('<td></td>')

            sec.append('</tr>')
        sec.append('</tbody></table></rdc-sortable-table></div>')
        sbody.append(''.join(sec))

        # Secondary metrics (collapsed): per-shader instruction-mix detail (c16b column diet).
        det = ['<details class="secondary-metrics"><summary>secondary metrics</summary>',
               '<div class="table-wrap"><rdc-sortable-table>',
               '<table class="report">',
               '<caption>per-shader instruction-mix detail</caption>',
               '<thead><tr>',
               '<th scope="col">shader</th>',
               '<th class="num" scope="col">branches</th>',
               '<th class="num" scope="col">loops</th>',
               '<th class="num" scope="col">discards</th>',
               '<th class="num" scope="col">dfdx/dfdy</th>',
               '<th class="num" scope="col">tex samples</th>',
               '<th class="num" scope="col">src bytes</th>',
               '</tr></thead><tbody>']
        for sk, p, total_uses, cost in ranked:
            shader_label = f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}'
            det.append('<tr>')
            det.append(f'<td>{base.h(shader_label)}</td>')
            det.append(f'<td class="num">{base.fmt_int(p["branches"])}</td>')
            det.append(f'<td class="num">{base.fmt_int(p["loops"])}</td>')
            det.append(f'<td class="num">{base.fmt_int(p["discards"])}</td>')
            det.append(f'<td class="num">{base.fmt_int(p["dfdx_dfdy"])}</td>')
            det.append(f'<td class="num">{base.fmt_int(p["tex_samples"])}</td>')
            det.append(f'<td class="num">{base.fmt_int(p["src_len"])}</td>')
            det.append('</tr>')
        det.append('</tbody></table></rdc-sortable-table></div></details>')
        sbody.append(''.join(det))

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
            rbody = ['<div class="table-wrap"><rdc-sortable-table>',
                     '<table class="report">',
                     f'<caption>{stage} shaders present in {base.h(bl.key)} but gone in {base.h(ck)} - removed or retired</caption>',
                     '<thead><tr>', '<th scope="col">shader</th>',
                     '<th class="num" scope="col">complexity</th>',
                     f'<th class="num" scope="col">uses@{base.h(bl.key)}</th>',
                     '</tr></thead><tbody>']
            for sk, p in resolved[:30]:
                shader_label = f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}'
                rbody.append('<tr>')
                rbody.append(f'<td>{base.h(shader_label)}</td>')
                rbody.append(f'<td class="num">{base.fmt_float(p["complexity"], 2)}</td>')
                rbody.append(f'<td class="num">{base.fmt_int(p["uses_by_drop"].get(bl.key, 0))}</td>')
                rbody.append('</tr>')
            rbody.append('</tbody></table></rdc-sortable-table></div>')
            parts.append('<rdc-sticky-h2>'
                         + base.section_card('resolved', f'resolved since {bl.key}',
                                             ''.join(rbody), count=len(resolved))
                         + '</rdc-sticky-h2>')

    return base.write_report(out_path, [base.report_page(
        f'shader hotlist ({stage})', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
        ab=ab, root=root, report_key='shader_hotlist',
        kpis=kpis, run=rc,
        device=base.provenance_strip(*base.newest_drop_provenance(root, [cur] if cur else [])))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='shader_hotlist'))
