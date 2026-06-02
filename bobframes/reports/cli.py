"""CLI dispatch + path utilities + report-tail helpers."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Callable

from .. import lint as _lint
from .. import paths as _paths
from ..manifest import now_iso  # single UTC timestamp helper (H-28); re-exported via base
from .discovery import DropSet, discover_drops, resolve_drop_set


def _lint_or_raise(path: str) -> None:
    hits = _lint.lint_file(path)
    if hits:
        msg_lines = [f'lint blocked {path}:']
        for lineno, label, snippet in hits:
            msg_lines.append(f'  line {lineno} [{label}]: {snippet}')
        raise RuntimeError('\n'.join(msg_lines))


def ab_subdir(root: str, baseline: DropSet, compare: DropSet) -> str:
    d = os.path.join(_paths.reports_dir(root), _paths.AB_DIR, f'{baseline.key}_vs_{compare.key}')
    os.makedirs(d, exist_ok=True)
    return d


def run_subdir(root: str, run_key: str) -> str:
    """The per-run page dir <root>/_reports/run/<run_key>/ (c16f); created on demand."""
    d = os.path.join(_paths.reports_dir(root), _paths.RUN_DIR, run_key)
    os.makedirs(d, exist_ok=True)
    return d


def _is_per_run(run) -> bool:
    """True when `run` is a RunContext rendering a NON-newest run -> its pages live under run/<key>/."""
    return run is not None and getattr(run, 'current', None) is not None and not run.is_newest


def output_path(root: str, name: str, ab: tuple | None, *, run=None) -> str:
    if ab is not None:
        baseline, compare = ab
        return os.path.join(ab_subdir(root, baseline, compare), f'{name}.html')
    if _is_per_run(run):
        return os.path.join(run_subdir(root, run.current.key), f'{name}.html')
    d = _paths.reports_dir(root)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{name}.html')


def crumb_depth(ab, *, run=None) -> int:
    """Depth of crumb relative-path to root index.html: 3 levels deep when A/B (under
    _reports/ab/<pair>/) or a per-run page (under _reports/run/<key>/), 1 for top-level reports."""
    return 3 if (ab is not None or _is_per_run(run)) else 1


def rel_path_to_drop_index(out_dir: str, drop_dir: str, anchor: str | None = None) -> str:
    """Relative path from out_dir to the per-drop browser index.html.

    drop_dir is the per-drop data dir (<root>/_data/<area>/<drop>/).
    The browser HTML lives at <root>/_reports/drill/<area>/<drop>/index.html.
    """
    drill_dir = _paths.drop_dir_to_drill_dir(drop_dir)
    target = os.path.join(drill_dir, _paths.INDEX_HTML)
    p = os.path.relpath(target, out_dir).replace('\\', '/')
    return p + ('#' + anchor if anchor else '')


def rel_path_to_drop_file(out_dir: str, drop_dir: str, subpath: str) -> str:
    """Relative path from out_dir to a file under the per-drop data dir.

    drop_dir is <root>/_data/<area>/<drop>/. Used for shader_src/<id>.glsl etc.
    """
    if not subpath:
        return ''
    target = os.path.join(drop_dir, subpath)
    return os.path.relpath(target, out_dir).replace('\\', '/')


def write_report(out_path: str, parts) -> str:
    """Write joined parts to out_path, lint, return out_path. Raises on lint hits."""
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    _lint_or_raise(out_path)
    return out_path


def run_report(build_fn: Callable, *, module_name: str) -> int:
    ap = argparse.ArgumentParser(prog=f'bobframes.reports.{module_name}')
    ap.add_argument('root', nargs='?', default='.')
    ap.add_argument('--baseline-label', default=None)
    ap.add_argument('--compare-label', default=None)
    ap.add_argument('--baseline-date', default=None)
    ap.add_argument('--compare-date', default=None)
    ap.add_argument('--run-label', default=None,
                    help='render for this run (the current run) instead of the newest (c16f)')
    ap.add_argument('--run-date', default=None)
    args = ap.parse_args(sys.argv[1:])
    root = os.path.abspath(args.root)

    if args.baseline_label or args.compare_label:
        baseline = resolve_drop_set(root, label=args.baseline_label,
                                    date=args.baseline_date)
        compare = resolve_drop_set(root, label=args.compare_label,
                                   date=args.compare_date)
        if not baseline or not compare:
            print(f'A/B resolve failed: baseline={args.baseline_label}, '
                  f'compare={args.compare_label}', file=sys.stderr)
            return 2
        out = build_fn(root, drops=[baseline, compare], ab=(baseline, compare))
    else:
        out = build_fn(root, drops=discover_drops(root), ab=None,
                       run_label=args.run_label, run_date=args.run_date)
    print(f'wrote {out}')
    return 0
