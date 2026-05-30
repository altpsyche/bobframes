"""Draws-by-class report.

Stacked horizontal bars per (area, drop_date), proportional within the bar.
Segments colored by draw_class. Below: raw-count table.
"""

from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as papq

from . import base


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
    classes = base.DRAW_CLASSES
    rows = []
    rows.append('<table class="report"><thead><tr>')
    rows.append('<th>area</th><th>drop</th><th class="num">total</th>')
    for c in classes:
        rows.append(f'<th class="num">{base.h(c)}</th>')
    rows.append('<th class="num">prepass / opaque</th>')
    rows.append('</tr></thead><tbody>')

    keys = sorted(counts.keys(), key=lambda k: (k[1], k[0]))
    for area, date in keys:
        cc = counts[(area, date)]
        total = sum(cc.values())
        rows.append('<tr>')
        rows.append(f'<td>{base.h(area)}</td>')
        rows.append(f'<td>{base.h(date)}</td>')
        rows.append(f'<td class="num">{base.fmt_int(total)}</td>')
        for c in classes:
            n = cc.get(c, 0)
            rows.append(f'<td class="num">{base.fmt_int(n)}</td>')
        ratio = (cc.get('prepass', 0) / cc['opaque']) if cc.get('opaque', 0) else 0.0
        rows.append(f'<td class="num">{base.fmt_float(ratio, 2)}</td>')
        rows.append('</tr>')
    rows.append('</tbody></table>')
    return '\n'.join(rows)


def _compute_kpis(counts: dict, areas: list) -> list:
    """Hero KPIs: total draws, n areas, median prepass/opaque ratio, dominant class."""
    total = sum(sum(cc.values()) for cc in counts.values())
    ratios = []
    class_totals: Counter = Counter()
    for cc in counts.values():
        for cls, n in cc.items():
            class_totals[cls] += n
        op = cc.get('opaque', 0)
        if op:
            ratios.append(cc.get('prepass', 0) / op)
    median_ratio = (sorted(ratios)[len(ratios) // 2]
                    if ratios else 0.0)
    dominant_cls = (class_totals.most_common(1)[0][0]
                    if class_totals else '')
    return [
        {'label': 'total draws', 'value': base.fmt_int(total)},
        {'label': 'areas',       'value': base.fmt_int(len(areas))},
        {'label': 'prepass/opaque (med)', 'value': base.fmt_float(median_ratio, 2)},
        {'label': 'dominant class', 'value': dominant_cls or '-'},
    ]


def build(root: str, *, drops: list | None = None, ab=None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    counts, areas, drop_keys, total_captures = _gather_from_drops(drops)

    parts = [base.page_open('draws by class', hdr_offset_px=120)]
    parts.append(base.header(
        'draws by class',
        drops=len(drops), captures=total_captures, build_ts=base.now_iso(),
        crumb_depth=base.crumb_depth(ab),
    ))
    parts.append(base.ab_strip(ab))
    parts.append(base.ab_picker_for(root, 'draws_by_class', ab=ab))

    # Summary bar: dominant class
    class_totals: Counter = Counter()
    for cc in counts.values():
        for cls, n in cc.items():
            class_totals[cls] += n
    grand_total = sum(class_totals.values()) or 1
    top_three = class_totals.most_common(3)
    if top_three:
        dom_cls, dom_n = top_three[0]
        dom_pct = 100.0 * dom_n / grand_total
        sub_bits = [f'{cls} {base.fmt_float(100.0 * n / grand_total, 1)}%'
                    for cls, n in top_three[1:]]
        sub_text = f'across {len(areas)} areas; next: ' + ', '.join(sub_bits) if sub_bits else f'across {len(areas)} areas'
        parts.append(base.summary_bar(
            'dominant class',
            f'{dom_cls} {base.fmt_float(dom_pct, 1)}%',
            sub=sub_text,
            tone='neutral',
        ))

    # Section 1: stacked share bars
    parts.append('<h2 id="stacked">stacked share per area / drop</h2>')
    sec1_body = ['<div class="table-wrap">', base.legend()]
    keys = sorted(counts.keys(), key=lambda k: (k[1], k[0]))
    for area, date in keys:
        cc = counts[(area, date)]
        total = sum(cc.values())
        label = f'{area} / {date}'
        sec1_body.append('<div class="bar-row">')
        sec1_body.append(f'<span class="key" title="{base.h(label)}">{base.h(label)}</span>')
        sec1_body.append(base.class_segments_bar(dict(cc), total))
        sec1_body.append(f'<span class="total">{base.fmt_int(total)}</span>')
        sec1_body.append('</div>')
    sec1_body.append('</div>')
    parts.append(''.join(sec1_body))

    # Section 2: raw counts table
    parts.append('<h2 id="counts">raw counts per class</h2>')
    parts.append('<div class="table-wrap"><rdc-sortable-table data-default-sort="opaque" data-default-dir="desc">')
    parts.append(_build_table(counts, drop_keys))
    parts.append('</rdc-sortable-table></div>')

    parts.append(base.page_close())

    out_path = base.output_path(root, 'draws_by_class', ab)
    return base.write_report(out_path, parts)


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='draws_by_class'))
