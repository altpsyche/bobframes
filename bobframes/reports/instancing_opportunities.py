"""Top mesh_hashes by repeat_count + sister 'material batching' section.

Reads _reports/_cache/draws_summary_per_drop.parquet when present; falls back
to live scan of **/draws.parquet.
"""

from __future__ import annotations

import os
import statistics
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as papq

from . import base


_DRAWS_COLS = [
    'area', 'drop_date', 'drop_label', 'capture',
    'mesh_hash', 'program_id', 'vs_shader_id', 'fs_shader_id',
    'parent_pass_path_norm', 'draw_class', 'num_indices', 'num_instances',
]


def _iter_draws(root: str, drops: list):
    """Yield row dicts from cache, else live-scan each drop."""
    cache = base.cache_path(root, 'draws_summary')
    if os.path.exists(cache):
        try:
            t = papq.read_table(cache)
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            wanted_keys = {(d.date, d.label) for d in drops}
            for i in range(t.num_rows):
                if (cols['drop_date'][i], cols['drop_label'][i]) not in wanted_keys:
                    continue
                yield {c: cols[c][i] for c in cols}
            return
        except Exception:
            pass
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'draws.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=_DRAWS_COLS)
            except Exception:
                continue
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            for i in range(t.num_rows):
                row = {c: cols[c][i] for c in cols}
                row['drop_date'] = r.drop_date
                row['drop_label'] = r.drop_label
                yield row


def _drop_dir_for(drops: list, drop_date, drop_label, area) -> str:
    for d in drops:
        if d.date == drop_date and d.label == drop_label:
            for r in d.rows:
                if r.area == area:
                    return r.drop_dir
    return ''


def build(root: str, *, drops: list | None = None, ab=None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    out_path = base.output_path(root, 'instancing_opportunities', ab)
    out_dir = os.path.dirname(out_path)

    drop_keys = [d.key for d in drops]

    per_mesh: dict = defaultdict(lambda: {
        'repeat_by_drop': Counter(),
        'pass_paths': Counter(),
        'draw_classes': Counter(),
        'program_ids': Counter(),
        'num_indices': [],
        'captures': set(),
        'areas': set(),
        'rep_row': None,
        'rep_drop': None,
    })

    batching_groups: Counter = Counter()
    batching_meshes: dict = defaultdict(set)
    batching_drops: dict = defaultdict(set)

    for row in _iter_draws(root, drops):
        mh = row.get('mesh_hash')
        n_idx = row.get('num_indices') or 0
        prog = row.get('program_id') or 0
        if not mh or n_idx <= 0 or prog == 0:
            continue
        drop_key = f"{row['drop_date']}_{row['drop_label']}"
        m = per_mesh[mh]
        m['repeat_by_drop'][drop_key] += 1
        pass_norm = row.get('parent_pass_path_norm') or ''
        cls = row.get('draw_class') or 'other'
        m['pass_paths'][pass_norm] += 1
        m['draw_classes'][cls] += 1
        m['program_ids'][prog] += 1
        m['num_indices'].append(n_idx)
        m['captures'].add((row['area'], row['drop_date'], row.get('capture')))
        m['areas'].add(row['area'])
        if m['rep_row'] is None:
            m['rep_row'] = row
            m['rep_drop'] = (row['drop_date'], row['drop_label'])

        inst = row.get('num_instances') or 1
        if cls in ('opaque', 'prepass') and inst <= 1:
            fs = row.get('fs_shader_id') or 0
            key = (pass_norm, fs, cls)
            batching_groups[key] += 1
            batching_meshes[key].add(mh)
            batching_drops[key].add(drop_key)

    ranked = sorted(
        per_mesh.items(),
        key=lambda kv: max(kv[1]['repeat_by_drop'].values()) if kv[1]['repeat_by_drop'] else 0,
        reverse=True,
    )[:50]

    top_repeat = (max((max(m['repeat_by_drop'].values()) for _, m in ranked
                        if m['repeat_by_drop']), default=0)
                  if ranked else 0)
    n_unique_meshes = len(per_mesh)
    max_wasted = 0
    for mh, m in ranked:
        n_idx_list = m['num_indices']
        if not n_idx_list:
            continue
        n_typ = sorted(n_idx_list)[len(n_idx_list) // 2]
        max_r = max(m['repeat_by_drop'].values())
        max_wasted = max(max_wasted, (max_r - 1) * n_typ)
    pct_deduped = (1.0 - (n_unique_meshes / sum(sum(m['repeat_by_drop'].values())
                                                  for _, m in per_mesh.items())
                          if per_mesh else 0)) * 100.0 if per_mesh else 0.0

    parts = []

    # Summary bar: top 3 meshes by repeat
    top3 = []
    for rank_i, (mh, m) in enumerate(ranked[:3], 1):
        try:
            n_typ = int(statistics.median(m['num_indices'])) if m['num_indices'] else 0
        except statistics.StatisticsError:
            n_typ = 0
        max_repeat = max(m['repeat_by_drop'].values()) if m['repeat_by_drop'] else 0
        dominant_pass = m['pass_paths'].most_common(1)[0][0] if m['pass_paths'] else ''
        dominant_cls = m['draw_classes'].most_common(1)[0][0] if m['draw_classes'] else ''
        suffix = base.pass_suffix(dominant_pass) or '?'
        hash_tag = str(mh)[-4:] if mh else ''
        label = f'{dominant_cls}/{suffix}/{n_typ}v#{hash_tag}'
        top3.append((label, max_repeat))
    if top3:
        headline = f'{top3[0][0]} (repeat {base.fmt_int(top3[0][1])})'
        sub_bits = [f'{lbl} x{rep}' for lbl, rep in top3[1:]]
        parts.append(base.summary_bar(
            'top batch candidates',
            headline,
            sub='next: ' + ', '.join(sub_bits) if sub_bits else None,
            link_href='#top_meshes',
            link_text='table',
            tone='neutral',
        ))

    sec1 = []
    single = len(drop_keys) == 1
    sec1.append('<h2 id="top_meshes">top meshes by repeat</h2>')
    sec1.append('<div class="table-wrap"><rdc-sortable-table>')
    sec1.append('<table class="report"><thead><tr>')
    sec1.append('<th>mesh</th>')
    for i, k in enumerate(drop_keys):
        head = 'repeat' if single else f'repeat@{base.h(k)}'
        sec1.append(f'<th class="num">{head}</th>')
        if i > 0:
            latest = ' delta-latest' if i == len(drop_keys) - 1 else ''
            sec1.append(f'<th class="num{latest}">delta</th>')
    if len(drop_keys) >= 3:
        sec1.append('<th class="num">trend</th>')
    sec1.extend([
        '<th>areas</th>',
        '<th>dominant pass</th>',
        '<th class="num">indices typical</th>',
        '<th class="num">wasted indices</th>',
        '</tr></thead><tbody>',
    ])

    for rank_i, (mh, m) in enumerate(ranked, 1):
        max_repeat = max(m['repeat_by_drop'].values()) if m['repeat_by_drop'] else 0
        try:
            n_typ = int(statistics.median(m['num_indices'])) if m['num_indices'] else 0
        except statistics.StatisticsError:
            n_typ = 0
        wasted = (max_repeat - 1) * n_typ
        rep_row = m['rep_row'] or {}
        rep_drop_dir = _drop_dir_for(drops, rep_row.get('drop_date'),
                                      rep_row.get('drop_label'), rep_row.get('area'))
        dominant_pass = m['pass_paths'].most_common(1)[0][0] if m['pass_paths'] else ''
        dominant_cls = m['draw_classes'].most_common(1)[0][0] if m['draw_classes'] else ''
        suffix = base.pass_suffix(dominant_pass) or '?'
        hash_tag = str(mh)[-4:] if mh else ''
        mesh_label = f'{dominant_cls}/{suffix}/{n_typ}v#{hash_tag}'

        sec1.append('<tr>')
        link = base.rel_path_to_drop_index(out_dir, rep_drop_dir, 'draws') if rep_drop_dir else '#'
        rp = base.rank_pill(rank_i) if rank_i <= 3 else ''
        sec1.append(
            f'<td>{rp}<a href="{base.h(link)}" data-link-kind="drill">{base.h(mesh_label)}</a></td>'
        )
        prev = None
        series = []
        for i, k in enumerate(drop_keys):
            v = m['repeat_by_drop'].get(k, 0)
            series.append(v)
            sec1.append(f'<td class="num">{base.fmt_int(v)}</td>')
            if i > 0:
                sec1.append(base.delta_cell(v, prev,
                    lower_is_better=True, fmt='{:+,.0f}',
                    regression_threshold_pct=20.0))
            prev = v
        if len(drop_keys) >= 3:
            sec1.append(f'<td class="num">{base.sparkline_svg(series)}</td>')

        areas_str = ', '.join(sorted(m['areas']))
        sec1.append(f'<td>{base.h(areas_str)}</td>')
        sec1.append(f'<td>{base.h(base.pass_short(dominant_pass))}</td>')
        sec1.append(f'<td class="num">{base.fmt_int(n_typ)}</td>')
        bar = base.inline_bar(wasted, max_wasted) if max_wasted > 0 else ''
        sec1.append(f'<td class="num">{base.fmt_int(wasted)}{bar}</td>')
        sec1.append('</tr>')
    sec1.append('</tbody></table></rdc-sortable-table></div>')
    parts.append(''.join(sec1))

    sec2 = []
    sec2.append('<h2 id="batching">potential material batching</h2>')
    sec2.append('<div class="table-wrap"><rdc-sortable-table>')
    sec2.append('<table class="report"><thead><tr>')
    sec2.append('<th>pass</th>')
    sec2.append('<th>class</th>')
    sec2.append('<th class="num">repeat</th>')
    sec2.append('<th class="num">distinct meshes</th>')
    sec2.append('<th>drops</th>')
    sec2.append('</tr></thead><tbody>')
    top_batch = [(k, v) for k, v in batching_groups.items() if v >= 4]
    top_batch.sort(key=lambda kv: kv[1], reverse=True)
    for (pass_norm, fs, cls), n in top_batch[:30]:
        sec2.append('<tr>')
        sec2.append(f'<td>{base.h(base.pass_short(pass_norm))}</td>')
        sec2.append(f'<td>{base.h(cls)}</td>')
        sec2.append(f'<td class="num">{base.fmt_int(n)}</td>')
        sec2.append(f'<td class="num">{base.fmt_int(len(batching_meshes[(pass_norm, fs, cls)]))}</td>')
        sec2.append(f'<td>{base.h(", ".join(sorted(batching_drops[(pass_norm, fs, cls)])))}</td>')
        sec2.append('</tr>')
    sec2.append('</tbody></table></rdc-sortable-table></div>')
    parts.append(''.join(sec2))

    return base.write_report(out_path, [base.report_page(
        'instancing opportunities', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(), crumb_depth=base.crumb_depth(ab),
        ab=ab, root=root, report_key='instancing_opportunities')])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='instancing_opportunities'))
