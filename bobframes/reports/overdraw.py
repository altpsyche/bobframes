"""Per-RT pixel_history aggregation. Color bar of rejection causes.

Aggregation key: (area, rt_label). Falls back to (area, rt_id) when label empty.
Gracefully renders 'no data' when pixel_history absent for a drop.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

import pyarrow.parquet as papq

from . import base


_PH_COLS = ['area', 'drop_date', 'drop_label', 'capture', 'rt_id',
            'passed', 'backface_culled', 'depth_test_failed',
            'stencil_test_failed', 'scissor_clipped', 'shader_discarded']

_RT_COLS = ['area', 'drop_date', 'drop_label', 'capture',
            'rt_id', 'format', 'width', 'height', 'label',
            'is_swap_chain_target']


def _read_rts(drop: base.DropSet) -> dict:
    """{(area, capture, rt_id): {label, format, width, height, is_swap}}"""
    out: dict = {}
    for r in drop.rows:
        p = os.path.join(r.drop_dir, 'render_targets.parquet')
        if not os.path.exists(p):
            continue
        try:
            schema_cols = set(papq.read_schema(p).names)
            want = [c for c in _RT_COLS if c in schema_cols]
            t = papq.read_table(p, columns=want)
        except Exception:
            continue
        cols = {c: t.column(c).to_pylist() for c in t.column_names}
        for i in range(t.num_rows):
            key = (cols.get('area', [''])[i] if 'area' in cols else r.area,
                   cols['capture'][i],
                   cols['rt_id'][i])
            out[key] = {
                'label': cols.get('label', [''])[i] if 'label' in cols else '',
                'format': cols.get('format', [''])[i] if 'format' in cols else '',
                'width': cols.get('width', [0])[i] if 'width' in cols else 0,
                'height': cols.get('height', [0])[i] if 'height' in cols else 0,
                'is_swap': cols.get('is_swap_chain_target', [False])[i] if 'is_swap_chain_target' in cols else False,
            }
    return out


def _agg_pixel_history(drop: base.DropSet, rt_meta: dict) -> dict:
    """{(area, group_key): {n_samples, n_passed, n_depth_failed, ...,
                            'format', 'width', 'height', 'is_swap'}}."""
    out: dict = defaultdict(lambda: {
        'n_samples': 0, 'n_passed': 0, 'n_depth_failed': 0,
        'n_discarded': 0, 'n_scissor': 0, 'n_backface': 0, 'n_stencil': 0,
        'format': '', 'width': 0, 'height': 0, 'is_swap': False,
        'rt_id': 0,
    })
    any_data = False
    for r in drop.rows:
        p = os.path.join(r.drop_dir, 'pixel_history.parquet')
        if not os.path.exists(p):
            continue
        try:
            schema_cols = set(papq.read_schema(p).names)
            want = [c for c in _PH_COLS if c in schema_cols]
            t = papq.read_table(p, columns=want)
        except Exception:
            continue
        if t.num_rows == 0:
            continue
        any_data = True
        cols = {c: t.column(c).to_pylist() for c in t.column_names}
        for i in range(t.num_rows):
            cap = cols.get('capture', [''])[i] if 'capture' in cols else ''
            rt_id = cols.get('rt_id', [0])[i] if 'rt_id' in cols else 0
            meta = rt_meta.get((r.area, cap, rt_id), {})
            label = meta.get('label') or f'rt_{rt_id}'
            key = (r.area, label)
            bucket = out[key]
            bucket['n_samples'] += 1
            bucket['rt_id'] = rt_id
            if cols.get('passed', [False])[i]:
                bucket['n_passed'] += 1
            if cols.get('depth_test_failed', [False])[i]:
                bucket['n_depth_failed'] += 1
            if cols.get('shader_discarded', [False])[i]:
                bucket['n_discarded'] += 1
            if cols.get('scissor_clipped', [False])[i]:
                bucket['n_scissor'] += 1
            if cols.get('backface_culled', [False])[i]:
                bucket['n_backface'] += 1
            if cols.get('stencil_test_failed', [False])[i]:
                bucket['n_stencil'] += 1
            if not bucket['format'] and meta:
                bucket['format'] = meta.get('format', '')
                bucket['width'] = meta.get('width', 0)
                bucket['height'] = meta.get('height', 0)
                bucket['is_swap'] = meta.get('is_swap', False)
    return dict(out) if any_data else {}


def _rejection_bar(b: dict) -> str:
    n = b['n_samples']
    if n <= 0:
        return ''
    weights = {
        'opaque':       b['n_passed'],
        'prepass':      b['n_depth_failed'],
        'ui':           b['n_discarded'],
        'other':        b['n_scissor'],
        'shadow':       b['n_backface'],
        'translucent':  b['n_stencil'],
    }
    accounted = sum(weights.values())
    remainder = n - accounted
    if remainder > 0:
        weights['additive'] = remainder
    return base.class_segments_bar(weights, n)


def build(root: str, *, drops: list | None = None, ab=None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    out_path = base.output_path(root, 'overdraw', ab)

    drop_keys = [d.key for d in drops]
    per_drop_data: dict = {}
    for d in drops:
        meta = _read_rts(d)
        per_drop_data[d.key] = _agg_pixel_history(d, meta)

    all_keys: set = set()
    for agg in per_drop_data.values():
        all_keys.update(agg.keys())

    by_area: dict = defaultdict(list)
    for area, label in all_keys:
        by_area[area].append(label)

    parts = []

    # Summary bar: worst shadow RT rejection % (or worst RT rejection if no shadow)
    worst_rt = None
    worst_pct = -1.0
    for area_key, label in all_keys:
        # Pick the rep bucket (first seen across drops)
        rep = None
        for k in drop_keys:
            b = per_drop_data.get(k, {}).get((area_key, label))
            if b is not None:
                rep = b
                break
        if not rep:
            continue
        ns = rep.get('n_samples', 0)
        if ns <= 0:
            continue
        passed = rep.get('n_passed', 0)
        reject_pct = 100.0 * (1.0 - passed / ns)
        label_str = str(label or '').lower()
        is_shadow = 'shadow' in label_str
        # Prefer shadow RTs; fall back to highest reject overall
        score = reject_pct + (10000.0 if is_shadow else 0.0)
        if score > worst_pct:
            worst_pct = score
            worst_rt = (area_key, label or '?', reject_pct, is_shadow)
    if worst_rt is not None:
        area_w, label_w, pct_w, is_shadow_w = worst_rt
        kind = 'shadow rejection' if is_shadow_w else 'rt rejection'
        tone = 'alarm' if pct_w >= 70 else ('warn' if pct_w >= 40 else 'neutral')
        parts.append(base.summary_bar(
            f'worst {kind}',
            f'{area_w} / {label_w}',
            sub=f'{base.fmt_float(pct_w, 1)}% rejected',
            link_href=f'#{base.h(area_w)}',
            link_text='area',
            tone=tone,
        ))

    parts.append('<div class="legend">')
    for cls, name in [('opaque', 'passed'), ('prepass', 'depth failed'),
                       ('ui', 'discarded'), ('other', 'scissor'),
                       ('shadow', 'backface'), ('translucent', 'stencil'),
                       ('additive', 'other')]:
        parts.append(f'<span class="chip"><span class="swatch" '
                     f'style="background: {base.class_color_var(cls)}"></span>{base.h(name)}</span>')
    parts.append('</div>')

    drops_without_data = [k for k in drop_keys if not per_drop_data.get(k)]
    if drops_without_data:
        msg = ', '.join(base.h(k) for k in drops_without_data)
        parts.append(f'<p class="note">no pixel_history rows in drops: {msg}</p>')

    if not by_area:
        parts.append('<p class="note">no pixel_history data across all drops</p>')
    else:
        for area in sorted(by_area.keys()):
            rows = []
            for label in set(by_area[area]):
                rep = None
                for k in drop_keys:
                    b = per_drop_data.get(k, {}).get((area, label))
                    if b is not None:
                        rep = b
                        break
                max_samples = max((per_drop_data.get(k, {}).get((area, label), {}).get('n_samples', 0)
                                    for k in drop_keys), default=0)
                rows.append((label, rep, max_samples))
            rows.sort(key=lambda x: x[2], reverse=True)

            sec = []
            sec.append('<table class="report"><thead><tr>')
            sec.append('<th>rt label</th>')
            sec.append('<th>format</th>')
            sec.append('<th>dims</th>')
            sec.append('<th class="num">samples (latest)</th>')
            sec.append('<th class="num">passed</th>')
            sec.append('<th class="num">depth failed</th>')
            sec.append('<th class="num">discarded</th>')
            sec.append('<th class="num">scissor</th>')
            sec.append('<th class="num">backface</th>')
            sec.append('<th>rejection bar</th>')
            for i, k in enumerate(drop_keys):
                sec.append(f'<th class="num">samples@{base.h(k)}</th>')
                if i > 0:
                    latest_cls = ' delta-latest' if i == len(drop_keys) - 1 else ''
                    sec.append(f'<th class="num{latest_cls}">delta</th>')
            sec.append('</tr></thead><tbody>')

            for label, rep, _ in rows:
                latest_bucket = None
                for k in reversed(drop_keys):
                    b = per_drop_data.get(k, {}).get((area, label))
                    if b is not None:
                        latest_bucket = b
                        break
                if latest_bucket is None:
                    continue
                n = latest_bucket['n_samples']
                pct = lambda v, total=n: (v / total * 100.0) if total > 0 else 0.0
                swap = ' (swap)' if latest_bucket.get('is_swap') else ''
                dims = f'{latest_bucket["width"]}x{latest_bucket["height"]}' if latest_bucket['width'] else ''

                sec.append('<tr>')
                sec.append(f'<td>{base.h(label)}{base.h(swap)}</td>')
                sec.append(f'<td>{base.h(latest_bucket.get("format") or "")}</td>')
                sec.append(f'<td class="num">{base.h(dims)}</td>')
                sec.append(f'<td class="num">{base.fmt_int(n)}</td>')
                sec.append(f'<td class="num">{base.fmt_pct(pct(latest_bucket["n_passed"]))}</td>')
                sec.append(f'<td class="num">{base.fmt_pct(pct(latest_bucket["n_depth_failed"]))}</td>')
                sec.append(f'<td class="num">{base.fmt_pct(pct(latest_bucket["n_discarded"]))}</td>')
                sec.append(f'<td class="num">{base.fmt_pct(pct(latest_bucket["n_scissor"]))}</td>')
                sec.append(f'<td class="num">{base.fmt_pct(pct(latest_bucket["n_backface"]))}</td>')
                sec.append(f'<td>{_rejection_bar(latest_bucket)}</td>')

                prev_n = None
                for i, k in enumerate(drop_keys):
                    bb = per_drop_data.get(k, {}).get((area, label))
                    cur = bb['n_samples'] if bb else None
                    sec.append(f'<td class="num">{base.fmt_int(cur) if cur is not None else ""}</td>')
                    if i > 0:
                        sec.append(base.delta_cell(
                            cur if cur is not None else 0,
                            prev_n,
                            lower_is_better=None, fmt='{:+,.0f}'))
                    prev_n = cur
                sec.append('</tr>')
            sec.append('</tbody></table>')
            parts.append(f'<h2 id="{base.h(area)}">{base.h(area)}</h2>')
            parts.append(f'<div class="table-wrap"><rdc-sortable-table>{"".join(sec)}</rdc-sortable-table></div>')

    return base.write_report(out_path, [base.report_page(
        'overdraw', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(), crumb_depth=base.crumb_depth(ab),
        ab=ab, root=root, report_key='overdraw')])


if __name__ == '__main__':
    sys.exit(base.run_report(build, module_name='overdraw'))
