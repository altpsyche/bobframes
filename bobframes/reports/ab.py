"""Unified A/B entry point. Generates all 6 reports for one drop pair.

Usage:
    python -m bobframes.reports.ab \\
        --baseline-label r110565 \\
        --compare-label  r110600 \\
        [--baseline-date 2026-05-27] \\
        [--compare-date  2026-06-15] \\
        [--root .]

Writes _reports/ab/<labelA>_vs_<labelB>/<name>.html for each report.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import base
from . import draws_by_class as report_draws_by_class
from . import trend_table as report_trend
from . import instancing_opportunities as report_instancing
from . import pass_gpu as report_pass_gpu
from . import shader_hotlist as report_shader
from . import overdraw as report_overdraw


_MODULES = [
    report_draws_by_class,
    report_trend,
    report_instancing,
    report_pass_gpu,
    report_shader,
    report_overdraw,
]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog='bobframes.reports.ab')
    ap.add_argument('root', nargs='?', default='.')
    # Hidden one-release alias for the old --root flag (positional is canonical, §4).
    ap.add_argument('--root', dest='root', default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    ap.add_argument('--baseline-label', required=True)
    ap.add_argument('--compare-label', required=True)
    ap.add_argument('--baseline-date', default=None)
    ap.add_argument('--compare-date', default=None)
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    baseline = base.resolve_drop_set(root, label=args.baseline_label,
                                     date=args.baseline_date)
    compare = base.resolve_drop_set(root, label=args.compare_label,
                                    date=args.compare_date)
    if not baseline:
        print(f'baseline not found: label={args.baseline_label}, '
              f'date={args.baseline_date}', file=sys.stderr)
        return 2
    if not compare:
        print(f'compare not found: label={args.compare_label}, '
              f'date={args.compare_date}', file=sys.stderr)
        return 2

    print(f'a/b: {baseline.key} ({baseline.n_captures} captures) '
          f'vs {compare.key} ({compare.n_captures} captures)')

    drops = [baseline, compare]
    ab = (baseline, compare)
    for mod in _MODULES:
        try:
            out = mod.build(root, drops=drops, ab=ab)
            print(f'  wrote {out}')
        except Exception as e:
            print(f'  {mod.__name__} FAILED: {e}', file=sys.stderr)
            return 1
    # Rebuild dashboard so its a/b table picks up new pair
    from . import _dashboard as report_dashboard
    try:
        out = report_dashboard.build(root)
        print(f'  refreshed dashboard {out}')
    except Exception as e:
        print(f'  dashboard refresh FAILED: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
