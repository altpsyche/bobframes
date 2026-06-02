"""Per-area pass GPU breakdown. Stacked bars colored by draw_class.

Aggregation key: (area, marker_path_norm). Captures + classes summed.
Bar widths normalized within each area (share-of-area-total).
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

import pyarrow.parquet as papq

from . import base


def _aggregate(drops: list, ok_caps: set) -> dict:
    """Return {area: {marker: {drop_key: {'gpu': sum, 'draws': sum,
                                            'verts': sum,
                                            'class_gpu': {cls: sum}}}}}."""
    out: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: {'gpu': 0.0, 'draws': 0, 'verts': 0,
                 'class_gpu': defaultdict(float)})))
    for d in drops:
        drop_key = d.key
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'pass_class_breakdown.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p)
            except Exception:
                continue
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            for i in range(t.num_rows):
                cap = cols['capture'][i]
                key = (r.area, r.drop_date, r.drop_label, cap)
                if ok_caps and key not in ok_caps:
                    continue
                marker = cols['marker_path_norm'][i] or ''
                cls = cols['draw_class'][i] or 'other'
                gpu = cols['sum_gpu_duration_s'][i] or 0.0
                ndr = cols['n_draws'][i] or 0
                verts = cols['sum_pre_vs_vertices'][i] or 0
                bucket = out[r.area][marker][drop_key]
                bucket['gpu'] += gpu
                bucket['draws'] += ndr
                bucket['verts'] += verts
                bucket['class_gpu'][cls] += gpu
    return out


def _drop_dir_for_area(drops: list, drop_key: str, area: str) -> str:
    for d in drops:
        if d.key != drop_key:
            continue
        for r in d.rows:
            if r.area == area:
                return r.drop_dir
    return ''


def build(root: str, *, drops: list | None = None, ab=None,
          run_label=None, run_date=None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    # Run model (ADR-35): GPU headline + treemap + per-area ranking reflect the CURRENT run; the
    # per-drop GPU comparison rows below keep every run.
    rc = base.run_context(drops, run_label=run_label, run_date=run_date)
    cur = rc.current
    ck = cur.key if cur else None
    out_path = base.output_path(root, 'pass_gpu', ab, run=rc)
    out_dir = os.path.dirname(out_path)

    ok_caps = base.ok_capture_set(root)
    data = _aggregate(drops, ok_caps)
    drop_keys = [d.key for d in drops]

    def _cur_gpu(drop_buckets) -> float:
        return drop_buckets.get(ck, {}).get('gpu', 0.0)

    parts = []

    # Hero KPIs: current-run total GPU, area + pass counts (passes/areas with current-run GPU only).
    total_gpu = 0.0
    n_passes = 0
    cur_areas_set: set = set()
    for area, _markers in data.items():
        for _buckets in _markers.values():
            g = _cur_gpu(_buckets)
            if g <= 0:
                continue
            total_gpu += g
            n_passes += 1
            cur_areas_set.add(area)
    kpis = [
        {'label': 'total gpu (s)', 'value': base.fmt_float(total_gpu, 3)},
        {'label': 'areas',         'value': base.fmt_int(len(cur_areas_set))},
        {'label': 'passes',        'value': base.fmt_int(n_passes)},
    ]

    # Summary bar: top pass in the current run + area count
    if cur_areas_set:
        global_top = None
        global_top_gpu = 0.0
        for area, markers in data.items():
            for marker, drop_buckets in markers.items():
                mg = _cur_gpu(drop_buckets)
                if mg > global_top_gpu:
                    global_top_gpu = mg
                    global_top = (area, base.pass_suffix(marker) or marker)
        if global_top is not None:
            area, marker_short = global_top
            parts.append(base.summary_bar(
                'top pass',
                f'{area} / {marker_short}',
                sub=f'across {len(cur_areas_set)} areas',
                link_href=f'#{base.h(area)}',
                link_text='area',
                tone='neutral',
            ))
            # Insight: the single heaviest pass is where GPU-time investigation starts.
            parts.append(base.callout(
                'info',
                f'heaviest pass: {area} / {marker_short}',
                f'{base.fmt_float(global_top_gpu, 3)}s GPU on the costliest capture - '
                f'profile this pass first.',
                href=f'#{base.h(area)}', link_text='jump to area'))

    parts.append(base.legend())

    if not cur_areas_set:
        parts.append(base.empty_state('no pass_class_breakdown data found'))
    else:
        for ai, area in enumerate(sorted(cur_areas_set)):
            markers = data[area]
            ranked = sorted(
                ((marker, db) for marker, db in markers.items() if _cur_gpu(db) > 0),
                key=lambda kv: _cur_gpu(kv[1]),
                reverse=True,
            )[:20]
            area_total = sum(_cur_gpu(db) for _, db in ranked) or 1.0

            area_body = []
            for marker, drop_buckets in ranked:
                cur_g = _cur_gpu(drop_buckets)
                latest_bucket = drop_buckets.get(ck, {})
                latest_class_gpu = dict(latest_bucket.get('class_gpu', {}))
                latest_gpu = latest_bucket.get('gpu', 0.0)
                latest_draws = latest_bucket.get('draws', 0)
                latest_verts = latest_bucket.get('verts', 0)

                bar_total = latest_gpu if latest_gpu > 0 else cur_g
                bar_weights = latest_class_gpu
                if bar_total <= 0:
                    bar_weights = {'other': 1.0}
                    bar_total = 1.0

                rep_drop = ck
                drop_dir = _drop_dir_for_area(drops, rep_drop, area)
                link = base.rel_path_to_drop_index(out_dir, drop_dir, 'passes') if drop_dir else '#'

                pct_share = (cur_g / area_total) * 100.0 if area_total > 0 else 0.0

                area_body.append('<div class="bar-row">')
                short = base.pass_short(marker)
                if len(short) > 60:
                    short = base.trunc_left(short, 60)
                area_body.append(
                    f'<span class="key" title="{base.h(marker)}">'
                    f'<rdc-copy-button data-value="{base.safe_chrome_text(marker)}" '
                    f'data-label="copy pass path"></rdc-copy-button>'
                    f'<a href="{base.h(link)}" data-link-kind="drill">'
                    f'{base.safe_chrome_text(short)}</a></span>'
                )
                bar_html = base.class_segments_bar(bar_weights, bar_total)
                area_body.append(f'<div style="width: {pct_share:.2f}%;">{bar_html}</div>')
                area_body.append(f'<span class="total">{pct_share:.1f}%</span>')
                area_body.append('</div>')

                if len(drop_keys) >= 2:
                    cells = ['<div class="bar-row">',
                             '<span class="key" style="color: var(--text-2)">drops</span>',
                             '<div style="display:flex;gap:var(--sp-3);font:var(--fs-small) ui-monospace,monospace;align-items:center;color:var(--text-2)">']
                    prev_gpu = None
                    for i, k in enumerate(drop_keys):
                        b = drop_buckets.get(k, {})
                        g = b.get('gpu', 0.0)
                        cells.append(f'<span>{base.h(k)}: {base.fmt_float(g, 3)}</span>')
                        if i > 0:
                            cells.append(base.delta_pill(
                                g, prev_gpu,
                                lower_is_better=True, fmt='{:+,.3f}'))
                        prev_gpu = g
                    cells.append('</div>')
                    cells.append(f'<span class="total" style="color:var(--text-3)">'
                                 f'draws {base.fmt_int(latest_draws)} | verts {base.fmt_int(latest_verts)}</span>')
                    cells.append('</div>')
                    area_body.append(''.join(cells))

            # Flagship: GPU-by-pass treemap + top-pass bars, above the per-pass share rows (c16b).
            sec = []
            chart_items = []
            for marker, drop_buckets in ranked:
                g = _cur_gpu(drop_buckets)
                if g <= 0:
                    continue
                cg = dict(drop_buckets.get(ck, {}).get('class_gpu', {}))
                dom = max(cg.items(), key=lambda kv: kv[1])[0] if cg else 'other'
                short = base.pass_short(marker) or marker or '(root)'
                chart_items.append((short, g, dom))
            if chart_items:
                sec.append(base.figure(
                    base.treemap([(lbl, g, base.class_color_var(d)) for lbl, g, d in chart_items],
                                 title='gpu by pass',
                                 desc='pass area sized by GPU time, colored by dominant draw class'),
                    f'{area}: GPU time by pass'))
                sec.append(base.figure(
                    base.bar_chart([(lbl, g) for lbl, g, _ in chart_items][:10],
                                   value_fmt=lambda v: f'{v:.3f}',
                                   title='top passes by gpu (s)',
                                   desc='heaviest passes by GPU seconds',
                                   chart_id=f'pg-bar-{ai}'),
                    f'{area}: top passes by GPU (s)'))

            # c16c: frame the per-area section in a sticky-highlighted card.
            sec.append(''.join(area_body))
            parts.append('<rdc-sticky-h2>'
                         + base.section_card(area, area, ''.join(sec), count=len(ranked))
                         + '</rdc-sticky-h2>')

    return base.write_report(out_path, [base.report_page(
        'pass gpu', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
        ab=ab, root=root, report_key='pass_gpu',
        kpis=kpis, run=rc,
        device=base.provenance_strip(*base.newest_drop_provenance(root, [cur] if cur else [])))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='pass_gpu'))
