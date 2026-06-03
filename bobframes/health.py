"""Build-health verdict + trend - a presentation-independent contract (ADR-39).

Evaluates per-area performance metrics into an OK/AT_RISK/ALARM/UNKNOWN verdict and a trajectory
(``Direction`` + a ranked improvements/regressions ledger). This lives BELOW presentation (a peer of
the future ``jsonout``/``export``, NOT under ``reports/``) so the one-pager (``reports/summary.py``),
the c20 ``--json`` emitter, and the c21 ``report --gate`` exit code all consume the SAME evaluator and
can never disagree - durable logic belongs in the data contract, not a presentation page (ADR-37).

Pure: no HTML, no I/O, no human labels, no ``random``/``Date``. ``cfg`` is duck-typed over
``config.ReportCfg`` (reads its 5 threshold attrs only); the human verdict labels (``Healthy`` etc.)
live in the presentation layer.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ReportCfg


class State(enum.Enum):
    """Build-health tier. ``.name`` is the stable wire identifier (c20 JSON); the int is internal
    only - it orders the rollup ``max(area_verdicts)``:

        OK < UNKNOWN < AT_RISK < ALARM

    UNKNOWN outranks OK so missing data never reads as a false green (ADR-23), but sits BELOW
    AT_RISK/ALARM so a genuine problem in one area is never masked by an unmeasured area - the
    unmeasured area is surfaced per-area instead.
    """

    OK = 0
    UNKNOWN = 1
    AT_RISK = 2
    ALARM = 3


class Direction(enum.Enum):
    """Run-over-run trajectory of the headline metrics. ``.name`` is the wire identifier."""

    IMPROVING = 0
    MIXED = 1
    REGRESSING = 2
    UNKNOWN = 3


@dataclass(frozen=True)
class Trigger:
    """One rule evaluation in an area's ledger (the audit trail c20/c21 expose)."""

    rule: str             # stable rule id, e.g. 'overdraw_alarm'
    input: str            # the AreaMetrics field it read, e.g. 'overdraw_pct'
    value: float | None   # the metric value (None = the input was absent)
    threshold: float      # the ReportCfg threshold compared against
    fired: bool           # present and value >= threshold
    present: bool         # value is not None


@dataclass(frozen=True)
class AreaMetrics:
    """One area's verdict inputs. A ``None`` field is an ABSENT measurement (present=False).

    The first four feed the verdict; ``overdraw_pct``/``shader_cplx``/``mesh_repeat`` are ABSOLUTE
    signals, ``gpu_regression_pct`` is a TRAJECTORY signal (None on every single-run build). The two
    ``avg_*`` are always-present scale numbers (also the headline KPI averages + trend deltas).
    """

    overdraw_pct: float | None
    gpu_regression_pct: float | None
    shader_cplx: float | None
    mesh_repeat: float | None
    avg_draws_per_frame: float
    avg_gpu_per_frame: float


@dataclass(frozen=True)
class HealthMetrics:
    per_area: dict[str, AreaMetrics]
    has_baseline: bool


@dataclass(frozen=True)
class Verdict:
    state: State
    triggers: list[Trigger]
    worst_area: str | None
    area_verdicts: dict[str, State]


@dataclass(frozen=True)
class Change:
    metric: str            # 'draws' | 'gpu' | 'overdraw' | 'shader'
    area: str | None
    delta_pct: float | None
    kind: str              # 'improved' | 'regressed' | 'resolved' | 'new'


@dataclass(frozen=True)
class Trend:
    direction: Direction
    improvements: list[Change]
    regressions: list[Change]


# Rule tables: (rule_id, AreaMetrics field, ReportCfg threshold attr). First-match, ALARM band before
# AT_RISK band. Each comparison mirrors a source report so the verdict cannot disagree with it.
_ALARM_RULES = (
    ('overdraw_alarm', 'overdraw_pct', 'overdraw_reject_alarm_pct'),
    ('gpu_regression', 'gpu_regression_pct', 'gpu_regression_pct'),
)
_AT_RISK_RULES = (
    ('overdraw_warn', 'overdraw_pct', 'overdraw_reject_warn_pct'),
    ('shader_high', 'shader_cplx', 'shader_complexity_high'),
    ('mesh_repeat', 'mesh_repeat', 'instancing_repeat_min'),
)
# Absolute inputs that must be PRESENT for an area to be OK. ``gpu_regression_pct`` is NOT here: it is
# a trajectory input, absent on every single-run build, so its absence does not block OK (it shows as
# Direction=UNKNOWN). Missing absolute data still -> UNKNOWN (no false-green, ADR-23).
_ABSOLUTE_INPUTS = ('overdraw_pct', 'shader_cplx', 'mesh_repeat')

# The four headline metrics the trajectory nets over (lower-is-better), each an AreaMetrics field.
# These are exactly the four one-pager KPI chips.
_TREND_METRICS = (
    ('draws', 'avg_draws_per_frame'),
    ('gpu', 'avg_gpu_per_frame'),
    ('overdraw', 'overdraw_pct'),
    ('shader', 'shader_cplx'),
)


def _trigger(am: AreaMetrics, rule: str, field: str, threshold: float) -> Trigger:
    value = getattr(am, field)
    present = value is not None
    return Trigger(rule=rule, input=field, value=value, threshold=threshold,
                   fired=present and value >= threshold, present=present)


def area_verdict(am: AreaMetrics, cfg: ReportCfg) -> Verdict:
    """Score ONE area, first-match, from ReportCfg ONLY (no new threshold).

    ALARM if any alarm-band rule fired; else AT_RISK if any at-risk-band rule fired; else OK only if
    every absolute input is present; else UNKNOWN (absent absolute data -> no false-green). Returns a
    single-area Verdict carrying the full Trigger ledger; the rollup fills worst_area/area_verdicts.
    """
    alarm = [_trigger(am, r, f, getattr(cfg, a)) for r, f, a in _ALARM_RULES]
    at_risk = [_trigger(am, r, f, getattr(cfg, a)) for r, f, a in _AT_RISK_RULES]
    triggers = alarm + at_risk
    if any(t.fired for t in alarm):
        state = State.ALARM
    elif any(t.fired for t in at_risk):
        state = State.AT_RISK
    elif all(getattr(am, f) is not None for f in _ABSOLUTE_INPUTS):
        state = State.OK
    else:
        state = State.UNKNOWN
    return Verdict(state=state, triggers=triggers, worst_area=None, area_verdicts={})


def verdict(metrics: HealthMetrics, cfg: ReportCfg) -> Verdict:
    """Roll up per-area verdicts: ``state = max(area_verdicts)`` over the State ordering.

    Empty (no areas) -> UNKNOWN (never OK). ``worst_area`` is the worst-scoring area (alphabetical
    tie-break). ``triggers`` concatenates every area's ledger.
    """
    area_verdicts: dict[str, State] = {}
    triggers: list[Trigger] = []
    for area in sorted(metrics.per_area):
        av = area_verdict(metrics.per_area[area], cfg)
        area_verdicts[area] = av.state
        triggers.extend(av.triggers)
    if not area_verdicts:
        return Verdict(state=State.UNKNOWN, triggers=triggers, worst_area=None, area_verdicts={})
    state = max(area_verdicts.values(), key=lambda s: s.value)
    # max() over the alphabetically-sorted areas returns the first area at the worst .value.
    worst_area = max(sorted(area_verdicts), key=lambda a: area_verdicts[a].value)
    return Verdict(state=state, triggers=triggers, worst_area=worst_area,
                   area_verdicts=area_verdicts)


def trend(current: HealthMetrics, baseline: HealthMetrics | None) -> Trend:
    """Run-over-run trajectory: a ``Direction`` + a ranked improvements/regressions ledger.

    No baseline -> Direction.UNKNOWN with empty ledgers (the trajectory is genuinely unknown; never a
    false-green). Over the four headline metrics x every area: a metric present in current but absent
    in baseline is ``new`` (a regression-side risk); present in baseline but gone in current is
    ``resolved`` (an improvement, e.g. a mesh newly un-instanced); present in both becomes a
    lower-is-better delta (``improved`` if it dropped, ``regressed`` if it rose). Direction nets the
    DELTA-bearing changes only (improved vs regressed) over the four metrics.
    """
    if baseline is None or not baseline.per_area:
        return Trend(direction=Direction.UNKNOWN, improvements=[], regressions=[])
    improvements: list[Change] = []
    regressions: list[Change] = []
    areas = sorted(set(current.per_area) | set(baseline.per_area))
    for metric, field in _TREND_METRICS:
        for area in areas:
            cam = current.per_area.get(area)
            bam = baseline.per_area.get(area)
            cur = getattr(cam, field) if cam is not None else None
            base = getattr(bam, field) if bam is not None else None
            if cur is None and base is None:
                continue
            if base is None:                                  # appeared this run
                regressions.append(Change(metric, area, None, 'new'))
            elif cur is None:                                 # gone this run
                improvements.append(Change(metric, area, None, 'resolved'))
            elif base == 0:                                   # cannot form a pct; skip
                continue
            else:
                delta = (cur - base) / base * 100.0
                if delta < 0:
                    improvements.append(Change(metric, area, delta, 'improved'))
                elif delta > 0:
                    regressions.append(Change(metric, area, delta, 'regressed'))
                # delta == 0 -> no movement -> skip
    # Rank: largest magnitude first (None -> infinity, so new/resolved lead), then (metric, area).
    def _rank(c: Change) -> tuple:
        mag = float('inf') if c.delta_pct is None else abs(c.delta_pct)
        return (-mag, c.metric, c.area or '')
    improvements.sort(key=_rank)
    regressions.sort(key=_rank)
    n_improved = sum(1 for c in improvements if c.kind == 'improved')
    n_regressed = sum(1 for c in regressions if c.kind == 'regressed')
    if n_improved > 0 and n_regressed == 0:
        direction = Direction.IMPROVING
    elif n_regressed > 0 and n_improved == 0:
        direction = Direction.REGRESSING
    else:
        direction = Direction.MIXED
    return Trend(direction=direction, improvements=improvements, regressions=regressions)
