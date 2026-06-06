"""Trend table: per-area KPI matrices across drop_dates.

One sticky section card per KPI, rows = area, columns = drop_dates (+ delta cols + sparkline).
Plus per-area class-count matrix at the end.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import pyarrow.parquet as papq

from . import base
from ..config import get_config


# (col_name, label, fmt, lower_is_better, regression_pct)
KPIS = [
    ('total_gpu_duration_s',          'gpu (s)',           '{:+,.3f}', True,  10.0),
    ('n_draws',                        'draws',             '{:+,.0f}', True,  10.0),
    ('vbo_bytes_bound_derived',        'vbo bytes',         '{:+,.0f}', True,  15.0),
    ('ibo_bytes_bound_derived',        'ibo bytes',         '{:+,.0f}', True,  15.0),
    ('program_switches',               'prog switches',     '{:+,.0f}', True,  20.0),
]

_INT_KPIS = {'n_draws', 'vbo_bytes_bound_derived', 'ibo_bytes_bound_derived',
             'program_switches'}


def _aggregate_frame_totals(drop: base.DropSet, ok_caps: set) -> dict:
    """Return {area: {kpi: sum}} from frame_totals.parquet."""
    out: dict = defaultdict(lambda: defaultdict(float))
    for r in drop.rows:
        p = os.path.join(r.drop_dir, 'frame_totals.parquet')
        if not os.path.exists(p):
            continue
        try:
            t = papq.read_table(p)
        except Exception:
            continue
        cols = base._to_dict_of_lists(t)   # Q-7
        for i in range(t.num_rows):
            cap = cols['capture'][i]
            key = (r.area, r.drop_date, r.drop_label, cap)
            if ok_caps and key not in ok_caps:
                continue
            for kpi, *_ in KPIS:
                if kpi in cols:
                    v = cols[kpi][i]
                    if v is not None:
                        out[r.area][kpi] += v
    return out


def _aggregate_buffer_bytes(drop: base.DropSet, ok_caps: set) -> dict:
    """Return {area: {vbo_bytes_bound_derived, ibo_..., ubo_...}}.

    Buffer used_as_* flags are unpopulated (parser limitation).
    Derive via joins:
      vbo_bytes = sum allocated_size_bytes of distinct buffer_ids in vertex_inputs
      ibo_bytes = sum allocated_size_bytes of distinct ibo_ids in draws
      ubo_bytes = sum allocated_size_bytes of distinct resource_ids in
                  draw_bindings where slot_kind='ubo'
    """
    out: dict = defaultdict(lambda: defaultdict(int))

    for r in drop.rows:
        ao = r.drop_dir

        bufs_p = os.path.join(ao, 'buffers.parquet')
        if not os.path.exists(bufs_p):
            continue
        try:
            bt = papq.read_table(bufs_p,
                                  columns=['capture', 'buffer_id', 'allocated_size_bytes'])
        except Exception:
            continue
        bc = {n: bt.column(n).to_pylist() for n in bt.column_names}
        size_by: dict[tuple, int] = {}
        for i in range(bt.num_rows):
            size_by[(bc['capture'][i], bc['buffer_id'][i])] = bc['allocated_size_bytes'][i] or 0

        # vbo via vertex_inputs
        vi_p = os.path.join(ao, 'vertex_inputs.parquet')
        if os.path.exists(vi_p):
            try:
                vi = papq.read_table(vi_p, columns=['capture', 'buffer_id'])
            except Exception:
                vi = None
            if vi is not None:
                seen: set = set()
                vc = {n: vi.column(n).to_pylist() for n in vi.column_names}
                for i in range(vi.num_rows):
                    cap = vc['capture'][i]
                    bid = vc['buffer_id'][i]
                    if not bid:
                        continue
                    key = (r.area, r.drop_date, r.drop_label, cap)
                    if ok_caps and key not in ok_caps:
                        continue
                    pk = (r.area, cap, bid)
                    if pk in seen:
                        continue
                    seen.add(pk)
                    out[r.area]['vbo_bytes_bound_derived'] += size_by.get((cap, bid), 0)

        # ibo via draws.ibo_id
        draws_p = os.path.join(ao, 'draws.parquet')
        if os.path.exists(draws_p):
            try:
                schema_cols = set(papq.read_schema(draws_p).names)
                want = ['capture', 'ibo_id'] if 'ibo_id' in schema_cols else None
                if want:
                    dt = papq.read_table(draws_p, columns=want)
                else:
                    dt = None
            except Exception:
                dt = None
            if dt is not None:
                seen = set()
                dc = {n: dt.column(n).to_pylist() for n in dt.column_names}
                for i in range(dt.num_rows):
                    cap = dc['capture'][i]
                    ibo = dc['ibo_id'][i]
                    if not ibo:
                        continue
                    key = (r.area, r.drop_date, r.drop_label, cap)
                    if ok_caps and key not in ok_caps:
                        continue
                    pk = (r.area, cap, ibo)
                    if pk in seen:
                        continue
                    seen.add(pk)
                    out[r.area]['ibo_bytes_bound_derived'] += size_by.get((cap, ibo), 0)

        # ubo via draw_bindings where slot_kind='ubo'
        db_p = os.path.join(ao, 'draw_bindings.parquet')
        if os.path.exists(db_p):
            try:
                db = papq.read_table(db_p,
                                      columns=['capture', 'slot_kind', 'resource_id'])
            except Exception:
                db = None
            if db is not None:
                seen = set()
                dbc = {n: db.column(n).to_pylist() for n in db.column_names}
                for i in range(db.num_rows):
                    if dbc['slot_kind'][i] != 'ubo':
                        continue
                    cap = dbc['capture'][i]
                    rid = dbc['resource_id'][i]
                    if not rid:
                        continue
                    key = (r.area, r.drop_date, r.drop_label, cap)
                    if ok_caps and key not in ok_caps:
                        continue
                    pk = (r.area, cap, rid)
                    if pk in seen:
                        continue
                    seen.add(pk)
                    out[r.area]['ubo_bytes_bound_derived'] += size_by.get((cap, rid), 0)

    return out


def _aggregate_class_counts(drop: base.DropSet, ok_caps: set) -> dict:
    """Return {area: {draw_class: n_draws}}."""
    out: dict = defaultdict(lambda: defaultdict(int))
    for r in drop.rows:
        p = os.path.join(r.drop_dir, 'pass_class_breakdown.parquet')
        if not os.path.exists(p):
            continue
        try:
            t = papq.read_table(p, columns=['capture', 'draw_class', 'n_draws'])
        except Exception:
            continue
        c = {n: t.column(n).to_pylist() for n in t.column_names}
        for i in range(t.num_rows):
            cap = c['capture'][i]
            key = (r.area, r.drop_date, r.drop_label, cap)
            if ok_caps and key not in ok_caps:
                continue
            cls = c['draw_class'][i] or 'other'
            out[r.area][cls] += c['n_draws'][i] or 0
    return out


def _device_string(drop: base.DropSet) -> str:
    for r in drop.rows:
        p = os.path.join(r.drop_dir, 'frame_metadata.jsonl')
        if not os.path.exists(p):
            continue
        try:
            with open(p, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    s = o.get('gl_renderer_string') or o.get('gl_renderer') or ''
                    if s:
                        return s
        except OSError:
            continue
    return ''


def _kpi_matrix(kpi: str, label: str, fmt: str, lower_is_better, threshold,
                per_drop_area_data: list, areas: list, drops: list, lead: str = '') -> str:
    """Render one KPI matrix as a sticky section card: (flagship chart) + table-wrap.

    One per KPI, n_drops >= 2 (c16c: framed via section_card; the chart `lead` rides in the body)."""
    is_int = kpi in _INT_KPIS

    # v0.2.6-4: adopt the data_table component (ADR-43; golden absorbs the normalization). The last
    # delta column carries delta-latest on BOTH the th (header_class) and its tds (cell_class) -- the
    # trend matrix brackets the most-recent comparison down the whole column (was the .replace hack).
    n_drops = len(drops)
    cols = [base.Column('area', 'area', clip='default')]
    for i, d in enumerate(drops):
        cols.append(base.Column(f'v{i}', d.key, numeric=True))
        if i > 0:
            last = i == n_drops - 1
            cols.append(base.delta_column(f'd{i}', latest=last, latest_cell=last))
    if n_drops >= 3:
        cols.append(base.Column('trend', 'trend', numeric=True,
                                render=lambda value, row: base.sparkline_svg(value)))

    rows = []
    for area in areas:
        row = {'area': area}
        series: list = []
        prev = None
        for i, d in enumerate(drops):
            v = per_drop_area_data[i].get(area, {}).get(kpi)
            series.append(v)
            row[f'v{i}'] = base.fmt_int(v) if is_int else base.fmt_float(v, 3)
            if i > 0:
                row[f'd{i}'] = base.delta_parts(v, prev, lower_is_better=lower_is_better,
                                               fmt=fmt, regression_threshold_pct=threshold)
            prev = v
        if n_drops >= 3:
            row['trend'] = series
        rows.append(row)

    body = [lead] if lead else []
    body.append(str(base.data_table(cols, rows, table_key=f'trend_{kpi}',
                                    caption=f'{label} per area across drops')))
    return ('<rdc-sticky-h2>'
            + base.section_card(kpi, label, '\n'.join(body))
            + '</rdc-sticky-h2>')


def _single_drop_matrix(per_drop_ft: list, areas: list, drops: list) -> str:
    """Render single wide matrix (rows=area, cols=KPI) when n_drops==1. v0.2.6-4: data_table component."""
    data = per_drop_ft[0]
    col_max: dict = {}   # per-column max for heatmap normalization
    for kpi, _, _, _, _ in KPIS:
        vals = [float(data.get(a, {}).get(kpi) or 0) for a in areas]
        col_max[kpi] = max(vals) if vals else 0.0

    cols = [base.Column('area', 'area', clip='default')]
    cols += [base.Column(kpi, label, numeric=True, render=lambda value, row: value)
             for kpi, label, *_ in KPIS]   # value = the prebuilt heatmap-or-plain inner

    rows = []
    for area in areas:
        row = {'area': area}
        for kpi, _, _, _, _ in KPIS:
            v = data.get(area, {}).get(kpi)
            val_str = base.fmt_int(v) if kpi in _INT_KPIS else base.fmt_float(v, 3)
            row[kpi] = (base.heatmap_cell(v, 0, col_max[kpi], text=val_str)
                        if (v is not None and col_max[kpi] > 0) else val_str)
        rows.append(row)
    table = base.data_table(cols, rows, table_key='trend_matrix',
                            caption='per-area KPI matrix for the single drop')
    return ('<rdc-sticky-h2>'
            + base.section_card('matrix', 'per-area kpi matrix', str(table))
            + '</rdc-sticky-h2>')


def _class_count_matrix(per_drop_area_class: list, areas: list,
                        drops: list) -> str:
    # v0.2.6-4: data_table component. Per (drop, class) column; single-drop drops the drop prefix.
    single = len(drops) == 1
    cols = [base.Column('area', 'area', clip='default')]
    for i, d in enumerate(drops):
        for cls in base.DRAW_CLASSES:
            cols.append(base.Column(f'd{i}_{cls}', cls if single else f'{d.key}/{cls}', numeric=True))
    rows = []
    for area in areas:
        row = {'area': area}
        for i in range(len(drops)):
            cc = per_drop_area_class[i].get(area, {})
            for cls in base.DRAW_CLASSES:
                row[f'd{i}_{cls}'] = base.fmt_int(cc.get(cls, 0))
        rows.append(row)
    table = base.data_table(cols, rows, table_key='trend_class_counts',
                            caption='draw counts by class per area')
    return ('<rdc-sticky-h2>'
            + base.section_card('class_counts', 'draws by class', str(table))
            + '</rdc-sticky-h2>')


def build(root: str, *, drops: list | None = None, ab=None,
          sink: base.AssetSink = base.AssetSink.INLINE,
          build_ts: str | None = None, redact: bool = False, theme: dict | None = None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    if not drops:
        out_path = base.output_path(root, 'trend_table', ab)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(base.page_open('trend table', sink=sink, depth=base.crumb_depth(ab), theme=theme))
            f.write(base.header('trend table', drops=0, captures=0,
                                build_ts=build_ts or base.now_iso()))
            f.write(base.empty_state('no drops found in catalog'))
            f.write(base.page_close())
        base._lint_or_raise(out_path)
        return out_path

    ok_caps = base.ok_capture_set(root)

    per_drop_ft = []
    per_drop_bytes = []
    per_drop_class = []
    device_strings = []
    for d in drops:
        ft = _aggregate_frame_totals(d, ok_caps)
        bb = _aggregate_buffer_bytes(d, ok_caps)
        for area in list(ft.keys()) + list(bb.keys()):
            ft.setdefault(area, {})
            ft[area].update(bb.get(area, {}))
        per_drop_ft.append(ft)
        per_drop_bytes.append(bb)
        per_drop_class.append(_aggregate_class_counts(d, ok_caps))
        device_strings.append(_device_string(d))

    all_areas = sorted({a for d in per_drop_ft for a in d.keys()})
    drop_keys_l = [d.key for d in drops]

    rcfg = get_config().report

    # Hero KPIs: latest total GPU, delta vs previous drop, regression count.
    def _sum_gpu(ft):
        return sum(float(ft.get(a, {}).get('total_gpu_duration_s', 0) or 0) for a in all_areas)
    latest_gpu = _sum_gpu(per_drop_ft[-1])
    kpis = [
        {'label': 'latest gpu (s)', 'value': base.fmt_float(latest_gpu, 3)},
        {'label': 'areas',          'value': base.fmt_int(len(all_areas))},
    ]
    if len(drops) > 1:
        d_gpu = latest_gpu - _sum_gpu(per_drop_ft[-2])
        n_reg = 0
        for _kpi, _lbl, *_ in KPIS:
            for a in all_areas:
                cur = per_drop_ft[-1].get(a, {}).get(_kpi)
                prv = per_drop_ft[-2].get(a, {}).get(_kpi)
                if (cur is not None and prv not in (None, 0) and float(prv) > 0
                        and 100.0 * (float(cur) - float(prv)) / float(prv) >= rcfg.gpu_regression_pct):
                    n_reg += 1
        # Explicit sign so the regression direction is not conveyed by tone colour alone (c16c a11y).
        kpis.insert(1, {'label': 'gpu delta (s)', 'value': f'{d_gpu:+,.3f}',
                        'tone': 'neg' if d_gpu > 0 else ('pos' if d_gpu < 0 else 'neutral')})
        kpis.append({'label': 'regressions', 'value': base.fmt_int(n_reg)})

    body_attrs = {'data-multi-section': 'true'} if len(drops) > 1 else None
    # trend_table's A/B strip is bespoke (capture-count suffixes, only when ab) so it rides at the
    # head of the body rather than through report_page's standard report_key strip (Q-6).
    parts = []
    if ab is not None:
        baseline, compare = ab
        parts.append(base.ab_strip(
            ab,
            baseline_suffix=f' ({baseline.n_captures} captures)',
            compare_suffix=f' ({compare.n_captures} captures)',
        ))
    parts.append(base.ab_picker_for(root, 'trend_table', ab=ab))

    # Summary bar: worst KPI (n=1) or biggest regression (n>1)
    if len(drops) == 1:
        ft = per_drop_ft[0]
        worst_area, worst_gpu = None, 0.0
        for area, ft_row in ft.items():     # not `kpis` - that name holds the hero KPI list (used below)
            g = float(ft_row.get('total_gpu_duration_s', 0) or 0)
            if g > worst_gpu:
                worst_gpu, worst_area = g, area
        if worst_area is not None:
            parts.append(base.summary_bar(
                'worst gpu area',
                worst_area,
                sub=f'rank 1 of {len(all_areas)} areas',
                tone='neutral',
            ))
    else:
        worst_pct = 0.0
        worst_tuple = None
        for kpi, label, *_rest in KPIS:
            for area in all_areas:
                prev = None
                for di, drop in enumerate(drops):
                    cur = per_drop_ft[di].get(area, {}).get(kpi)
                    if cur is None:
                        continue
                    if prev is not None and prev > 0:
                        pct = 100.0 * (float(cur) - float(prev)) / float(prev)
                        if pct > worst_pct:
                            worst_pct = pct
                            worst_tuple = (kpi, area, label, pct, drops[di-1].key, drop.key)
                    prev = cur
        if worst_tuple is not None:
            kpi, area, label, pct, prev_key, cur_key = worst_tuple
            tone = 'alarm' if pct >= rcfg.gpu_regression_pct else 'warn'
            parts.append(base.summary_bar(
                'biggest regression',
                f'{area} / {label} +{base.fmt_float(pct, 1)}%',
                sub=f'{prev_key} to {cur_key}',
                tone=tone,
            ))
            # Insight: the largest cross-drop increase is the regression to chase first.
            parts.append(base.callout(
                tone,
                f'{area} / {label} regressed +{base.fmt_float(pct, 1)}%',
                f'{prev_key} to {cur_key} - investigate the change between these drops.',
                href=f'#{base.h(kpi)}', link_text='see trend'))

    if any(device_strings):
        if redact:
            # c16u: the per-drop gl-renderer chips are device info -> scrub at the data seam (ADR-40).
            parts.append('<div class="device-strip">redacted</div>')
        else:
            chips = []
            for d, dev in zip(drops, device_strings):
                chips.append(f'{base.h(d.key)}: {base.safe_chrome_text(dev) or "no metadata"}')
            parts.append(f'<div class="device-strip">{" | ".join(chips)}</div>')

    if len(drops) == 1:
        parts.append(_single_drop_matrix(per_drop_ft, all_areas, drops))
    else:
        parts.append('<nav class="toc">')
        for kpi, label, *_ in KPIS:
            parts.append(f'<a href="#{base.h(kpi)}" data-link-kind="crumb">{base.h(label)}</a>')
        parts.append('<a href="#class_counts" data-link-kind="crumb">draws by class</a>')
        parts.append('</nav>')
        for kpi, label, fmt, lib, thr in KPIS:
            # Flagship: per-area line of this KPI across drops, leading the matrix (c16b).
            series = []
            for area in all_areas:
                vals = [per_drop_ft[i].get(area, {}).get(kpi) for i in range(len(drops))]
                series.append((area, [None if v is None else float(v) for v in vals], None))
            lead = base.figure(
                base.line_chart(series, x_labels=drop_keys_l, title=f'{label} trend',
                                desc=f'{label} per area across {len(drops)} drops'),
                f'{label}: trend across drops')
            parts.append(_kpi_matrix(kpi, label, fmt, lib, thr,
                                      per_drop_ft, all_areas, drops, lead=lead))

    parts.append(_class_count_matrix(per_drop_class, all_areas, drops))

    out_path = base.output_path(root, 'trend_table', ab)
    return base.write_report(out_path, [base.report_page(
        'trend table', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=build_ts or base.now_iso(), crumb_depth=base.crumb_depth(ab),
        body_attrs=body_attrs, kpis=kpis, sink=sink, theme=theme,
        device=base.provenance_strip(*base.newest_drop_provenance(root, drops), redact=redact))])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='trend_table'))
