"""Draws-by-class report.

Stacked horizontal bars per (area, drop_date), proportional within the bar.
Segments colored by draw_class. Below: raw-count table.
"""

from __future__ import annotations

import os
import statistics
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as papq

from . import base
from .. import aggregates as _agg


def _gather_from_drops(drops: list) -> tuple[dict, list, list, int]:
    """Return (counts, areas, drop_keys, total_captures).

    counts[(area, drop_key)][draw_class] = int.
    """
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    areas: set[str] = set()
    drop_keys: list[str] = []
    seen_captures: set[tuple] = set()

    for d in drops:
        drop_keys.append(d.key)
        for r in d.rows:
            p = os.path.join(r.drop_dir, 'draws.parquet')
            if not os.path.exists(p):
                continue
            try:
                t = papq.read_table(p, columns=['area', 'capture', 'draw_class'])
            except Exception:
                continue
            if t.num_rows == 0:
                continue
            a = t.column('area').to_pylist()
            cap = t.column('capture').to_pylist()
            cl = t.column('draw_class').to_pylist()
            for i in range(t.num_rows):
                counts[(a[i], d.key)][cl[i] or 'other'] += 1
                areas.add(a[i])
                seen_captures.add((a[i], d.key, cap[i]))

    return counts, sorted(areas), drop_keys, len(seen_captures)


def _build_table(counts: dict, drop_keys: list) -> str:
    # v0.2.6-4: adopt the data_table component (ADR-43; the golden absorbs the markup normalization). No
    # column groups - a compact fixed-column matrix; sort + auto-heatmap are the useful enhancements here.
    draw_classes = base.DRAW_CLASSES
    keys = sorted(counts.keys(), key=lambda k: (k[1], k[0]))
    hi_total = max((sum(counts[k].values()) for k in keys), default=0)

    # c16n: the area/drop text cells truncate via the default-tier .clip (escape + length-gated title=).
    cols = [base.Column('area', 'area', clip='default'),
            base.Column('drop', 'drop', clip='default'),
            base.Column('total', 'total', numeric=True,
                        render=lambda v, row: base.heatmap_cell(v, 0, row['_hi'],
                                                                text=base.fmt_int(v)))]
    cols += [base.Column(c, c, numeric=True) for c in draw_classes]
    cols.append(base.Column('ratio', 'prepass / opaque', numeric=True,
                            title='prepass draws divided by opaque draws (depth-prepass ratio)'))

    rows = []
    for area, date in keys:
        cc = counts[(area, date)]
        ratio = (cc.get('prepass', 0) / cc['opaque']) if cc.get('opaque', 0) else 0.0
        row = {'area': area, 'drop': date, 'total': sum(cc.values()), '_hi': hi_total,
               'ratio': base.fmt_float(ratio, 2)}
        for c in draw_classes:
            row[c] = base.fmt_int(cc.get(c, 0))
        rows.append(row)
    return base.data_table(cols, rows, table_key='draws_by_class',
                           default_sort='opaque', default_dir='desc',
                           caption='raw draw counts per class, per area and drop')


def _compute_kpis(counts: dict, areas: list, total_frames: int) -> list:
    """Hero KPIs (current run): mean draws / frame + the labeled raw total, n areas, the MEDIAN
    prepass/opaque ratio across areas, dominant class. Q-12: lead with the per-frame mean (the
    capture-count-independent number) and label the total. Q-11: `statistics.median` (not the
    upper-middle `sorted[n//2]`), and the label names the estimator + population."""
    total = sum(sum(cc.values()) for cc in counts.values())
    ratios = []
    class_totals: Counter = Counter()
    for cc in counts.values():
        for cls, n in cc.items():
            class_totals[cls] += n
        op = cc.get('opaque', 0)
        if op:
            ratios.append(cc.get('prepass', 0) / op)
    median_ratio = statistics.median(ratios) if ratios else 0.0
    dominant_cls = (class_totals.most_common(1)[0][0]
                    if class_totals else '')
    mean_draws = base.per_frame(total, total_frames)   # per frame (no-op when frames<=1)
    return [
        {'label': 'mean draws / frame', 'value': base.fmt_int(round(mean_draws))},
        {'label': 'total draws over captures', 'value': base.fmt_int(total)},
        {'label': 'areas',       'value': base.fmt_int(len(areas))},
        {'label': 'median prepass / opaque (across areas)', 'value': base.fmt_float(median_ratio, 2)},
        {'label': 'dominant class', 'value': dominant_cls or '-'},
    ]


def build(root: str, *, drops: list | None = None, ab=None,
          run_label=None, run_date=None,
          sink: base.AssetSink = base.AssetSink.INLINE,
          build_ts: str | None = None, redact: bool = False, theme: dict | None = None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    # Run model (ADR-35): the donut + headline KPIs reflect the CURRENT run only; the per-(area,drop)
    # table below keeps every run as the breakdown / comparison view.
    rc = base.run_context(drops, run_label=run_label, run_date=run_date)
    cur = rc.current
    drops = rc.history   # R-22: cross-drop data scoped to <= current (picker still lists all via rc)
    counts, areas, drop_keys, total_captures = _gather_from_drops(drops)
    cur_counts = {k: cc for k, cc in counts.items() if cur and k[1] == cur.key}
    cur_areas = cur.areas if cur else []
    # Q-12: per-frame mean draws needs the current run's captured-frame count (the single owner, D-15).
    cur_frames = sum(v['frames'] for v in (_agg.frame_counts(root, [cur]) if cur else {}).values())

    parts = []

    # Summary bar: dominant class (current run)
    class_totals: Counter = Counter()
    for cc in cur_counts.values():
        for cls, n in cc.items():
            class_totals[cls] += n
    grand_total = sum(class_totals.values()) or 1
    top_three = class_totals.most_common(3)
    if top_three:
        dom_cls, dom_n = top_three[0]
        dom_pct = 100.0 * dom_n / grand_total
        sub_bits = [f'{cls} {base.fmt_float(100.0 * n / grand_total, 1)}%'
                    for cls, n in top_three[1:]]
        sub_text = f'across {len(cur_areas)} areas; next: ' + ', '.join(sub_bits) if sub_bits else f'across {len(cur_areas)} areas'
        parts.append(base.summary_bar(
            'dominant class',
            f'{dom_cls} {base.fmt_float(dom_pct, 1)}%',
            sub=sub_text,
            tone='neutral',
        ))
        # Insight: a single class dominating the draw mix is the batching/instancing lever.
        sev = 'info' if dom_pct >= 50.0 else 'neutral'
        parts.append(base.callout(
            sev,
            f'{dom_cls} is {base.fmt_float(dom_pct, 1)}% of all draws',
            f'{base.fmt_int(grand_total)} draws across {len(cur_areas)} area(s) - the dominant class is '
            f'where instancing / batching pays off most.',
            href='#counts', link_text='see counts'))

    if not counts:
        parts.append(base.empty_state('no draws found in any drop'))
    else:
        # Section 1: flagship charts - class-share donut (current run) + per area/drop pct-stacked bars.
        # c16c: framed in a sticky-highlighted section card.
        sec_stacked = [base.legend()]
        donut_segs = [(c, class_totals.get(c, 0), base.class_color_var(c))
                      for c in base.DRAW_CLASSES if class_totals.get(c, 0) > 0]
        sec_stacked.append(base.figure(
            base.donut(donut_segs, center_label=base.fmt_int(grand_total),
                       title='draw class share',
                       desc='share of draws by class in the current run'),
            'draw-class share (current run)'))
        keys = sorted(counts.keys(), key=lambda k: (k[1], k[0]))
        rows = [(f'{area} / {date}', dict(counts[(area, date)])) for area, date in keys]
        sec_stacked.append(base.figure(
            base.pct_stacked_bar(rows, title='class mix per area / drop',
                                 desc='each bar is one area/drop normalized to 100% by draw class'),
            'class mix per area / drop (100%)'))
        parts.append('<rdc-sticky-h2>'
                     + base.section_card('stacked', 'class share per area / drop',
                                         ''.join(sec_stacked))
                     + '</rdc-sticky-h2>')

        # Section 2: raw counts table (the data_table component builds the host + sort + auto-heatmap).
        counts_body = str(_build_table(counts, drop_keys))
        parts.append('<rdc-sticky-h2>'
                     + base.section_card('counts', 'raw counts per class', counts_body,
                                         count=len(counts))
                     + '</rdc-sticky-h2>')

    out_path = base.output_path(root, 'draws_by_class', ab, run=rc)
    return base.write_report(out_path, [base.report_page(
        'draws by class', parts,
        drops=len(drops), captures=total_captures, build_ts=build_ts or base.now_iso(),
        crumb_depth=base.crumb_depth(ab, run=rc), ab=ab, root=root, report_key='draws_by_class',
        sink=sink, theme=theme,
        kpis=_compute_kpis(cur_counts, cur_areas, cur_frames), run=rc,
        device=base.provenance_strip(*base.newest_drop_provenance(root, [cur] if cur else []), redact=redact))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='draws_by_class'))
