"""Q-11 + Q-12 (v027_3): draws_by_class hero KPIs name the estimator precisely and use the real
median. A pure-unit test of `_compute_kpis` (no render) pins:
  - the prepass/opaque ratio is `statistics.median` (the old `sorted[n//2]` returned the UPPER-middle,
    an off-by-one on an even number of areas);
  - "total draws" is paired with a per-frame mean, both labeled (Q-12).
"""
from __future__ import annotations

from collections import Counter

from bobframes.reports import draws_by_class as dbc


def _kpi(kpis, label_prefix):
    return next(k['value'] for k in kpis if k['label'].startswith(label_prefix))


def test_ratio_is_true_median_not_upper_middle():
    # two areas: ratios 1.0 and 3.0 -> median 2.0; the old sorted[n//2] would pick 3.0 (upper-middle).
    counts = {('A', 'd'): Counter(prepass=1, opaque=1),
              ('B', 'd'): Counter(prepass=3, opaque=1)}
    kpis = dbc._compute_kpis(counts, ['A', 'B'], total_frames=1)
    assert _kpi(kpis, 'median prepass / opaque') == '2.00'


def test_total_draws_paired_with_per_frame_mean():
    counts = {('A', 'd'): Counter(prepass=1, opaque=1),
              ('B', 'd'): Counter(prepass=3, opaque=1)}   # 6 draws total
    kpis = dbc._compute_kpis(counts, ['A', 'B'], total_frames=2)
    assert _kpi(kpis, 'total draws over captures') == '6'
    assert _kpi(kpis, 'mean draws / frame') == '3'        # 6 / 2 frames
    # single-capture path: per_frame is a no-op, so the mean equals the total
    kpis1 = dbc._compute_kpis(counts, ['A', 'B'], total_frames=1)
    assert _kpi(kpis1, 'mean draws / frame') == '6'
