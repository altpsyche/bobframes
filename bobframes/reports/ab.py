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
from . import all_reports
from .. import manifest


def render_pair(root: str, baseline, compare, *,
                sink: base.AssetSink = base.AssetSink.INLINE,
                build_ts: str | None = None, redact: bool = False) -> list[str]:
    """Render every report for one ``(baseline, compare)`` pair; return the written paths.

    Reused by `package` shared-asset re-render (c16t, ADR-41): ``sink=REF`` re-emits the pair's pages
    with depth-relative ``_assets/`` links and ``build_ts`` pins the deterministic stamp (the caller
    renders into a staging copy of the tree). ``redact`` (c16u, ADR-40) scrubs the device strip. Raises
    on a failing report (the caller wraps it). The newest-run dashboard A/B picker is rebuilt by the
    orchestrator, so this does not touch the dashboard.
    """
    drops = [baseline, compare]
    ab = (baseline, compare)
    return [mod.build(root, drops=drops, ab=ab, sink=sink, build_ts=build_ts, redact=redact)
            for mod in all_reports()]


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

    # D-7: ab resolves drops via discovery (not the catalog chokepoint), so guard each drop's manifest
    # before reading its Parquet. Raises PipelineError (exit 1) on a stale-schema drop.
    for r in (*baseline.rows, *compare.rows):
        if r.drop_dir:
            manifest.assert_compatible(r.drop_dir)

    print(f'a/b: {baseline.key} ({baseline.n_captures} captures) '
          f'vs {compare.key} ({compare.n_captures} captures)')

    drops = [baseline, compare]
    ab = (baseline, compare)
    for mod in all_reports():
        try:
            out = mod.build(root, drops=drops, ab=ab)
            print(f'  wrote {out}')
        except Exception as e:
            print(f'  {mod.__name__} FAILED: {e}', file=sys.stderr)
            return 1
    # Rebuild dashboard so its a/b table picks up new pair
    from . import dashboard as report_dashboard
    try:
        out = report_dashboard.build(root)
        print(f'  refreshed dashboard {out}')
    except Exception as e:
        print(f'  dashboard refresh FAILED: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
