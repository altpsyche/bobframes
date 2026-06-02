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
from ..config import get_config


_DRAWS_COLS = [
    'area', 'drop_date', 'drop_label', 'capture',
    'mesh_hash', 'program_id', 'vs_shader_id', 'fs_shader_id',
    'parent_pass_path_norm', 'draw_class', 'num_indices', 'num_instances',
]


def _iter_draws(root: str, drops: list):
    """Yield row dicts from cache, else live-scan each drop."""
    t = base.load_cached(root, 'draws_summary')  # validates sha256 sidecar; None -> live scan (R-13)
    if t is not None:
        cols = base._to_dict_of_lists(t)
        wanted_keys = {(d.date, d.label) for d in drops}
        for i in range(t.num_rows):
            if (cols['drop_date'][i], cols['drop_label'][i]) not in wanted_keys:
                continue
            yield {c: cols[c][i] for c in cols}
        return
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
    # Run model (ADR-35): live candidates are meshes drawn in the CURRENT run; prior runs supply the
    # per-drop comparison columns + the resolved-since section, never inflate the live list.
    rc = base.run_context(drops)
    cur = rc.current
    bl = rc.baseline
    ck = cur.key if cur else None
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
        # Batching candidates are scoped to the current run too (ADR-35): batching a material that
        # was removed in the newer run would be the same cumulative-union bug as the live list.
        if cls in ('opaque', 'prepass') and inst <= 1 and drop_key == ck:
            fs = row.get('fs_shader_id') or 0
            key = (pass_norm, fs, cls)
            batching_groups[key] += 1
            batching_meshes[key].add(mh)
            batching_drops[key].add(drop_key)

    def _cur_repeat(m) -> int:
        return m['repeat_by_drop'].get(ck, 0)

    live = [(mh, m) for mh, m in per_mesh.items() if _cur_repeat(m) > 0]
    ranked = sorted(live, key=lambda kv: _cur_repeat(kv[1]), reverse=True)[:50]

    top_repeat = max((_cur_repeat(m) for _, m in ranked), default=0)
    n_unique_meshes = len(live)
    max_wasted = 0
    for mh, m in ranked:
        n_idx_list = m['num_indices']
        if not n_idx_list:
            continue
        n_typ = sorted(n_idx_list)[len(n_idx_list) // 2]
        max_wasted = max(max_wasted, (_cur_repeat(m) - 1) * n_typ)

    parts = []
    rcfg = get_config().report

    # Hero KPIs: top repeat, unique meshes, worst wasted-index estimate.
    kpis = [
        {'label': 'top mesh repeat', 'value': base.fmt_int(top_repeat)},
        {'label': 'unique meshes',   'value': base.fmt_int(n_unique_meshes)},
        {'label': 'max wasted idx',  'value': base.fmt_int(max_wasted)},
    ]

    # Summary bar: top 3 meshes by repeat
    top3 = []
    for rank_i, (mh, m) in enumerate(ranked[:3], 1):
        try:
            n_typ = int(statistics.median(m['num_indices'])) if m['num_indices'] else 0
        except statistics.StatisticsError:
            n_typ = 0
        max_repeat = _cur_repeat(m)
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
        # Insight: a mesh drawn many times is the prime instance/batch target.
        if top_repeat >= rcfg.instancing_repeat_min:
            parts.append(base.callout(
                'info',
                f'{top3[0][0]} is drawn {base.fmt_int(top_repeat)}x',
                f'~{base.fmt_int(max_wasted)} indices re-submitted across repeats - instance or batch '
                f'the hottest meshes to cut draw calls.',
                href='#top_meshes', link_text='top meshes'))

    single = len(drop_keys) == 1
    # c16c: framed in a sticky-highlighted section card.
    mbody = []
    if not ranked:
        mbody.append(base.empty_state('no repeated meshes found'))
    else:
        # Flagship: estimated wasted indices for the top meshes (c16b).
        chart_items = []
        for mh, m in ranked[:12]:
            try:
                n_typ_c = int(statistics.median(m['num_indices'])) if m['num_indices'] else 0
            except statistics.StatisticsError:
                n_typ_c = 0
            max_r = _cur_repeat(m)
            wasted_c = (max_r - 1) * n_typ_c
            if wasted_c <= 0:
                continue
            suffix_c = base.pass_suffix(m['pass_paths'].most_common(1)[0][0]) if m['pass_paths'] else '?'
            dom_c = m['draw_classes'].most_common(1)[0][0] if m['draw_classes'] else ''
            tag_c = str(mh)[-4:] if mh else ''
            chart_items.append((f'{dom_c}/{suffix_c}#{tag_c}', wasted_c))
        if chart_items:
            mbody.append(base.figure(
                base.bar_chart(chart_items, title='estimated wasted indices',
                               desc='(max repeat - 1) x typical indices, per mesh',
                               chart_id='inst-wasted'),
                'estimated wasted indices (top meshes)'))

        sec1 = ['<div class="table-wrap"><rdc-sortable-table>',
                '<table class="report">',
                '<caption>meshes drawn repeatedly - instancing / batching candidates</caption>',
                '<thead><tr>', '<th scope="col">mesh</th>']
        for i, k in enumerate(drop_keys):
            head = 'repeat' if single else f'repeat@{base.h(k)}'
            sec1.append(f'<th class="num" scope="col">{head}</th>')
            if i > 0:
                latest = ' delta-latest' if i == len(drop_keys) - 1 else ''
                sec1.append(f'<th class="num{latest}" scope="col">delta</th>')
        if len(drop_keys) >= 3:
            sec1.append('<th class="num" scope="col">trend</th>')
        sec1.extend([
            '<th scope="col">areas</th>',
            '<th scope="col">dominant pass</th>',
            '<th class="num" scope="col">indices typical</th>',
            '<th class="num" scope="col" title="(max repeat - 1) x typical indices: index data re-submitted across repeats">wasted indices</th>',
            '</tr></thead><tbody>',
        ])
        for rank_i, (mh, m) in enumerate(ranked, 1):
            max_repeat = _cur_repeat(m)
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
            copy_mh = (f'<rdc-copy-button data-value="{base.safe_chrome_text(mh)}" '
                       f'data-label="copy mesh hash"></rdc-copy-button>') if mh else ''
            sec1.append(
                f'<td>{rp}<a href="{base.h(link)}" data-link-kind="drill">{base.h(mesh_label)}</a>{copy_mh}</td>'
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
            sec1.append(f'<td class="num">{base.heatmap_cell(wasted, 0, max_wasted, text=base.fmt_int(wasted))}</td>')
            sec1.append('</tr>')
        sec1.append('</tbody></table></rdc-sortable-table></div>')
        mbody.append(''.join(sec1))
    parts.append('<rdc-sticky-h2>'
                 + base.section_card('top_meshes', 'top meshes by repeat',
                                     ''.join(mbody), count=len(ranked))
                 + '</rdc-sticky-h2>')

    # Resolved since baseline (ADR-35): meshes drawn in the baseline run but gone in the current run -
    # a win (removed/fixed), surfaced separately (fill-or-hide) so it never mixes into the live list.
    if bl is not None:
        resolved = sorted(
            ((mh, m) for mh, m in per_mesh.items()
             if m['repeat_by_drop'].get(bl.key, 0) > 0 and _cur_repeat(m) == 0),
            key=lambda kv: kv[1]['repeat_by_drop'].get(bl.key, 0), reverse=True)
        if resolved:
            rbody = ['<div class="table-wrap"><rdc-sortable-table>',
                     '<table class="report">',
                     f'<caption>meshes drawn in {base.h(bl.key)} but gone in {base.h(ck)} - removed or fixed</caption>',
                     '<thead><tr>', '<th scope="col">mesh</th>',
                     f'<th class="num" scope="col">repeat@{base.h(bl.key)}</th>',
                     '<th scope="col">areas</th>', '</tr></thead><tbody>']
            for mh, m in resolved[:30]:
                try:
                    n_typ = int(statistics.median(m['num_indices'])) if m['num_indices'] else 0
                except statistics.StatisticsError:
                    n_typ = 0
                dominant_pass = m['pass_paths'].most_common(1)[0][0] if m['pass_paths'] else ''
                dominant_cls = m['draw_classes'].most_common(1)[0][0] if m['draw_classes'] else ''
                suffix = base.pass_suffix(dominant_pass) or '?'
                hash_tag = str(mh)[-4:] if mh else ''
                mesh_label = f'{dominant_cls}/{suffix}/{n_typ}v#{hash_tag}'
                rbody.append('<tr>')
                rbody.append(f'<td>{base.h(mesh_label)}</td>')
                rbody.append(f'<td class="num">{base.fmt_int(m["repeat_by_drop"].get(bl.key, 0))}</td>')
                rbody.append(f'<td>{base.h(", ".join(sorted(m["areas"])))}</td>')
                rbody.append('</tr>')
            rbody.append('</tbody></table></rdc-sortable-table></div>')
            parts.append('<rdc-sticky-h2>'
                         + base.section_card('resolved', f'resolved since {bl.key}',
                                             ''.join(rbody), count=len(resolved))
                         + '</rdc-sticky-h2>')

    # c16c fill-or-hide: only emit the batching section when there is real content - no bare heading.
    top_batch = [(k, v) for k, v in batching_groups.items() if v >= rcfg.instancing_repeat_min]
    top_batch.sort(key=lambda kv: kv[1], reverse=True)
    if top_batch:
        sec2 = ['<div class="table-wrap"><rdc-sortable-table>',
                '<table class="report">',
                '<caption>passes where many distinct meshes share one material - batch candidates</caption>',
                '<thead><tr>', '<th scope="col">pass</th>', '<th scope="col">class</th>',
                '<th class="num" scope="col">repeat</th>',
                '<th class="num" scope="col">distinct meshes</th>',
                '<th scope="col">drops</th>', '</tr></thead><tbody>']
        for (pass_norm, fs, cls), n in top_batch[:30]:
            sec2.append('<tr>')
            sec2.append(f'<td>{base.h(base.pass_short(pass_norm))}</td>')
            sec2.append(f'<td>{base.h(cls)}</td>')
            sec2.append(f'<td class="num">{base.fmt_int(n)}</td>')
            sec2.append(f'<td class="num">{base.fmt_int(len(batching_meshes[(pass_norm, fs, cls)]))}</td>')
            sec2.append(f'<td>{base.h(", ".join(sorted(batching_drops[(pass_norm, fs, cls)])))}</td>')
            sec2.append('</tr>')
        sec2.append('</tbody></table></rdc-sortable-table></div>')
        parts.append('<rdc-sticky-h2>'
                     + base.section_card('batching', 'potential material batching',
                                         ''.join(sec2), count=len(top_batch))
                     + '</rdc-sticky-h2>')

    return base.write_report(out_path, [base.report_page(
        'instancing opportunities', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(), crumb_depth=base.crumb_depth(ab),
        ab=ab, root=root, report_key='instancing_opportunities',
        kpis=kpis, run=rc,
        device=base.provenance_strip(*base.newest_drop_provenance(root, [cur] if cur else [])))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='instancing_opportunities'))
