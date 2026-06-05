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
from .. import aggregates as _agg
from .. import paths as _paths


def _top_meshes(root: str, current, n: int = 3) -> list:
    """Return [(label, repeat, indices_med)] where label is a human-readable synthetic.

    Scoped to the CURRENT run (ADR-35). The mesh repeat-count atom is the single-source
    `aggregates.draw_aggregates` (G-26) collapsed across areas, so this card, the instancing report,
    and the verdict can never disagree. c16v normalizes `repeat` per frame; here it is the raw
    per-run occurrence count (the helper's contract is unchanged).
    """
    if current is None:
        return []
    da = _agg.draw_aggregates(root, [current])
    counts: Counter = Counter()
    indices: dict = defaultdict(list)
    cls_by_mesh: dict = {}
    pass_by_mesh: dict = {}
    for (dk, area, mh), c in da.count.items():
        counts[mh] += base.per_frame(c, da.frames(dk, area))   # c16v: per frame, summed across areas
        indices[mh].extend(da.num_indices[(dk, area, mh)])
        cls_by_mesh.setdefault(mh, da.draw_class[(dk, area, mh)])
        pass_by_mesh.setdefault(mh, da.pass_norm[(dk, area, mh)])
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
            cols = base._to_dict_of_lists(t)   # Q-7
            for i in range(t.num_rows):
                key = (cols['area'][i], cols['marker_path_norm'][i] or '')
                agg[key] += cols['sum_gpu_duration_s'][i] or 0.0
    ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [(a, base.pass_suffix(m) or m, g) for (a, m), g in ranked]


def _top_shaders(root: str, current, n: int = 3) -> list:
    """Return [(label, complexity, cost_proxy)] where label is `frag-cplx-{int(cplx)}`.

    Scoped to the CURRENT run (ADR-35) via the cache's drop_date/drop_label columns.
    """
    if current is None:
        return []
    sa = _agg.shader_aggregates(root, [current], stage='fragment')
    cost: dict = defaultdict(float)
    cplx: dict = {}
    stype: dict = {}
    for (dk, area, sk), cs in sa.cost_sum.items():
        cost[sk] += base.per_frame(cs, sa.frames(dk, area))    # c16v: cost per frame (complexity unchanged)
        cplx[sk] = max(cplx.get(sk, 0), sa.cplx[(dk, area, sk)])
        stype[sk] = sa.stype[(dk, area, sk)]
    ranked = sorted(cost.items(), key=lambda kv: kv[1], reverse=True)[:n]
    out = []
    for sk, c in ranked:
        cval = cplx[sk]
        label = f'{stype[sk][:4]}-cplx-{int(cval)}'
        out.append((label, cval, c))
    return out


def _top_shaders_by_area(root: str, current, n: int = 999) -> list:
    """Return [(area, label, complexity, cost_proxy)] for the CURRENT run, keyed per (area,
    stable_key), ranked by COMPLEXITY desc.

    The area-resolved sibling of `_top_shaders` (which collapses across areas + ranks by cost).
    Reuses the same sha256-validated shader_summary cache + run filter (+ the `area` column); used by
    the c16q health verdict (summary.py) to derive each area's worst shader complexity and to name
    the worst shader's area. The verdict keys on COMPLEXITY (per-shader max), not cost. NOT called by
    `build()`."""
    if current is None:
        return []
    sa = _agg.shader_aggregates(root, [current], stage='fragment')
    cost: dict = defaultdict(float)
    cplx: dict = {}
    stype: dict = {}
    for (dk, area, sk), cs in sa.cost_sum.items():
        key = (area, sk)
        cost[key] += base.per_frame(cs, sa.frames(dk, area))   # c16v: cost per frame
        cplx[key] = max(cplx.get(key, 0.0), sa.cplx[(dk, area, sk)])
        stype[key] = sa.stype[(dk, area, sk)]
    rows = [(area, f'{stype[(area, sk)][:4]}-cplx-{int(cval)}', cval, cost[(area, sk)])
            for (area, sk), cval in cplx.items()]
    rows.sort(key=lambda x: x[2], reverse=True)
    return rows[:n]


def _per_area_draws(drops: list) -> tuple[dict, Counter]:
    """Return ({area: {n_draws, dominant_class}}, class_totals) where class_totals sums all areas."""
    per: dict = defaultdict(lambda: {'n_draws': 0, 'by_class': Counter()})
    class_totals: Counter = Counter()
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'pass_class_breakdown.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=['area', 'draw_class', 'n_draws'])
            except Exception:
                continue
            cols = base._to_dict_of_lists(t)   # Q-7
            for i in range(t.num_rows):
                a = cols['area'][i]
                cls = cols['draw_class'][i] or 'other'
                n = cols['n_draws'][i] or 0
                per[a]['n_draws'] += n
                per[a]['by_class'][cls] += n
                class_totals[cls] += n
    res: dict = {}
    for a, v in per.items():
        dom = v['by_class'].most_common(1)[0][0] if v['by_class'] else '-'
        res[a] = {'n_draws': v['n_draws'], 'dominant_class': dom}
    return res, class_totals


def _top_areas_gpu(drops: list, n: int = 3) -> list:
    """Return [(area, gpu_s, draws, avg_draws_frame, avg_gpu_frame)] top by gpu. `draws` is the
    per-area total over that area's captured frames; `avg_draws_frame` = draws / frames is the
    per-area average draw load (capture-count-independent) - the meaningful "draws per area" number
    (one per area, so it belongs in this card, not the single-value headline KPI strip).

    The 5th element `avg_gpu_frame` (gpu_s / frames, also capture-count-independent) was added for the
    c16q health one-pager (summary.py, which derives each area's per-frame gpu + gpu-regression from
    it). `dashboard.build()` indexes only [0..3], so the dashboard output is unchanged by it."""
    agg: dict = defaultdict(lambda: {'gpu': 0.0, 'draws': 0, 'frames': 0})
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
            agg[r.area]['frames'] += t.num_rows
    rows = [(a, v['gpu'], v['draws'],
             (v['draws'] / v['frames'] if v['frames'] else 0.0),
             (v['gpu'] / v['frames'] if v['frames'] else 0.0))
            for a, v in agg.items()]
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows[:n]


def _top_meshes_by_area(root: str, current, n: int = 999) -> list:
    """Return [(area, label, repeat, indices_med)] for the CURRENT run, keyed per (area, mesh_hash),
    ordered by repeat desc.

    The area-resolved sibling of `_top_meshes` (which collapses across areas). Sources the repeat-count
    atom from `aggregates.draw_aggregates` (G-26), keyed per (area, mesh_hash); used by the c16q health
    verdict (summary.py) to derive each area's worst mesh repeat-count. NOT called by `build()`.
    c16v per-frame-normalizes the repeat count at the aggregates seam, so the verdict and the
    instancing report read the SAME per-frame number."""
    if current is None:
        return []
    da = _agg.draw_aggregates(root, [current])
    counts: Counter = Counter()
    for (dk, area, mh), c in da.count.items():
        counts[(area, mh)] += base.per_frame(c, da.frames(dk, area))   # c16v: repeat per frame
    out = []
    for (area, mh), c in counts.most_common(n):
        k = (current.key, area, mh)
        idx = da.num_indices.get(k, [])
        try:
            med = int(statistics.median(idx)) if idx else 0
        except statistics.StatisticsError:
            med = 0
        cls = da.draw_class.get(k, 'other')
        suffix = base.pass_suffix(da.pass_norm.get(k, '')) or '?'
        hash_tag = str(mh)[-4:] if mh else ''
        label = f'{cls}/{suffix}/{med}v#{hash_tag}'
        out.append((area, label, c, med))
    return out


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
            cols = base._to_dict_of_lists(t)   # Q-7
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


def _run_totals(drops: list) -> tuple:
    """Pooled (total_gpu_s, total_draws, n_frames) over frame_totals across `drops`.

    The raw basis for `_global_kpis`' per-frame averages, factored out so the c16q health one-pager
    (summary.py) derives the SAME headline averages + the per-run sparkline series from one source (it
    reads raw floats, not the formatted KPI strings). `n_frames` is the count of frame rows that fed
    the totals, so `total / n_frames` is the true arithmetic mean.
    """
    total_gpu = 0.0
    total_draws = 0
    n_frames = 0
    for d in drops:
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'frame_totals.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=['total_gpu_duration_s', 'n_draws'])
            except Exception:
                continue
            n_frames += t.num_rows
            for v in t.column('total_gpu_duration_s').to_pylist():
                if v is not None:
                    total_gpu += float(v)
            for v in t.column('n_draws').to_pylist():
                if v is not None:
                    total_draws += int(v)
    return total_gpu, total_draws, n_frames


def _global_kpis(drops: list) -> list:
    """Cheap-to-compute global numbers from frame_totals across drops.

    Totals are paired with PER-FRAME and PER-AREA averages: a raw "total draws" reads as alarming on
    its own, but the mean PER CAPTURED FRAME is the number that informs a budget decision. n_frames is
    the count of frame rows that fed the totals, so each average is the true arithmetic mean of the
    summed values (self-consistent with the total). Per-AREA averages are NOT a single headline number
    (one value per area) - they live in the per-area trend card (_top_areas_gpu), not here.
    """
    total_gpu, total_draws, n_frames = _run_totals(drops)
    areas: set = set()
    for d in drops:
        areas.update(d.areas)
    avg_gpu_frame = (total_gpu / n_frames) if n_frames else 0.0
    avg_draws_frame = (total_draws / n_frames) if n_frames else 0.0
    return [
        {'label': 'total gpu (s)',      'value': base.fmt_float(total_gpu, 3)},
        {'label': 'avg gpu / frame (s)', 'value': base.fmt_float(avg_gpu_frame, 4)},
        {'label': 'total draws',        'value': base.fmt_int(total_draws)},
        {'label': 'avg draws / frame',  'value': base.fmt_int(round(avg_draws_frame))},
        {'label': 'areas',              'value': base.fmt_int(len(areas))},
    ]


def _card_table(rows: list, columns: list, *, caption: str = '') -> str:
    # c16l (ADR-38): a dashboard mini is a 3-row preview INSIDE the card-link <a>. It uses the unified
    # `table.data` styling for visual consistency but is deliberately NOT wrapped in <rdc-table>: a
    # sortable header inside a nav-card would both sort and navigate, and cursor:pointer would mis-signal.
    # So it stays a plain server-baked table (no sort/heatmap enhancement) - the right call for a preview.
    if not rows:
        return base.empty_state('no data yet')
    parts = ['<table class="data">']
    if caption:
        parts.append(f'<caption>{base.h(caption)}</caption>')
    parts.append('<thead><tr>')
    for col_name, _, num in columns:
        cls = ' class="num"' if num else ''
        # c16m: the mini uses table-layout:fixed (so it never overflows the card), which can clip a long
        # HEADER too (e.g. "avg draws / frame"). Carry the full header in title= so it also reveals on hover.
        parts.append(f'<th{cls} scope="col" title="{base.h(col_name)}">{base.h(col_name)}</th>')
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        for col_name, fn, num in columns:
            cls = ' class="num"' if num else ''
            val = fn(row)
            # c16m: a bare mini is not engine-hosted, so it carries no inner `.clip` + JS title. Set a
            # server-side title= on the (clippable) text cells so the FULL value is revealed on hover -
            # the cell text stays inline, so the td-level ellipsis still renders + Ctrl-F still matches.
            # val is already escaped plain text (base.h / safe_chrome_text), so it is attribute-safe.
            title = f' title="{val}"' if (not num and val) else ''
            parts.append(f'<td{cls}{title}>{val}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts)


def _card(href: str, title: str, subtitle: str, chart: str, table: str) -> str:
    """One dashboard small-multiple card: title + insight subtitle + mini chart + summary table.

    The card itself is the drill link to the full report (c16c)."""
    sub = (f'<p class="dash-sub">{base.safe_chrome_text(subtitle)}</p>'
           if subtitle else '')
    return (f'<a class="dash-card" href="{base.h(href)}">'
            f'<h3>{base.h(title)}</h3>{sub}{chart}{table}</a>')


def build(root: str, *, drops: list | None = None, ab=None,
          run_label=None, run_date=None,
          sink: base.AssetSink = base.AssetSink.INLINE,
          build_ts: str | None = None, redact: bool = False) -> str:
    if drops is None:
        drops = base.discover_drops(root)

    # Run model (ADR-35): the dashboard reports the CURRENT run only (default newest); prior runs
    # are baselines for trend context, never summed into a headline. Aggregators that loop a drop
    # list receive just the current run; the cache-readers filter to its (date, label).
    rc = base.run_context(drops, run_label=run_label, run_date=run_date)
    cur = rc.current
    cur_drops = [cur] if cur else []

    # c16f: a per-run dashboard lives at _reports/run/<key>/index.html; its sibling reports (instancing
    # etc.) are pre-rendered there too, so their links stay bare. trend_table is NOT per-run (it is the
    # across-run view), so its link is prefixed up to the top-level _reports/ on a per-run dashboard.
    crumb = base.crumb_depth(None, run=rc)
    up = '../' * (crumb - 1)            # '' on the top-level dashboard, '../../' on a per-run one
    tt_href = f'{up}trend_table.html'
    reports_top = _paths.reports_dir(root)   # the A/B index always lives at the top level
    out_path = base.output_path(root, 'index', None, run=rc)
    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)

    parts = []
    cards = []

    # Cross-report nav: jump chips to every report (c16c).
    _NAV = [
        (tt_href, 'trend table'),
        ('instancing_opportunities.html', 'instancing'),
        ('pass_gpu.html', 'pass gpu'),
        ('shader_hotlist.html', 'shader hotlist'),
        ('overdraw.html', 'overdraw'),
        ('draws_by_class.html', 'draws by class'),
        ('summary.html', 'build health'),   # c16q: the exec one-pager (co-rendered per run, so bare)
    ]

    # Summary bar: worst area by GPU rank + current-run counts
    top_a = _top_areas_gpu(cur_drops, n=999)
    n_areas = len(top_a)
    total_draws = sum(t[2] for t in top_a)
    if top_a:
        worst_area, worst_gpu, worst_draws = top_a[0][:3]
        parts.append(base.summary_bar(
            'worst gpu area',
            worst_area,
            sub=(f'rank 1 of {n_areas} areas; this area {base.fmt_int(worst_draws)} draws; '
                 f'all areas {base.fmt_int(total_draws)} draws'),
            link_href=f'{tt_href}#gpu',
            link_text='trend',
            tone='neutral',
        ))

    # Cross-report nav strip.
    parts.append('<nav class="chip-cluster" aria-label="reports">'
                 + ''.join(f'<a href="{href}" data-link-kind="primary">{base.h(lbl)}</a>'
                           for href, lbl in _NAV)
                 + '</nav>')

    # Card: trend table - GPU time per area (mini bars matching the trend flagship).
    top_a = top_a[:3]
    chart_tt = base.figure(base.bar_chart(
        [(a, g) for a, g, *_ in top_a], value_fmt=lambda v: f'{v:.3f}', width=280,
        title='gpu (s) per area', desc='top areas by GPU seconds', chart_id='dash-tt'))
    body_tt = _card_table(
        top_a,
        [
            ('area', lambda r: base.h(r[0]), False),
            ('gpu (s)', lambda r: base.fmt_float(r[1], 3), True),
            ('draws', lambda r: base.fmt_int(r[2]), True),
            ('avg draws / frame', lambda r: base.fmt_int(round(r[3])), True),
        ],
        caption='per-area GPU + draw load (avg draws per captured frame)')
    sub_tt = ('GPU time per area in the current run.'
              + (f' worst: {top_a[0][0]} {base.fmt_float(top_a[0][1], 3)}s' if top_a else ''))
    cards.append(_card(tt_href, 'trend table', sub_tt, chart_tt, body_tt))

    # Card: instancing - repeat per mesh (mini bars).
    top_m = _top_meshes(root, cur)
    chart_im = base.figure(base.bar_chart(
        [(lbl, rep) for lbl, rep, _ in top_m], value_fmt=lambda v: base.fmt_int(int(v)), width=280,
        title='repeat per mesh', desc='most-repeated meshes', chart_id='dash-im'))
    body_im = _card_table(
        top_m,
        [
            ('mesh', lambda r: base.h(r[0]), False),
            ('repeat', lambda r: base.fmt_int(r[1]), True),
            ('indices typ', lambda r: base.fmt_int(r[2]), True),
        ],
        caption='most-repeated meshes')
    sub_im = ('Repeated meshes worth instancing or batching.'
              + (f' top: {top_m[0][0]} x{base.fmt_int(top_m[0][1])}' if top_m else ''))
    cards.append(_card('instancing_opportunities.html', 'instancing opportunities',
                       sub_im, chart_im, body_im))

    # Card: pass gpu - GPU per pass (mini bars).
    top_p = _top_passes(cur_drops)
    chart_pg = base.figure(base.bar_chart(
        [(pl, g) for _, pl, g in top_p], value_fmt=lambda v: f'{v:.3f}', width=280,
        title='gpu (s) per pass', desc='heaviest passes by GPU seconds', chart_id='dash-pg'))
    body_pg = _card_table(
        top_p,
        [
            ('area', lambda r: base.h(r[0]), False),
            # c16m: emit the FULL marker (was builder-truncated via trunc_left, which discarded the value
            # so hover could never reveal it). The CSS clip now truncates the display + the td title=
            # reveals the full value on hover - consistent with every other mini text column.
            ('marker', lambda r: base.safe_chrome_text(r[1]), False),
            ('gpu (s)', lambda r: base.fmt_float(r[2], 3), True),
        ],
        caption='heaviest passes by GPU time')
    sub_pg = ('Heaviest GPU passes.'
              + (f' top: {top_p[0][1]} {base.fmt_float(top_p[0][2], 3)}s in {top_p[0][0]}'
                 if top_p else ''))
    cards.append(_card('pass_gpu.html', 'pass gpu', sub_pg, chart_pg, body_pg))

    # Card: shader hotlist - cost proxy per shader (mini bars).
    top_s = _top_shaders(root, cur)
    chart_sh = base.figure(base.bar_chart(
        [(lbl, cost) for lbl, _, cost in top_s], value_fmt=lambda v: f'{v:.1f}', width=280,
        title='cost proxy per shader', desc='costliest shaders', chart_id='dash-sh'))
    body_sh = _card_table(
        top_s,
        [
            ('shader', lambda r: base.h(r[0]), False),
            ('complexity', lambda r: base.fmt_float(r[1], 2), True),
            ('cost proxy', lambda r: base.fmt_float(r[2], 1), True),
        ],
        caption='costliest shaders by cost proxy')
    sub_sh = ('Costliest shaders (complexity x uses).'
              + (f' top: {top_s[0][0]} cost {base.fmt_float(top_s[0][2], 1)}' if top_s else ''))
    cards.append(_card('shader_hotlist.html', 'shader hotlist', sub_sh, chart_sh, body_sh))

    # Card: overdraw - rejection % per RT (mini bars, 0-100 scale).
    wo = _worst_overdraw(cur_drops)
    chart_od = base.figure(base.bar_chart(
        [(rt, pct) for _, rt, pct, _ in wo], value_fmt=lambda v: f'{v:.1f}%',
        max_value=100.0, width=280,
        title='rejection % per rt', desc='worst render targets by sample rejection', chart_id='dash-od'))
    body_od = _card_table(
        wo,
        [
            ('area', lambda r: base.h(r[0]), False),
            ('rt', lambda r: base.h(r[1]), False),
            ('rejected %', lambda r: base.fmt_pct(r[2]), True),
        ],
        caption='worst render targets by rejection')
    sub_od = ('Sample rejection per render target.'
              + (f' worst: {wo[0][1]} {base.fmt_pct(wo[0][2])} in {wo[0][0]}' if wo else ''))
    cards.append(_card('overdraw.html', 'overdraw', sub_od, chart_od, body_od))

    # Card: draws by class - class-share donut (matching the draws_by_class flagship).
    pa, class_totals = _per_area_draws(cur_drops)
    pa_rows = sorted(pa.items(), key=lambda kv: kv[1]['n_draws'], reverse=True)[:5]
    grand = sum(class_totals.values())
    donut_segs = [(cls, class_totals.get(cls, 0), base.class_color_var(cls))
                  for cls in base.DRAW_CLASSES if class_totals.get(cls, 0) > 0]
    chart_dc = base.figure(base.donut(
        donut_segs, center_label=base.fmt_int(grand), width=180,
        title='draw class share', desc='share of all draws by class'))
    body_dc = _card_table(
        pa_rows,
        [
            ('area', lambda r: base.h(r[0]), False),
            ('draws', lambda r: base.fmt_int(r[1]['n_draws']), True),
            ('dominant', lambda r: base.h(r[1]['dominant_class']), False),
        ],
        caption='top areas by draw count')
    dom = class_totals.most_common(1)[0] if class_totals else None
    sub_dc = ('Draw mix by class.'
              + (f' dominant: {dom[0]} {base.fmt_pct(100.0 * dom[1] / grand)}'
                 if dom and grand else ''))
    cards.append(_card('draws_by_class.html', 'draws by class', sub_dc, chart_dc, body_dc))

    parts.append(
        '<rdc-search-cards data-target=".dash-grid">'
        '<label for="rdc-search">filter</label>'
        '<input id="rdc-search" type="search" placeholder="filter cards">'
        '<span class="rdc-count"></span>'
        '</rdc-search-cards>'
    )
    parts.append(f'<div class="dash-grid">{"".join(cards)}</div>')

    # A/B section: only on the top-level (newest) dashboard. A per-run dashboard is a single-run
    # snapshot; the A/B comparison index lives at the top level and its links are _reports-relative.
    ab_root = os.path.join(reports_top, 'ab')
    if rc.is_newest and os.path.isdir(ab_root):
        ab_pairs = sorted(d for d in os.listdir(ab_root)
                          if os.path.isdir(os.path.join(ab_root, d)))
        if ab_pairs:
            ab_body = ['<div class="pair-list">']
            for pair in ab_pairs:
                files = sorted(f for f in os.listdir(os.path.join(ab_root, pair))
                               if f.endswith('.html'))
                chips = ''.join(
                    f'<a href="ab/{base.h(pair)}/{base.h(f)}" data-link-kind="primary">{base.h(f[:-5])}</a>'
                    for f in files
                )
                ab_body.append(
                    f'<div class="pair-group">'
                    f'<h3>{base.h(pair)}</h3>'
                    f'<div class="chip-cluster">{chips}</div>'
                    f'</div>'
                )
            ab_body.append('</div>')
            parts.append('<rdc-sticky-h2>'
                         + base.section_card('ab', 'a/b comparisons', ''.join(ab_body))
                         + '</rdc-sticky-h2>')

    return base.write_report(out_path, [base.report_page(
        'reports dashboard', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=build_ts or base.now_iso(), crumb_depth=crumb, current_page='dashboard',
        kpis=_global_kpis(cur_drops), run=rc, root=root, run_nav_key='index', sink=sink,
        device=base.provenance_strip(*base.newest_drop_provenance(root, cur_drops), redact=redact))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='dashboard'))
