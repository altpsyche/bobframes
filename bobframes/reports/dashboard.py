"""Cumulative dashboard: hero strip + card grid of report summaries.

Lives at <root>/_reports/index.html. Linked from root index.html.
"""

from __future__ import annotations

import os
import statistics
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as papq

from . import base
from .. import paths as _paths


def _top_meshes(root: str, drops: list, n: int = 3) -> list:
    """Return [(label, repeat, indices_med)] where label is a human-readable synthetic."""
    t = base.load_cached(root, 'draws_summary', columns=[
        'mesh_hash', 'num_indices', 'program_id',
        'draw_class', 'parent_pass_path_norm'])  # sha256-validated; None -> warn + [] (R-13)
    if t is None:
        return []
    cols = base._to_dict_of_lists(t)
    counts: Counter = Counter()
    indices: dict = defaultdict(list)
    cls_by_mesh: dict = {}
    pass_by_mesh: dict = {}
    for i in range(t.num_rows):
        mh = cols['mesh_hash'][i]
        prog = cols['program_id'][i] or 0
        n_idx = cols['num_indices'][i] or 0
        if not mh or n_idx <= 0 or prog == 0:
            continue
        counts[mh] += 1
        indices[mh].append(n_idx)
        cls_by_mesh.setdefault(mh, cols['draw_class'][i] or 'other')
        pass_by_mesh.setdefault(mh, cols['parent_pass_path_norm'][i] or '')
    out = []
    for mh, c in counts.most_common(n):
        try:
            med = int(statistics.median(indices[mh])) if indices[mh] else 0
        except statistics.StatisticsError:
            med = 0
        cls = cls_by_mesh.get(mh, 'other')
        suffix = base.pass_suffix(pass_by_mesh.get(mh, '')) or '?'
        hash_tag = str(mh)[-4:] if mh else ''
        label = f'{cls}/{suffix}/{med}v#{hash_tag}'
        out.append((label, c, med))
    return out


def _top_passes(drops: list, n: int = 3) -> list:
    """Return [(area, pass_label, gpu_s)] where pass_label is the suffix only."""
    agg: dict = defaultdict(float)
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'pass_class_breakdown.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=['area', 'marker_path_norm',
                                                 'sum_gpu_duration_s'])
            except Exception:
                continue
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            for i in range(t.num_rows):
                key = (cols['area'][i], cols['marker_path_norm'][i] or '')
                agg[key] += cols['sum_gpu_duration_s'][i] or 0.0
    ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [(a, base.pass_suffix(m) or m, g) for (a, m), g in ranked]


def _top_shaders(root: str, n: int = 3) -> list:
    """Return [(label, complexity, cost_proxy)] where label is `frag-cplx-{int(cplx)}`."""
    t = base.load_cached(root, 'shader_summary',
        columns=['stable_key', 'shader_type', 'complexity_score',
                 'used_by_draw_count'])  # sha256-validated; None -> warn + [] (R-13)
    if t is None:
        return []
    cols = base._to_dict_of_lists(t)
    cost: dict = defaultdict(float)
    cplx: dict = {}
    stype: dict = {}
    for i in range(t.num_rows):
        if cols['shader_type'][i] != 'fragment':
            continue
        sk = cols['stable_key'][i] or ''
        if not sk:
            continue
        c_val = float(cols['complexity_score'][i] or 0)
        uses = int(cols['used_by_draw_count'][i] or 0)
        cost[sk] += c_val * uses
        cplx[sk] = max(cplx.get(sk, 0), c_val)
        stype[sk] = cols['shader_type'][i]
    ranked = sorted(cost.items(), key=lambda kv: kv[1], reverse=True)[:n]
    out = []
    for sk, c in ranked:
        cval = cplx[sk]
        label = f'{stype[sk][:4]}-cplx-{int(cval)}'
        out.append((label, cval, c))
    return out


def _per_area_draws(drops: list) -> dict:
    """Return {area: {n_draws, dominant_class}}."""
    per: dict = defaultdict(lambda: {'n_draws': 0, 'by_class': Counter()})
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'pass_class_breakdown.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=['area', 'draw_class', 'n_draws'])
            except Exception:
                continue
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            for i in range(t.num_rows):
                a = cols['area'][i]
                cls = cols['draw_class'][i] or 'other'
                n = cols['n_draws'][i] or 0
                per[a]['n_draws'] += n
                per[a]['by_class'][cls] += n
    res: dict = {}
    for a, v in per.items():
        dom = v['by_class'].most_common(1)[0][0] if v['by_class'] else '-'
        res[a] = {'n_draws': v['n_draws'], 'dominant_class': dom}
    return res


def _top_areas_gpu(drops: list, n: int = 3) -> list:
    """Return [(area, gpu_s, draws)] top by gpu."""
    agg: dict = defaultdict(lambda: {'gpu': 0.0, 'draws': 0})
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'frame_totals.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=['total_gpu_duration_s', 'n_draws'])
            except Exception:
                continue
            gpu_vals = t.column('total_gpu_duration_s').to_pylist()
            draw_vals = t.column('n_draws').to_pylist()
            for g, dr in zip(gpu_vals, draw_vals):
                agg[r.area]['gpu'] += float(g or 0)
                agg[r.area]['draws'] += int(dr or 0)
    rows = [(a, v['gpu'], v['draws']) for a, v in agg.items()]
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows[:n]


def _worst_overdraw(drops: list, n: int = 3) -> list:
    """Return [(area, rt_label, reject_pct, n_samples)]. Rejection = 1 - passed%.

    depth_test_failed is usually 0 in mobile (early-z handled by hardware);
    real signal is shadow/backface/discard rejection ratio.
    """
    agg: dict = defaultdict(lambda: {'n_samples': 0, 'n_passed': 0,
                                       'drop_dir': '', 'capture': None})
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'pixel_history.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p,
                    columns=['area', 'rt_id', 'passed', 'capture'])
            except Exception:
                continue
            if t.num_rows == 0:
                continue
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            for i in range(t.num_rows):
                key = (cols['area'][i], cols['rt_id'][i])
                agg[key]['n_samples'] += 1
                if cols['passed'][i]:
                    agg[key]['n_passed'] += 1
                if not agg[key]['drop_dir']:
                    agg[key]['drop_dir'] = r.drop_dir
                    agg[key]['capture'] = cols['capture'][i]
    rows = []
    for (area, rt_id), v in agg.items():
        if v['n_samples'] < 20:
            continue
        reject_pct = (1.0 - v['n_passed'] / v['n_samples']) * 100.0
        rt_label = base.label_for(v['drop_dir'], v['capture'], 'rt', rt_id) \
            or f'rt_{rt_id}'
        rows.append((area, rt_label, reject_pct, v['n_samples']))
    rows.sort(key=lambda x: x[2], reverse=True)
    return rows[:n]


def _global_kpis(drops: list) -> list:
    """Cheap-to-compute global numbers from frame_totals across drops."""
    total_gpu = 0.0
    total_draws = 0
    captures = 0
    areas: set = set()
    for d in drops:
        captures += d.n_captures
        areas.update(d.areas)
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'frame_totals.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=['total_gpu_duration_s', 'n_draws'])
            except Exception:
                continue
            for v in t.column('total_gpu_duration_s').to_pylist():
                if v is not None:
                    total_gpu += float(v)
            for v in t.column('n_draws').to_pylist():
                if v is not None:
                    total_draws += int(v)
    return [
        {'label': 'total gpu (s)', 'value': base.fmt_float(total_gpu, 3)},
        {'label': 'total draws',    'value': base.fmt_int(total_draws)},
        {'label': 'areas',          'value': base.fmt_int(len(areas))},
    ]


def _card_table(rows: list, columns: list) -> str:
    if not rows:
        return base.empty_state('no data yet')
    parts = ['<table class="report"><thead><tr>']
    for col_name, _, num in columns:
        cls = ' class="num"' if num else ''
        parts.append(f'<th{cls}>{base.h(col_name)}</th>')
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        for col_name, fn, num in columns:
            cls = ' class="num"' if num else ''
            val = fn(row)
            parts.append(f'<td{cls}>{val}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts)


def build(root: str, *, drops: list | None = None, ab=None) -> str:
    if drops is None:
        drops = base.discover_drops(root)

    out_dir = _paths.reports_dir(root)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, _paths.INDEX_HTML)

    parts = []

    # Summary bar: worst area by GPU rank + global counts
    cards = []

    top_a = _top_areas_gpu(drops, n=999)
    n_areas = len(top_a)
    total_draws = sum(t[2] for t in top_a)
    if top_a:
        worst_area, worst_gpu, worst_draws = top_a[0]
        parts.append(base.summary_bar(
            'worst gpu area',
            worst_area,
            sub=(f'rank 1 of {n_areas} areas; this area {base.fmt_int(worst_draws)} draws; '
                 f'all areas {base.fmt_int(total_draws)} draws'),
            link_href=f'trend_table.html#gpu',
            link_text='trend',
            tone='neutral',
        ))
    top_a = top_a[:3]
    body_tt = _card_table(
        top_a,
        [
            ('area', lambda r: base.h(r[0]), False),
            ('gpu (s)', lambda r: base.fmt_float(r[1], 3), True),
            ('draws', lambda r: base.fmt_int(r[2]), True),
        ]
    )
    cards.append(
        '<a class="dash-card" href="trend_table.html">'
        '<h3>trend table</h3>'
        f'{body_tt}'
        '</a>'
    )

    # Card: instancing
    top_m = _top_meshes(root, drops)
    body_im = _card_table(
        top_m,
        [
            ('mesh', lambda r: base.h(r[0]), False),
            ('repeat', lambda r: base.fmt_int(r[1]), True),
            ('indices typ', lambda r: base.fmt_int(r[2]), True),
        ]
    )
    cards.append(
        '<a class="dash-card" href="instancing_opportunities.html">'
        '<h3>instancing opportunities</h3>'
        f'{body_im}'
        '</a>'
    )

    # Card: pass gpu
    top_p = _top_passes(drops)
    body_pg = _card_table(
        top_p,
        [
            ('area', lambda r: base.h(r[0]), False),
            ('marker', lambda r: base.safe_chrome_text(base.trunc_left(r[1], 32)), False),
            ('gpu (s)', lambda r: base.fmt_float(r[2], 3), True),
        ]
    )
    cards.append(
        '<a class="dash-card" href="pass_gpu.html">'
        '<h3>pass gpu</h3>'
        f'{body_pg}'
        '</a>'
    )

    # Card: shader hotlist
    top_s = _top_shaders(root)
    body_sh = _card_table(
        top_s,
        [
            ('shader', lambda r: base.h(r[0]), False),
            ('complexity', lambda r: base.fmt_float(r[1], 2), True),
            ('cost proxy', lambda r: base.fmt_float(r[2], 1), True),
        ]
    )
    cards.append(
        '<a class="dash-card" href="shader_hotlist.html">'
        '<h3>shader hotlist</h3>'
        f'{body_sh}'
        '</a>'
    )

    # Card: overdraw — by rejection ratio (1 - passed%)
    wo = _worst_overdraw(drops)
    body_od = _card_table(
        wo,
        [
            ('area', lambda r: base.h(r[0]), False),
            ('rt', lambda r: base.h(r[1]), False),
            ('rejected %', lambda r: base.fmt_pct(r[2]), True),
        ]
    )
    cards.append(
        '<a class="dash-card" href="overdraw.html">'
        '<h3>overdraw</h3>'
        f'{body_od}'
        '</a>'
    )

    # Card: draws by class — top 5 areas by draw count, dominant class
    pa = _per_area_draws(drops)
    pa_rows = sorted(pa.items(), key=lambda kv: kv[1]['n_draws'], reverse=True)[:5]
    body_dc = _card_table(
        pa_rows,
        [
            ('area', lambda r: base.h(r[0]), False),
            ('draws', lambda r: base.fmt_int(r[1]['n_draws']), True),
            ('dominant', lambda r: base.h(r[1]['dominant_class']), False),
        ]
    )
    cards.append(
        '<a class="dash-card" href="draws_by_class.html">'
        '<h3>draws by class</h3>'
        f'{body_dc}'
        '</a>'
    )

    parts.append(
        '<rdc-search-cards data-target=".dash-grid">'
        '<label for="rdc-search">filter</label>'
        '<input id="rdc-search" type="search" placeholder="filter cards">'
        '<span class="rdc-count"></span>'
        '</rdc-search-cards>'
    )
    parts.append(f'<div class="dash-grid">{"".join(cards)}</div>')

    # A/B section
    ab_root = os.path.join(out_dir, 'ab')
    if os.path.isdir(ab_root):
        ab_pairs = sorted(d for d in os.listdir(ab_root)
                          if os.path.isdir(os.path.join(ab_root, d)))
        if ab_pairs:
            parts.append(f'<h2 id="ab">a/b comparisons</h2>')
            parts.append('<div class="pair-list">')
            for pair in ab_pairs:
                files = sorted(f for f in os.listdir(os.path.join(ab_root, pair))
                               if f.endswith('.html'))
                chips = ''.join(
                    f'<a href="ab/{base.h(pair)}/{base.h(f)}" data-link-kind="primary">{base.h(f[:-5])}</a>'
                    for f in files
                )
                parts.append(
                    f'<div class="pair-group">'
                    f'<h3>{base.h(pair)}</h3>'
                    f'<div class="chip-cluster">{chips}</div>'
                    f'</div>'
                )
            parts.append('</div>')

    return base.write_report(out_path, [base.report_page(
        'reports dashboard', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(), crumb_depth=1, current_page='dashboard',
        kpis=_global_kpis(drops),
        device=base.provenance_strip(*base.newest_drop_provenance(root, drops)))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='dashboard'))
