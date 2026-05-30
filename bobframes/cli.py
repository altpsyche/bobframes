"""Console entry point for the ``bobframes`` command (c11 dispatcher).

A single argparse dispatcher over the verbs in ARCHITECTURE §4. ``<root>`` is positional with
default ``.`` across every verb; flags are long-form only. Wired as ``[project.scripts]
bobframes = "bobframes.cli:main"`` and runnable as ``python -m bobframes.cli``.

Heavy modules (pipeline, reports, pyarrow) are imported lazily inside each handler so that fast
verbs like ``version`` / ``check`` stay cheap.

Exit codes (ARCHITECTURE §4): 0 success · 1 pipeline/build failure · 2 user error (argparse) ·
3 external tool missing · 4 interrupted.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

# CLI report name -> reports submodule. `build(root)` on each builds one report.
_REPORTS = {
    'draws-by-class': 'draws_by_class',
    'trend': 'trend_table',
    'instancing': 'instancing_opportunities',
    'pass-gpu': 'pass_gpu',
    'shader': 'shader_hotlist',
    'overdraw': 'overdraw',
    'dashboard': '_dashboard',
}


def _configure_logging(verbose: bool) -> None:
    """Attach the shared ``[HH:MM:SS] message`` handler to the 'bobframes' logger (G-8)."""
    logger = logging.getLogger('bobframes')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    if logger.handlers:
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(h)
    logger.propagate = False


# --- verb handlers -----------------------------------------------------------

def _cmd_version(args: argparse.Namespace) -> int:
    from . import __version__, schemas
    try:
        import pyarrow
        pa = pyarrow.__version__
    except Exception:
        pa = 'not installed'
    print(f'bobframes {__version__}  schema {schemas.SCHEMA_VERSION}  pyarrow {pa}')
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    from . import run
    rargv = ['--root', os.path.abspath(args.root)]
    if args.area:
        rargv += ['--area', args.area]
    if args.label:
        rargv += ['--label', args.label]
    if args.capture:
        rargv += ['--capture', args.capture]
    if args.force:
        rargv += ['--force']
    if args.render_only:
        rargv += ['--render-only']
    rargv += ['--workers', str(args.workers), '--pixel-grid', str(args.pixel_grid)]
    return run.main(rargv)


def _cmd_render(args: argparse.Namespace) -> int:
    from . import run
    rargv = ['--root', os.path.abspath(args.root), '--render-only']
    if args.area:
        rargv += ['--area', args.area]
    if args.label:
        rargv += ['--label', args.label]
    return run.main(rargv)


def _cmd_ab(args: argparse.Namespace) -> int:
    from .reports import ab
    argv = [os.path.abspath(args.root),
            '--baseline-label', args.baseline_label,
            '--compare-label', args.compare_label]
    if args.baseline_date:
        argv += ['--baseline-date', args.baseline_date]
    if args.compare_date:
        argv += ['--compare-date', args.compare_date]
    return ab.main(argv)


def _cmd_report(args: argparse.Namespace) -> int:
    import importlib
    modname = _REPORTS.get(args.name)
    if modname is None:
        print(f'unknown report {args.name!r}; choose from: {", ".join(sorted(_REPORTS))}',
              file=sys.stderr)
        return 2
    mod = importlib.import_module(f'.reports.{modname}', package='bobframes')
    out = mod.build(os.path.abspath(args.root))
    print(f'wrote {out}')
    return 0


def _cmd_catalog(args: argparse.Namespace) -> int:
    from . import catalog
    log = logging.getLogger('bobframes')
    summary = catalog.build_catalog(os.path.abspath(args.root))
    log.info(f"catalog: {summary['drop_count']} drops, {summary['capture_count']} captures")
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    from . import lint
    rc = 0
    for path in args.files:
        hits = lint.lint_file(path)
        for lineno, label, snip in hits:
            print(f'{path}:{lineno}: [{label}] {snip}')
            rc = 1
    return rc


def _cmd_check(args: argparse.Namespace) -> int:
    if sys.platform != 'win32':
        print('bobframes v1 is Windows-only (qrenderdoc replay requirement). '
              'Track GH issue for Linux/macOS support.', file=sys.stderr)
        return 3
    if args.write_config:
        print('--write-config is a v0.2 feature (config layer); not available yet.',
              file=sys.stderr)
        return 2
    from . import qrd_harness, rdcmd
    missing = False
    for name, finder in (('renderdoccmd', rdcmd.find_renderdoccmd),
                         ('qrenderdoc', qrd_harness.find_qrenderdoc)):
        try:
            print(f'{name}: {finder()}')
        except FileNotFoundError:
            print(f'{name}: NOT FOUND', file=sys.stderr)
            missing = True
    return 3 if missing else 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import functools
    import http.server
    import socketserver

    root = os.path.abspath(args.root)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    log = logging.getLogger('bobframes')
    try:
        with socketserver.TCPServer((args.bind, args.port), handler) as httpd:
            log.info(f'serving {root} at http://{args.bind}:{args.port} (Ctrl+C to stop)')
            httpd.serve_forever()
    except KeyboardInterrupt:
        return 4
    return 0


def _cmd_smoke(args: argparse.Namespace) -> int:
    # End-to-end smoke. `--data` (custom capture dir) is wired in c15's smoke rewrite (G-12);
    # for now this runs the existing self-hosted smoke against its bundled paths.
    from .tests import smoke
    return smoke.main()


# --- parser ------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--verbose', action='store_true', help='DEBUG-level logging')

    p = argparse.ArgumentParser(
        prog='bobframes',
        description='RenderDoc capture pipeline: ingest, analyze, render.')
    sub = p.add_subparsers(dest='verb', metavar='<verb>')

    sp = sub.add_parser('ingest', parents=[common],
                        help='full pipeline: export, parse, replay, parquetize, derive, render')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--area')
    sp.add_argument('--label')
    sp.add_argument('--capture')
    sp.add_argument('--force', action='store_true')
    sp.add_argument('--render-only', action='store_true')
    sp.add_argument('--workers', type=int, default=min(4, os.cpu_count() or 4))
    sp.add_argument('--pixel-grid', type=int, default=4)
    sp.set_defaults(func=_cmd_ingest)

    sp = sub.add_parser('render', parents=[common],
                        help='render-only: rebuild HTML + catalog from existing Parquet')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--area')
    sp.add_argument('--label')
    sp.set_defaults(func=_cmd_render)

    sp = sub.add_parser('ab', parents=[common], help='all reports for one drop pair')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--baseline-label', required=True)
    sp.add_argument('--compare-label', required=True)
    sp.add_argument('--baseline-date')
    sp.add_argument('--compare-date')
    sp.set_defaults(func=_cmd_ab)

    sp = sub.add_parser('report', parents=[common], help='build one named report')
    sp.add_argument('name', choices=sorted(_REPORTS))
    sp.add_argument('root', nargs='?', default='.')
    sp.set_defaults(func=_cmd_report)

    sp = sub.add_parser('catalog', parents=[common], help='rebuild _data/_catalog.parquet only')
    sp.add_argument('root', nargs='?', default='.')
    sp.set_defaults(func=_cmd_catalog)

    sp = sub.add_parser('lint', parents=[common], help='lint HTML/MD files against the banlist')
    sp.add_argument('files', nargs='+')
    sp.set_defaults(func=_cmd_lint)

    sp = sub.add_parser('check', parents=[common], help='resolve external tool paths')
    sp.add_argument('--write-config', action='store_true', help='(v0.2)')
    sp.set_defaults(func=_cmd_check)

    sp = sub.add_parser('version', parents=[common], help='print version, schema, pyarrow')
    sp.set_defaults(func=_cmd_version)

    sp = sub.add_parser('serve', parents=[common], help='static preview server')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--port', type=int, default=8000)
    sp.add_argument('--bind', default='127.0.0.1')
    sp.set_defaults(func=_cmd_serve)

    sp = sub.add_parser('smoke', parents=[common], help='end-to-end smoke test')
    sp.add_argument('--data', help='capture dir (default: bundled synthetic; c15)')
    sp.set_defaults(func=_cmd_smoke)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help()
        return 0

    _configure_logging(getattr(args, 'verbose', False))
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print('interrupted', file=sys.stderr)
        return 4


if __name__ == '__main__':
    sys.exit(main())
