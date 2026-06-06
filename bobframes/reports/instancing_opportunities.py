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
from .. import aggregates as _agg
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
            cols = base._to_dict_of_lists(t)   # Q-7
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


def build(root: str, *, drops: list | None = None, ab=None,
          run_label=None, run_date=None,
          sink: base.AssetSink = base.AssetSink.INLINE,
          build_ts: str | None = None, redact: bool = False, theme: dict | None = None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    # Run model (ADR-35): live candidates are meshes drawn in the CURRENT run; prior runs supply the
    # per-drop comparison columns + the resolved-since section, never inflate the live list.
    rc = base.run_context(drops, run_label=run_label, run_date=run_date)
    cur = rc.current
    bl = rc.baseline
    ck = cur.key if cur else None
    out_path = base.output_path(root, 'instancing_opportunities', ab, run=rc)
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

    # Single-source the repeat-count atom (G-26, aggregates): occurrences per (drop, area, mesh),
    # summed across areas into the cross-area per-(mesh, drop) count this report displays. Identical
    # filter + cache as the metadata loop above, so byte-for-byte the old inline `repeat_by_drop`; c16v
    # normalizes it per frame here so the report and the verdict read the same number.
    _da = _agg.draw_aggregates(root, drops)
    _repeat_by_mesh: dict = defaultdict(Counter)
    for (dk, area, mh2), c in _da.count.items():
        _repeat_by_mesh[mh2][dk] += base.per_frame(c, _da.frames(dk, area))   # c16v: per frame, per-area summed
    for mh, m in per_mesh.items():
        m['repeat_by_drop'] = _repeat_by_mesh.get(mh, Counter())

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

        # v0.2.6-4: adopt the data_table component (ADR-43; golden absorbs the normalization). No column
        # groups. Build the dynamic column list (per-drop repeat + delta) once, then the rows.
        cols = [base.Column('mesh', 'mesh', render=lambda value, row: value)]   # prebuilt trusted inner
        for i, k in enumerate(drop_keys):
            cols.append(base.Column(f'rep{i}', 'repeat' if single else f'repeat@{k}', numeric=True))
            if i > 0:
                cols.append(base.delta_column(f'rdelta{i}', latest=(i == len(drop_keys) - 1)))
        if len(drop_keys) >= 3:
            cols.append(base.Column('trend', 'trend', numeric=True,
                                    render=lambda value, row: base.sparkline_svg(value)))
        cols += [
            base.Column('areas', 'areas', clip='default'),
            base.Column('dompass', 'dominant pass', clip='narrow'),
            base.Column('ityp', 'indices typical', numeric=True),
            base.Column('wasted', 'wasted indices', numeric=True,
                        title='(max repeat - 1) x typical indices: index data re-submitted across repeats',
                        render=lambda value, row: base.heatmap_cell(value, 0, row['_maxw'],
                                                                    text=base.fmt_int(value))),
        ]
        rows = []
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
            link = base.rel_path_to_drop_index(out_dir, rep_drop_dir, 'draws') if rep_drop_dir else '#'
            rp = base.rank_pill(rank_i) if rank_i <= 3 else ''
            copy_mh = (f'<rdc-copy-button data-value="{base.safe_chrome_text(mh)}" '
                       f'data-label="copy mesh hash"></rdc-copy-button>') if mh else ''
            # c16m: clip the mesh label on the <a> (default tier); rank pill + copy button ride outside.
            row = {
                'mesh': (f'{rp}<a href="{base.h(link)}"{base.clip_attrs(mesh_label)} '
                         f'data-link-kind="drill">{base.h(mesh_label)}</a>{copy_mh}'),
                'areas': ', '.join(sorted(m['areas'])),
                'dompass': base.pass_short(dominant_pass),
                'ityp': base.fmt_int(n_typ),
                'wasted': wasted, '_maxw': max_wasted,
            }
            prev = None
            series = []
            for i, k in enumerate(drop_keys):
                v = m['repeat_by_drop'].get(k, 0)
                series.append(v)
                row[f'rep{i}'] = base.fmt_int(v)
                if i > 0:
                    row[f'rdelta{i}'] = base.delta_parts(v, prev, lower_is_better=True,
                                                         fmt='{:+,.0f}', regression_threshold_pct=20.0)
                prev = v
            if len(drop_keys) >= 3:
                row['trend'] = series
            rows.append(row)
        mbody.append(str(base.data_table(cols, rows, table_key='instancing_main')))
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
            rcols = [base.Column('mesh', 'mesh'),
                     base.Column('rep', f'repeat@{bl.key}', numeric=True),
                     base.Column('areas', 'areas')]
            rrows = []
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
                rrows.append({'mesh': mesh_label,
                              'rep': base.fmt_int(m['repeat_by_drop'].get(bl.key, 0)),
                              'areas': ', '.join(sorted(m['areas']))})
            rbody = base.data_table(rcols, rrows, table_key='instancing_resolved',
                                    caption=f'meshes drawn in {bl.key} but gone in {ck} - removed or fixed')
            parts.append('<rdc-sticky-h2>'
                         + base.section_card('resolved', f'resolved since {bl.key}',
                                             str(rbody), count=len(resolved))
                         + '</rdc-sticky-h2>')

    # c16c fill-or-hide: only emit the batching section when there is real content - no bare heading.
    # c16v: the batching repeat is per frame too (it shares the instancing_repeat_min threshold). The
    # count is current-run + cross-area, so the denominator is the current run's per-area frame count
    # (max over its areas; exact on a uniform/single-area drop, a documented approximation otherwise -
    # ADR-23). On 1-capture data it is /1, byte-identical.
    _cur_frames = max((len(v) for (dk, a), v in _da.captures.items() if dk == ck), default=1)
    top_batch = [(k, base.per_frame(v, _cur_frames)) for k, v in batching_groups.items()
                 if base.per_frame(v, _cur_frames) >= rcfg.instancing_repeat_min]
    top_batch.sort(key=lambda kv: kv[1], reverse=True)
    if top_batch:
        bcols = [base.Column('pass', 'pass'), base.Column('cls', 'class'),
                 base.Column('rep', 'repeat', numeric=True),
                 base.Column('distinct', 'distinct meshes', numeric=True),
                 base.Column('drops', 'drops')]
        brows = [{'pass': base.pass_short(pass_norm), 'cls': cls,
                  'rep': base.fmt_int(n),
                  'distinct': base.fmt_int(len(batching_meshes[(pass_norm, fs, cls)])),
                  'drops': ', '.join(sorted(batching_drops[(pass_norm, fs, cls)]))}
                 for (pass_norm, fs, cls), n in top_batch[:30]]
        sec2 = base.data_table(bcols, brows, table_key='instancing_batching',
                               caption='passes where many distinct meshes share one material - batch candidates')
        parts.append('<rdc-sticky-h2>'
                     + base.section_card('batching', 'potential material batching',
                                         str(sec2), count=len(top_batch))
                     + '</rdc-sticky-h2>')

    return base.write_report(out_path, [base.report_page(
        'instancing opportunities', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=build_ts or base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
        ab=ab, root=root, report_key='instancing_opportunities', sink=sink, theme=theme,
        kpis=kpis, run=rc,
        device=base.provenance_strip(*base.newest_drop_provenance(root, [cur] if cur else []), redact=redact))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='instancing_opportunities'))
