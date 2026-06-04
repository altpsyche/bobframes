"""Build-health one-pager - the exec / non-technical read (c16q, ADR-39).

A print-first single page that leads with a deterministic OK/AT_RISK/ALARM/UNKNOWN verdict, then four
averaged headline KPIs, what moved since the prior run, and a per-area table. The verdict + trajectory
LOGIC lives in `bobframes/health.py` (a presentation-independent contract c20 `--json` + c21
`report --gate` reuse); this module only ASSEMBLES the inputs and RENDERS them.

Pure composition of existing primitives (ADR-37): static, server-baked, JS-optional, printable,
Ctrl-F-able, offline + byte-deterministic. The human verdict labels live here, never in health.py.
"""

from __future__ import annotations

from . import base
from . import dashboard as _dash
from .. import health
from ..config import get_config
from ..health import Direction, State

# Presentation only: the contract key is `State`/`Direction`; these banlist-clean labels never leak
# into health.py (the lint banlist governs presentation copy, not the wire identifiers).
_STATE_LABEL = {
    State.OK: 'Healthy',
    State.AT_RISK: 'Needs attention',
    State.ALARM: 'Action needed',
    State.UNKNOWN: 'Unknown',
}
_STATE_TONE = {
    State.OK: 'ok',
    State.AT_RISK: 'warn',
    State.ALARM: 'alarm',
    State.UNKNOWN: 'neutral',
}
_DIRECTION_LABEL = {
    Direction.IMPROVING: 'improving',
    Direction.MIXED: 'mixed',
    Direction.REGRESSING: 'regressing',
    Direction.UNKNOWN: 'unknown',
}
_DIRECTION_TONE = {
    Direction.IMPROVING: 'ok',
    Direction.MIXED: 'info',
    Direction.REGRESSING: 'warn',
    Direction.UNKNOWN: 'neutral',
}
# health.Change.metric -> banlist-clean display label.
_METRIC_LABEL = {
    'draws': 'draw calls',
    'gpu': 'gpu cost',
    'overdraw': 'worst overdraw',
    'shader': 'worst shader',
}


def _pct_pill(cur, prev, *, lower_is_better: bool = True) -> str:
    """A colored vs-prior PERCENT pill reusing the `.delta-pill pos/neg` classes.

    `delta.delta_pill` renders the ABSOLUTE diff; the one-pager wants the per-frame PERCENT so the
    "reducing vs rising" read is glanceable. ASCII sign only. Falls back to the primitive for the
    new/flat edge cases (no prior, equal)."""
    if cur is None or prev in (None, 0):
        return base.delta_pill(cur, prev, lower_is_better=lower_is_better)
    pct = (float(cur) - float(prev)) / float(prev) * 100.0
    if abs(pct) < 0.5:
        return '<span class="delta-pill flat">0%</span>'
    cls = 'pos' if (pct < 0) == lower_is_better else 'neg'
    return f'<span class="delta-pill {cls}">{pct:+.0f}%</span>'


def _collect_metrics(root: str, run, baseline) -> health.HealthMetrics:
    """Assemble one run's per-area `AreaMetrics` by REUSING the dashboard current-run helpers (no new
    aggregation - the `aggregates.py` extraction is deferred to the 3rd consumer, G-26). Kept as ONE
    function so that extraction (which c20/c21 need so the data layer never imports presentation) is a
    clean lift. `baseline` (a DropSet or None) supplies ONLY the per-area gpu-regression denominator;
    its absence -> gpu_regression_pct=None -> the verdict treats the trajectory as unknown, not OK.
    """
    has_baseline = baseline is not None
    if run is None:
        return health.HealthMetrics(per_area={}, has_baseline=has_baseline)
    areas_gpu = {a: (gpu, draws, adf, agf)
                 for (a, gpu, draws, adf, agf) in _dash._top_areas_gpu([run], 999)}
    base_gpu = {}
    if has_baseline:
        base_gpu = {a: agf for (a, _g, _d, _adf, agf) in _dash._top_areas_gpu([baseline], 999)}
    overdraw: dict = {}
    for (a, _rt, reject, _ns) in _dash._worst_overdraw([run], 999):
        overdraw[a] = max(overdraw.get(a, 0.0), reject)
    shader: dict = {}
    for (a, _lbl, cplx, _cost) in _dash._top_shaders_by_area(root, run, 999):
        shader[a] = max(shader.get(a, 0.0), cplx)
    mesh: dict = {}
    for (a, _lbl, repeat, _med) in _dash._top_meshes_by_area(root, run, 999):
        mesh[a] = max(mesh.get(a, 0), repeat)
    per_area: dict = {}
    for a, (_gpu, _draws, adf, agf) in areas_gpu.items():
        gpu_reg = None
        if has_baseline and base_gpu.get(a):
            gpu_reg = (agf - base_gpu[a]) / base_gpu[a] * 100.0
        per_area[a] = health.AreaMetrics(
            overdraw_pct=overdraw.get(a),
            gpu_regression_pct=gpu_reg,
            shader_cplx=shader.get(a),
            mesh_repeat=mesh.get(a),
            avg_draws_per_frame=adf,
            avg_gpu_per_frame=agf,
        )
    return health.HealthMetrics(per_area=per_area, has_baseline=has_baseline)


def _per_run_series(root: str, rc) -> dict:
    """Per-run (chronological) series for the four headline metrics, for the micro sparklines. A run
    with no data for a metric contributes None (sparkline renders a break)."""
    draws: list = []
    gpu: list = []
    overd: list = []
    shad: list = []
    for d in rc.drops:
        tg, td, nf = _dash._run_totals([d])
        draws.append((td / nf) if nf else None)
        gpu.append((tg / nf) if nf else None)
        overd.append(max((r[2] for r in _dash._worst_overdraw([d], 999)), default=None))
        shad.append(max((r[2] for r in _dash._top_shaders_by_area(root, d, 999)), default=None))
    return {'draws': draws, 'gpu': gpu, 'overdraw': overd, 'shader': shad}


# Summary-SCOPED styling (keyed on body[data-page-kind="summary"]) so only summary.html changes - the
# shared chrome CSS bundle (inlined on every page pre-c16r) stays byte-identical for the other goldens.
# Lint skips <style> bodies; ASCII; deterministic. Restyles the KPI trend strip (a proper area
# sparkline on its own row, not a scratch line crammed beside the delta) + the Movement two-column
# layout + the change lists.
_SUMMARY_CSS = (
    '<style>'
    '[data-page-kind="summary"] .kpi-strip{gap:var(--sp-4);margin-bottom:var(--sp-6)}'
    '[data-page-kind="summary"] .kpi-chip{padding:var(--sp-4) var(--sp-6) var(--sp-6);'
    'gap:var(--sp-1)}'
    '[data-page-kind="summary"] .kpi-chip .kpi-delta{min-height:1.2em;display:flex;'
    'align-items:baseline;gap:var(--sp-2)}'
    '[data-page-kind="summary"] .kpi-chip .kpi-note{margin-top:1px}'
    '[data-page-kind="summary"] .bh-trend{width:100%;height:auto;display:block;'
    'margin-top:var(--sp-4);color:var(--text-3)}'
    '[data-page-kind="summary"] .bh-trend.tone-pos{color:var(--pos)}'
    '[data-page-kind="summary"] .bh-trend.tone-neg{color:var(--neg)}'
    '[data-page-kind="summary"] .bh-line{fill:none;stroke:currentColor;stroke-width:1.6;'
    'stroke-linejoin:round;stroke-linecap:round}'
    '[data-page-kind="summary"] .bh-fill{fill:currentColor;opacity:.12;stroke:none}'
    '[data-page-kind="summary"] .bh-dot{fill:currentColor}'
    '[data-page-kind="summary"] .movement{display:grid;grid-template-columns:1fr 1fr;'
    'gap:var(--sp-4) var(--sp-8)}'
    '[data-page-kind="summary"] .mv-col h3{margin:0 0 var(--sp-2);'
    'font:600 var(--fs-small) ui-monospace,monospace;text-transform:lowercase;'
    'letter-spacing:.04em;color:var(--text-3)}'
    '[data-page-kind="summary"] .mv-rollup{grid-column:1 / -1;margin-top:0}'
    '[data-page-kind="summary"] .change-list{list-style:none;margin:0;padding:0;'
    'display:flex;flex-direction:column;gap:var(--sp-2)}'
    '[data-page-kind="summary"] .change-list li{display:flex;align-items:baseline;'
    'gap:var(--sp-2)}'
    '[data-page-kind="summary"] .change-list li .delta-pill{margin-left:auto}'
    '[data-page-kind="summary"] .bh-status{font-weight:600}'
    '[data-page-kind="summary"] .bh-status.s-ALARM{color:var(--status-alarm)}'
    '[data-page-kind="summary"] .bh-status.s-AT_RISK{color:var(--status-warn)}'
    '[data-page-kind="summary"] .bh-status.s-OK{color:var(--status-ok)}'
    '[data-page-kind="summary"] .bh-status.s-UNKNOWN{color:var(--text-3)}'
    '</style>'
)


def _dir_tone(cur, prev) -> str:
    """Lower-is-better direction of a metric -> trend color: pos (improved), neg (worse), neutral."""
    if cur is None or prev in (None, 0):
        return 'neutral'
    if cur < prev:
        return 'pos'
    if cur > prev:
        return 'neg'
    return 'neutral'


def _trendline(values: list, *, tone: str = 'neutral', w: int = 240, h: int = 40,
               pad_x: int = 6, pad_y: int = 9) -> str:
    """A small filled area sparkline (deterministic inline SVG): polygon fill + polyline + an endpoint
    dot, uniformly scaled to the chip width (viewBox + width:100%, height:auto - no distortion). The
    generous `pad_y` keeps the line + dot floating clear of the strip's top/bottom edges (so the dot
    never hugs the card corner). Reads as a real trend strip even at 2 points, where the shared
    `delta.sparkline_svg` scratch-line did not. None values are dropped (present points plotted in
    order). '' for < 2 points (1-run)."""
    pts = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if len(pts) < 2:
        return ''
    n = len(values)
    ys = [v for _, v in pts]
    lo, hi = min(ys), max(ys)
    flat = hi == lo
    span = (hi - lo) or 1.0
    span_x = (n - 1) or 1

    def fx(i):
        return pad_x + (i / span_x) * (w - 2 * pad_x)

    def fy(v):
        if flat:                      # no movement -> a centered flat line, not one hugging the floor
            return h / 2
        return h - pad_y - ((v - lo) / span) * (h - 2 * pad_y)

    line = [(fx(i), fy(v)) for i, v in pts]
    poly = ' '.join(f'{x:.2f},{y:.2f}' for x, y in line)
    base_y = h - pad_y
    area = f'{line[0][0]:.2f},{base_y:.2f} {poly} {line[-1][0]:.2f},{base_y:.2f}'
    ex, ey = line[-1]
    return (f'<svg class="bh-trend tone-{tone}" viewBox="0 0 {w} {h}" role="img" aria-label="trend">'
            f'<polygon class="bh-fill" points="{area}"/>'
            f'<polyline class="bh-line" points="{poly}"/>'
            f'<circle class="bh-dot" cx="{ex:.2f}" cy="{ey:.2f}" r="2.5"/></svg>')


def _kpi(label: str, value, *, delta_html: str = '', trend: str = '',
         note: str = '', tone: str = 'neutral') -> str:
    """One headline KPI chip: label + big value + a colored vs-prior delta + scale note, then the
    trend strip on its own full-width row at the chip bottom (the chip's own padding gives it room -
    no extra panel). `chrome.kpi_chip` escapes its delta, so the one-pager builds the chip itself,
    reusing the styled `.kpi-*` classes + the summary-scoped rules. `trend` is '' on a 1-run page."""
    return (f'<div class="kpi-chip tone-{base.h(tone)}">'
            f'<div class="kpi-label">{base.h(label)}</div>'
            f'<div class="kpi-value">{base.h(value)}</div>'
            f'<div class="kpi-delta">{delta_html}</div>'
            f'<div class="kpi-note dim">{base.h(note)}</div>'
            f'{trend}'
            f'</div>')


def _change_line(c) -> str:
    lbl = _METRIC_LABEL.get(c.metric, c.metric)
    if c.delta_pct is None:
        pill = f'<span class="delta-pill flat">{base.h(c.kind)}</span>'
    else:
        cls = 'pos' if c.delta_pct < 0 else 'neg'
        pill = f'<span class="delta-pill {cls}">{c.delta_pct:+.0f}%</span>'
    return f'<li>{base.h(lbl)} {base.h(c.area or "")} {pill}</li>'


def _change_list(changes: list, empty: str) -> str:
    if not changes:
        return f'<p class="note dim">{base.h(empty)}</p>'
    return '<ul class="change-list">' + ''.join(_change_line(c) for c in changes[:3]) + '</ul>'


def build(root: str, *, drops: list | None = None, ab=None,
          run_label=None, run_date=None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    # Run model (ADR-35): ONE current run, never a cumulative sum (the G-19 flaw). baseline = the
    # immediately-prior run (None when current is the oldest -> per-run pages get per-run truth).
    rc = base.run_context(drops, run_label=run_label, run_date=run_date)
    cur, bl = rc.current, rc.baseline
    cur_drops = [cur] if cur else []
    out_path = base.output_path(root, 'summary', ab, run=rc)
    rcfg = get_config().report

    cur_hm = _collect_metrics(root, cur, bl)
    bl_hm = _collect_metrics(root, bl, None) if bl else None
    v = health.verdict(cur_hm, rcfg)
    tr = health.trend(cur_hm, bl_hm)
    series = _per_run_series(root, rc)

    parts: list = []

    if not cur_hm.per_area:
        parts.append(base.empty_state('no rendered run data yet'))
        return base.write_report(out_path, [base.report_page(
            'build health summary', parts,
            drops=len(drops), captures=sum(d.n_captures for d in drops),
            build_ts=base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
            current_page='summary', body_attrs={'data-page-kind': 'summary'},
            ab=ab, root=root, report_key='summary', run=rc, run_nav_key='summary',
            device=base.provenance_strip(*base.newest_drop_provenance(root, cur_drops)))])

    parts.append(_SUMMARY_CSS)

    # --- verdict bar + scope + direction ------------------------------------------------------
    n_areas = len(v.area_verdicts)
    n_attention = sum(1 for s in v.area_verdicts.values() if s in (State.AT_RISK, State.ALARM))
    n_unknown = sum(1 for s in v.area_verdicts.values() if s == State.UNKNOWN)
    areas_w = 'area' if n_areas == 1 else 'areas'
    if n_attention:
        verb = 'needs' if n_attention == 1 else 'need'
        scope = f'{n_attention} of {n_areas} {areas_w} {verb} attention - {v.worst_area}'
    elif v.state == State.UNKNOWN:
        scope = f'{n_unknown} of {n_areas} {areas_w} could not be assessed'
    else:
        scope = f'{n_areas} of {n_areas} {areas_w} healthy'
    parts.append(base.summary_bar('build health', _STATE_LABEL[v.state], sub=scope,
                                  tone=_STATE_TONE[v.state],
                                  link_href='index.html', link_text='dashboard'))
    dir_detail = f'since run {bl.key}' if bl else 'no baseline run yet'
    parts.append(base.callout(_DIRECTION_TONE[tr.direction],
                              f'Direction: {_DIRECTION_LABEL[tr.direction]}', dir_detail))

    # --- four headline KPIs as AVERAGES (reconcile with the dashboard via _run_totals) --------
    tg, td, nf = _dash._run_totals(cur_drops)
    avg_draws = (td / nf) if nf else 0.0
    avg_gpu = (tg / nf) if nf else 0.0
    btg = btd = bnf = 0
    if bl:
        btg, btd, bnf = _dash._run_totals([bl])
    b_avg_draws = (btd / bnf) if bnf else None
    b_avg_gpu = (btg / bnf) if bnf else None
    # worst overdraw / worst shader (MAX; name the area). Reuse the per-area inputs already collected.
    ov_area, ov_val = '', None
    for a, am in cur_hm.per_area.items():
        if am.overdraw_pct is not None and (ov_val is None or am.overdraw_pct > ov_val):
            ov_area, ov_val = a, am.overdraw_pct
    worst_sh = _dash._top_shaders_by_area(root, cur, 999)
    sh_area, sh_label, sh_cplx = (worst_sh[0][0], worst_sh[0][1], worst_sh[0][2]) if worst_sh \
        else ('', '', None)
    b_ov = max((r[2] for r in _dash._worst_overdraw([bl], 999)), default=None) if bl else None
    b_sh = max((r[2] for r in _dash._top_shaders_by_area(root, bl, 999)), default=None) if bl else None

    kpis = [
        _kpi('avg draws / frame', base.fmt_int(round(avg_draws)),
             delta_html=_pct_pill(avg_draws, b_avg_draws) if bl else '',
             trend=_trendline(series['draws'], tone=_dir_tone(avg_draws, b_avg_draws)),
             note=f'{n_areas} area{"" if n_areas == 1 else "s"} - {base.fmt_int(td)} total'),
        _kpi('avg gpu / frame', base.fmt_float(avg_gpu, 4),
             delta_html=_pct_pill(avg_gpu, b_avg_gpu) if bl else '',
             trend=_trendline(series['gpu'], tone=_dir_tone(avg_gpu, b_avg_gpu)),
             note=f'{base.fmt_float(tg, 3)} s total'),
        _kpi('worst overdraw', base.fmt_pct(ov_val) if ov_val is not None else '-',
             delta_html=_pct_pill(ov_val, b_ov) if bl else '',
             trend=_trendline(series['overdraw'], tone=_dir_tone(ov_val, b_ov)),
             note=ov_area),
        _kpi('worst shader', base.fmt_int(round(sh_cplx)) if sh_cplx is not None else '-',
             delta_html=_pct_pill(sh_cplx, b_sh) if bl else '',
             trend=_trendline(series['shader'], tone=_dir_tone(sh_cplx, b_sh)),
             note=(f'{sh_area} - over the complexity budget'
                   if (sh_cplx is not None and sh_cplx >= rcfg.shader_complexity_high)
                   else sh_area)),
    ]
    parts.append('<div class="kpi-strip">' + ''.join(kpis) + '</div>')

    # --- Movement since <baseline> (baseline-gated; the tech-lead glance) ----------------------
    if bl:
        n_resolved = sum(1 for c in tr.improvements if c.kind == 'resolved')
        n_new = sum(1 for c in tr.regressions if c.kind == 'new')
        body = (f'<div class="movement">'
                f'<div class="mv-col"><h3>Improvements</h3>{_change_list(tr.improvements, "none")}</div>'
                f'<div class="mv-col"><h3>Regressions</h3>{_change_list(tr.regressions, "none")}</div>'
                f'<p class="note dim mv-rollup">{n_resolved} resolved / {n_new} newly un-instanced</p>'
                f'</div>')
        parts.append(base.section_card('movement', f'Movement since {bl.key}', body))

    # --- By area (ALL areas, worst-first) ------------------------------------------------------
    order = sorted(cur_hm.per_area,
                   key=lambda a: (v.area_verdicts[a].value, cur_hm.per_area[a].avg_gpu_per_frame),
                   reverse=True)
    rows = ['<table class="data"><caption>By area</caption><thead><tr>'
            '<th scope="col">area</th>'
            '<th class="num" scope="col">avg draws / frame</th>'
            '<th class="num" scope="col">avg gpu / frame</th>'
            '<th class="num" scope="col">overdraw</th>'
            '<th scope="col">status</th>'
            '</tr></thead><tbody>']
    for a in order:
        am = cur_hm.per_area[a]
        bam = bl_hm.per_area.get(a) if bl_hm else None
        d_draws = _pct_pill(am.avg_draws_per_frame,
                            bam.avg_draws_per_frame if bam else None) if bl else ''
        d_gpu = _pct_pill(am.avg_gpu_per_frame,
                          bam.avg_gpu_per_frame if bam else None) if bl else ''
        ov = base.fmt_pct(am.overdraw_pct) if am.overdraw_pct is not None else '-'
        rows.append(
            f'<tr><td>{base.h(a)}</td>'
            f'<td class="num">{base.fmt_int(round(am.avg_draws_per_frame))} {d_draws}</td>'
            f'<td class="num">{base.fmt_float(am.avg_gpu_per_frame, 4)} {d_gpu}</td>'
            f'<td class="num">{ov}</td>'
            f'<td><span class="bh-status s-{v.area_verdicts[a].name}">'
            f'{base.h(_STATE_LABEL[v.area_verdicts[a]])}</span></td></tr>')
    rows.append('</tbody></table>')
    parts.append(base.section_card('by_area', 'By area', ''.join(rows), count=n_areas))

    return base.write_report(out_path, [base.report_page(
        'build health summary', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
        current_page='summary', body_attrs={'data-page-kind': 'summary'},
        ab=ab, root=root, report_key='summary', run=rc, run_nav_key='summary',
        device=base.provenance_strip(*base.newest_drop_provenance(root, cur_drops)))])


if __name__ == '__main__':
    base.run_report(build)
