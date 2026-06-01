"""delta.sparkline_svg null-gap rendering (c16, A10).

The live shader/instancing series feed `Counter.get(k, 0)` -> 0 (never None), so production sparklines
never gap today (recorded: FINDINGS reports-quality note). This is the golden-independent guard for the
null-gap code path itself, which a future sparse-series report (e.g. a shader absent in some drops) will
exercise. Adding it to the HTML golden would need a >=3-drop fixture with genuine None series, deferred.
"""
from __future__ import annotations

from bobframes.reports import delta


def test_sparkline_all_none_or_empty_is_blank():
    assert delta.sparkline_svg([]) == ''
    assert delta.sparkline_svg([None, None, None]) == ''


def test_sparkline_nulls_split_into_separate_polylines():
    # runs [10,20] and [30,40] are polylines; the trailing isolated 50 is a single-point circle.
    svg = delta.sparkline_svg([10, 20, None, None, 30, 40, None, 50])
    assert svg.startswith('<svg') and svg.endswith('</svg>')
    assert svg.count('<polyline') == 2
    assert svg.count('<circle') == 1


def test_sparkline_single_value_is_a_circle():
    assert delta.sparkline_svg([None, 5, None]).count('<circle') == 1


def test_sparkline_contiguous_values_one_polyline_no_gap():
    svg = delta.sparkline_svg([1, 2, 3, 4])
    assert svg.count('<polyline') == 1
    assert svg.count('<circle') == 0
