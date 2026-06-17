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
        return base.el('span', {'class': 'delta-pill flat'}, '0%')
    cls = 'pos' if (pct < 0) == lower_is_better else 'neg'
    return base.el('span', {'class': 'delta-pill ' + cls}, f'{pct:+.0f}%')


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
    for d in rc.history:   # R-22: up to & including current -> an older page's sparkline ends at THAT run
        tg, td, nf = _dash._run_totals([d])
        draws.append((td / nf) if nf else None)
        gpu.append((tg / nf) if nf else None)
        overd.append(max((r[2] for r in _dash._worst_overdraw([d], 999)), default=None))
        shad.append(max((r[2] for r in _dash._top_shaders_by_area(root, d, 999)), default=None))
    return {'draws': draws, 'gpu': gpu, 'overdraw': overd, 'shader': shad}


# c16x-5 (ADR-42): the summary-scoped styling that was an inline <style> here now lives in the owned
# component bundle (reports/assets/components.css, [data-page-kind="summary"]-scoped) and the bespoke
# _kpi/_trendline/_change-list markup is composed from chrome.kpi_card / delta.trendline /
# chrome.status_badge / chrome.movement. summary.py keeps only the metric POLICY helpers below
# (_dir_tone / _pct_pill / _change_line / _change_list); the generic layout/markup is chrome's.


def _dir_tone(cur, prev) -> str:
    """Lower-is-better direction of a metric -> trend color: pos (improved), neg (worse), neutral."""
    if cur is None or prev in (None, 0):
        return 'neutral'
    if cur < prev:
        return 'pos'
    if cur > prev:
        return 'neg'
    return 'neutral'


def _change_line(c) -> str:
    lbl = _METRIC_LABEL.get(c.metric, c.metric)
    if c.delta_pct is None:
        pill = base.el('span', {'class': 'delta-pill flat'}, c.kind)
    else:
        cls = 'pos' if c.delta_pct < 0 else 'neg'
        pill = base.el('span', {'class': 'delta-pill ' + cls}, f'{c.delta_pct:+.0f}%')
    return base.el('li', None, lbl, ' ', c.area or '', ' ', pill)


def _change_list(changes: list, empty: str) -> str:
    if not changes:
        return base.el('p', {'class': 'note dim'}, empty)
    return base.el('ul', {'class': 'change-list'}, *[_change_line(c) for c in changes[:3]])


def build(root: str, *, drops: list | None = None, ab=None,
          run_label=None, run_date=None,
          sink: base.AssetSink = base.AssetSink.INLINE,
          build_ts: str | None = None, redact: bool = False, theme: dict | None = None) -> str:
    if drops is None:
        drops = base.discover_drops(root)
    # Run model (ADR-35): ONE current run, never a cumulative sum (the G-19 flaw). baseline = the
    # immediately-prior run (None when current is the oldest -> per-run pages get per-run truth).
    rc = base.run_context(drops, run_label=run_label, run_date=run_date)
    drops = rc.history   # R-22: header count + the per-run sparkline cover runs <= current (picker via rc)
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
            build_ts=build_ts or base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
            current_page='summary', body_attrs={'data-page-kind': 'summary'},
            ab=ab, root=root, report_key='summary', run=rc, run_nav_key='summary', sink=sink, theme=theme,
            device=base.provenance_strip(*base.newest_drop_provenance(root, cur_drops), redact=redact))])

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
        base.kpi_card('pooled mean draws / frame', base.fmt_int(round(avg_draws)),
             delta_html=_pct_pill(avg_draws, b_avg_draws) if bl else '',
             trend=base.trendline(series['draws'], tone=_dir_tone(avg_draws, b_avg_draws)),
             note=f'pooled across {base.fmt_int(nf)} frames, {n_areas} area'
                  f'{"" if n_areas == 1 else "s"} - {base.fmt_int(td)} total'),
        base.kpi_card('pooled mean gpu / frame', base.fmt_float(avg_gpu, 4),
             delta_html=_pct_pill(avg_gpu, b_avg_gpu) if bl else '',
             trend=base.trendline(series['gpu'], tone=_dir_tone(avg_gpu, b_avg_gpu)),
             note=f'pooled across {base.fmt_int(nf)} frames - {base.fmt_float(tg, 3)} s total'),
        base.kpi_card('worst overdraw', base.fmt_pct(ov_val) if ov_val is not None else '-',
             delta_html=_pct_pill(ov_val, b_ov) if bl else '',
             trend=base.trendline(series['overdraw'], tone=_dir_tone(ov_val, b_ov)),
             note=ov_area),
        base.kpi_card('worst shader', base.fmt_int(round(sh_cplx)) if sh_cplx is not None else '-',
             delta_html=_pct_pill(sh_cplx, b_sh) if bl else '',
             trend=base.trendline(series['shader'], tone=_dir_tone(sh_cplx, b_sh)),
             note=(f'{sh_area} - over the complexity budget'
                   if (sh_cplx is not None and sh_cplx >= rcfg.shader_complexity_high)
                   else sh_area)),
    ]
    parts.append(base.el('div', {'class': 'kpi-strip'}, *kpis))

    # --- Movement since <baseline> (baseline-gated; the tech-lead glance) ----------------------
    if bl:
        n_resolved = sum(1 for c in tr.improvements if c.kind == 'resolved')
        n_new = sum(1 for c in tr.regressions if c.kind == 'new')
        rollup = f'<p class="note dim mv-rollup">{n_resolved} resolved / {n_new} newly un-instanced</p>'
        body = base.movement(
            [('Improvements', _change_list(tr.improvements, 'none')),
             ('Regressions', _change_list(tr.regressions, 'none'))],
            rollup_html=rollup)
        parts.append(base.section_card('movement', f'Movement since {bl.key}', body))

    # --- By area (ALL areas, worst-first) ------------------------------------------------------
    order = sorted(cur_hm.per_area,
                   key=lambda a: (v.area_verdicts[a].value, cur_hm.per_area[a].avg_gpu_per_frame),
                   reverse=True)
    cols = [base.Column('area', 'area'),
            base.Column('draws', 'mean draws / frame (per area)', numeric=True,
                        title='area draws / area captured frames'),
            base.Column('gpu', 'mean gpu / frame (per area)', numeric=True,
                        title='area gpu seconds / area captured frames'),
            base.Column('overdraw', 'overdraw', numeric=True),
            base.Column('status', 'status')]
    trows = []
    for a in order:
        am = cur_hm.per_area[a]
        bam = bl_hm.per_area.get(a) if bl_hm else None
        d_draws = _pct_pill(am.avg_draws_per_frame,
                            bam.avg_draws_per_frame if bam else None) if bl else ''
        d_gpu = _pct_pill(am.avg_gpu_per_frame,
                          bam.avg_gpu_per_frame if bam else None) if bl else ''
        ov = base.fmt_pct(am.overdraw_pct) if am.overdraw_pct is not None else '-'
        trows.append({
            'area': a,
            'draws': base.raw(f'{base.fmt_int(round(am.avg_draws_per_frame))} {d_draws}'),
            'gpu': base.raw(f'{base.fmt_float(am.avg_gpu_per_frame, 4)} {d_gpu}'),
            'overdraw': ov,
            'status': base.status_badge(v.area_verdicts[a].name, _STATE_LABEL[v.area_verdicts[a]]),
        })
    table = base.static_table(cols, trows,
        caption="By area - each area's own per-frame mean; the headline pools all captured frames")
    parts.append(base.section_card('by_area', 'By area', table, count=n_areas))

    return base.write_report(out_path, [base.report_page(
        'build health summary', parts,
        drops=len(drops), captures=sum(d.n_captures for d in drops),
        build_ts=build_ts or base.now_iso(), crumb_depth=base.crumb_depth(ab, run=rc),
        current_page='summary', body_attrs={'data-page-kind': 'summary'},
        ab=ab, root=root, report_key='summary', run=rc, run_nav_key='summary', sink=sink, theme=theme,
        device=base.provenance_strip(*base.newest_drop_provenance(root, cur_drops), redact=redact))])


if __name__ == '__main__':
    base.run_report(build)
