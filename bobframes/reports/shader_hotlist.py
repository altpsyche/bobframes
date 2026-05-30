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


_SHADER_COLS = [
    'area', 'drop_date', 'drop_label', 'capture', 'shader_id', 'stable_key',
    'shader_type', 'src_len', 'complexity_score', 'total_branches',
    'total_loops', 'total_discards', 'total_dfdx_dfdy',
    'total_texture_samples', 'used_by_draw_count', 'src_file_path',
    'fb_fetch', 'uses_cubemap',
]


def _iter_shaders(root: str, drops: list):
    cache = base.cache_path(root, 'shader_summary')
    if os.path.exists(cache):
        try:
            t = papq.read_table(cache)
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            wanted = {(d.date, d.label) for d in drops}
            for i in range(t.num_rows):
                if (cols['drop_date'][i], cols['drop_label'][i]) not in wanted:
                    continue
                yield {c: cols[c][i] for c in cols}
            return
        except Exception:
            pass
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
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
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
          stage: str = 'fragment') -> str:
    if drops is None:
        drops = base.discover_drops(root)
    out_path = base.output_path(root, 'shader_hotlist', ab)
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

    ranked = []
    for sk, p in per_key.items():
        total_uses = sum(p['uses_by_drop'].values())
        cost = p['complexity'] * total_uses
        ranked.append((sk, p, total_uses, cost))
    ranked.sort(key=lambda x: x[3], reverse=True)
    ranked = ranked[:50]

    max_cost = max((c for _, _, _, c in ranked), default=0.0)

    parts = [base.page_open(f'shader hotlist ({stage})', hdr_offset_px=120)]
    parts.append(base.header(
        f'shader hotlist ({stage})',
        drops=len(drops),
        captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(),
        crumb_depth=base.crumb_depth(ab),
    ))
    parts.append(base.ab_strip(ab))
    parts.append(base.ab_picker_for(root, 'shader_hotlist', ab=ab))

    # Summary bar: top shader by cost proxy
    if ranked:
        sk, p, total_uses, cost = ranked[0]
        label_top = f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}'
        parts.append(base.summary_bar(
            'top shader',
            f'{label_top}',
            sub=f'{base.fmt_int(total_uses)} uses across drops',
            link_href='#shaders',
            link_text='table',
            tone='neutral',
        ))

    sec = []
    sec.append(f'<h2 id="shaders">top {stage} shaders by complexity * uses</h2>')
    sec.append('<div class="table-wrap"><rdc-sortable-table data-default-sort="cost proxy" data-default-dir="desc">')
    sec.append('<table class="report"><thead><tr>')
    sec.append('<th>shader</th>')
    sec.append('<th class="num">complexity</th>')
    sec.append('<th class="num">uses total</th>')
    single = len(drop_keys) == 1
    for i, k in enumerate(drop_keys):
        head = 'uses' if single else f'uses@{base.h(k)}'
        sec.append(f'<th class="num">{head}</th>')
        if i > 0:
            latest = ' delta-latest' if i == len(drop_keys) - 1 else ''
            sec.append(f'<th class="num{latest}">delta</th>')
    if len(drop_keys) >= 3:
        sec.append('<th class="num">trend</th>')
    sec.extend([
        '<th class="num">cost proxy</th>',
        '<th class="num">branches</th>',
        '<th class="num">loops</th>',
        '<th class="num">tex samples</th>',
        '<th class="num">src bytes</th>',
        '<th>flags</th>',
        '<th>src</th>',
        '</tr></thead><tbody>',
    ])

    for rank_i, (sk, p, total_uses, cost) in enumerate(ranked, 1):
        sec.append('<tr>')
        rp = base.rank_pill(rank_i) if rank_i <= 3 else ''
        shader_label = f'{p["shader_type"][:4]}-cplx-{int(p["complexity"])}'
        drop_dir = _drop_dir_first(drops, p['rep_drop_date'], p['rep_drop_label'])
        src_link = base.rel_path_to_drop_file(out_dir, drop_dir, p['rep_src_path'])
        if src_link:
            sec.append(f'<td>{rp}<a href="{base.h(src_link)}" data-link-kind="inline" target="_blank" rel="noopener">{base.h(shader_label)}{base.icon("link-out")}</a></td>')
        else:
            sec.append(f'<td>{rp}{base.h(shader_label)}</td>')
        sec.append(f'<td class="num">{base.fmt_float(p["complexity"], 2)}</td>')
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

        bar = base.inline_bar(cost, max_cost) if max_cost > 0 else ''
        sec.append(f'<td class="num">{base.fmt_float(cost, 1)}{bar}</td>')
        sec.append(f'<td class="num">{base.fmt_int(p["branches"])}</td>')
        sec.append(f'<td class="num">{base.fmt_int(p["loops"])}</td>')
        sec.append(f'<td class="num">{base.fmt_int(p["tex_samples"])}</td>')
        sec.append(f'<td class="num">{base.fmt_int(p["src_len"])}</td>')

        flags = []
        if p['fb_fetch']:
            flags.append('fb_fetch')
        if p['uses_cubemap']:
            flags.append('cubemap')
        sec.append(f'<td>{base.h(",".join(flags))}</td>')

        if src_link:
            sec.append(f'<td><a href="{base.h(src_link)}" data-link-kind="inline" target="_blank" rel="noopener">{base.h(p["rep_src_path"])}{base.icon("file")}</a></td>')
        else:
            sec.append('<td></td>')

        sec.append('</tr>')
    sec.append('</tbody></table></rdc-sortable-table></div>')
    parts.append(''.join(sec))

    parts.append(base.page_close())

    return base.write_report(out_path, parts)


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='shader_hotlist'))
