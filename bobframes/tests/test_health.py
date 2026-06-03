"""c16q: unit tests for the presentation-independent build-health contract (bobframes/health.py).

Golden-independent: these pin the verdict logic (first-match bands, absolute-first OK gating, the
no-false-green UNKNOWN, the ALARM-beats-UNKNOWN rollup) + the trajectory (Direction over the four
headline metrics, resolved/new kinds) so a regression fails here, focused, before any render.
"""
from __future__ import annotations

import pytest

from bobframes import health as H
from bobframes.config import ReportCfg
from bobframes.health import AreaMetrics, Direction, HealthMetrics, State

CFG = ReportCfg()


def _am(*, overdraw=10.0, gpu_reg=0.0, shader=30.0, mesh=2,
        draws=800.0, gpu=0.03):
    return AreaMetrics(overdraw_pct=overdraw, gpu_regression_pct=gpu_reg,
                       shader_cplx=shader, mesh_repeat=mesh,
                       avg_draws_per_frame=draws, avg_gpu_per_frame=gpu)


# --- area_verdict: bands + first-match ---------------------------------------------------------

def test_area_verdict_ok():
    assert H.area_verdict(_am(), CFG).state is State.OK


def test_area_verdict_alarm_overdraw():
    v = H.area_verdict(_am(overdraw=75.0), CFG)
    assert v.state is State.ALARM
    assert any(t.rule == 'overdraw_alarm' and t.fired for t in v.triggers)


def test_area_verdict_alarm_gpu_regression():
    assert H.area_verdict(_am(gpu_reg=12.0), CFG).state is State.ALARM


@pytest.mark.parametrize('kw', [{'overdraw': 45.0}, {'shader': 65.0}, {'mesh': 5}])
def test_area_verdict_at_risk_each_input(kw):
    assert H.area_verdict(_am(**kw), CFG).state is State.AT_RISK


def test_area_verdict_first_match_alarm_over_at_risk():
    # an alarm-band fire wins over an at-risk-band fire in the same area
    assert H.area_verdict(_am(overdraw=75.0, shader=65.0), CFG).state is State.ALARM


# --- absolute-first gating (no false-green; trajectory absence does not block OK) ---------------

@pytest.mark.parametrize('field,inp', [
    ('overdraw', 'overdraw_pct'), ('shader', 'shader_cplx'), ('mesh', 'mesh_repeat'),
])
def test_missing_absolute_input_is_unknown(field, inp):
    v = H.area_verdict(_am(**{field: None}), CFG)
    assert v.state is State.UNKNOWN
    assert all(t.present is False for t in v.triggers if t.input == inp)


def test_no_baseline_absolute_clean_is_ok():
    # single-run: gpu_regression absent (trajectory), absolute inputs present + passing -> OK
    assert H.area_verdict(_am(gpu_reg=None), CFG).state is State.OK


def test_rule_recomputable_from_reportcfg():
    v = H.area_verdict(_am(overdraw=75.0, gpu_reg=12.0, shader=65.0, mesh=5), CFG)
    by_rule = {t.rule: t for t in v.triggers}
    assert by_rule['overdraw_alarm'].threshold == CFG.overdraw_reject_alarm_pct
    assert by_rule['gpu_regression'].threshold == CFG.gpu_regression_pct
    assert by_rule['overdraw_warn'].threshold == CFG.overdraw_reject_warn_pct
    assert by_rule['shader_high'].threshold == CFG.shader_complexity_high
    assert by_rule['mesh_repeat'].threshold == CFG.instancing_repeat_min
    for t in v.triggers:
        assert t.fired == (t.present and t.value >= t.threshold)


# --- verdict rollup ----------------------------------------------------------------------------

def test_verdict_state_is_max_of_area_verdicts():
    hm = HealthMetrics({'a': _am(), 'b': _am(overdraw=45.0), 'c': _am(overdraw=75.0)}, True)
    v = H.verdict(hm, CFG)
    assert v.state is State.ALARM
    assert v.state.value == max(s.value for s in v.area_verdicts.values())


def test_verdict_alarm_beats_unknown():
    # the precedence guard: a known fire is never masked by an unmeasured area
    hm = HealthMetrics({'a': _am(overdraw=75.0), 'b': _am(overdraw=None)}, True)
    v = H.verdict(hm, CFG)
    assert v.area_verdicts == {'a': State.ALARM, 'b': State.UNKNOWN}
    assert v.state is State.ALARM
    assert v.worst_area == 'a'


def test_verdict_unknown_beats_ok():
    hm = HealthMetrics({'a': _am(), 'b': _am(overdraw=None)}, True)
    assert H.verdict(hm, CFG).state is State.UNKNOWN


def test_verdict_worst_area_alphabetical_tie():
    hm = HealthMetrics({'z': _am(overdraw=75.0), 'a': _am(overdraw=75.0)}, True)
    assert H.verdict(hm, CFG).worst_area == 'a'


def test_verdict_empty_is_unknown():
    v = H.verdict(HealthMetrics({}, False), CFG)
    assert v.state is State.UNKNOWN
    assert v.worst_area is None


def test_state_enum_stable():
    assert [(s.name, s.value) for s in State] == \
        [('OK', 0), ('UNKNOWN', 1), ('AT_RISK', 2), ('ALARM', 3)]
    assert [(d.name, d.value) for d in Direction] == \
        [('IMPROVING', 0), ('MIXED', 1), ('REGRESSING', 2), ('UNKNOWN', 3)]


# --- trend -------------------------------------------------------------------------------------

def test_trend_unknown_no_baseline():
    t = H.trend(HealthMetrics({'a': _am()}, False), None)
    assert t.direction is Direction.UNKNOWN
    assert t.improvements == [] and t.regressions == []


def test_trend_improving():
    cur = HealthMetrics({'a': _am(draws=800, gpu=0.03, overdraw=10, shader=30)}, True)
    base = HealthMetrics({'a': _am(draws=1600, gpu=0.06, overdraw=10, shader=40)}, False)
    t = H.trend(cur, base)
    assert t.direction is Direction.IMPROVING
    assert any(c.metric == 'draws' and c.kind == 'improved' for c in t.improvements)
    assert t.regressions == []


def test_trend_mixed():
    cur = HealthMetrics({'a': _am(draws=600, gpu=0.07)}, True)   # draws down, gpu up
    base = HealthMetrics({'a': _am(draws=800, gpu=0.05)}, False)
    assert H.trend(cur, base).direction is Direction.MIXED


def test_trend_direction_nets_four_metrics():
    # draws/gpu flat (skipped); overdraw improves -> IMPROVING (proves overdraw counts, not just draws/gpu)
    cur = HealthMetrics({'a': _am(draws=800, gpu=0.05, overdraw=10, shader=30)}, True)
    base = HealthMetrics({'a': _am(draws=800, gpu=0.05, overdraw=20, shader=30)}, False)
    t = H.trend(cur, base)
    assert t.direction is Direction.IMPROVING
    assert any(c.metric == 'overdraw' for c in t.improvements)


def test_trend_kinds_resolved_new():
    cur = HealthMetrics({'a': _am(), 'c': _am()}, True)     # 'c' only in current
    base = HealthMetrics({'a': _am(), 'b': _am()}, False)   # 'b' only in baseline
    t = H.trend(cur, base)
    assert any(c.kind == 'resolved' and c.area == 'b' for c in t.improvements)
    assert any(c.kind == 'new' and c.area == 'c' for c in t.regressions)


def test_trend_determinism():
    cur = HealthMetrics({'a': _am(draws=800), 'b': _am(draws=700)}, True)
    base = HealthMetrics({'a': _am(draws=900), 'b': _am(draws=600)}, False)
    assert H.trend(cur, base) == H.trend(cur, base)
