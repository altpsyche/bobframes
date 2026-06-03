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

from .errors import BobFramesError

# CLI report name -> reports submodule. `build(root)` on each builds one report.
_REPORTS = {
    'draws-by-class': 'draws_by_class',
    'trend': 'trend_table',
    'instancing': 'instancing_opportunities',
    'pass-gpu': 'pass_gpu',
    'shader': 'shader_hotlist',
    'overdraw': 'overdraw',
    'summary': 'summary',           # c16q — the exec build-health one-pager (ADR-39)
    'dashboard': 'dashboard',
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
    if args.replay_timeout is not None:
        rargv += ['--replay-timeout', str(args.replay_timeout)]
    if args.convert_timeout is not None:
        rargv += ['--convert-timeout', str(args.convert_timeout)]
    return run.main(rargv)


def _cmd_render(args: argparse.Namespace) -> int:
    from . import run
    root = os.path.abspath(args.root)
    rargv = ['--root', root, '--render-only']
    if args.area:
        rargv += ['--area', args.area]
    if args.label:
        rargv += ['--label', args.label]
    if getattr(args, 'watch', False):
        return _render_watch(rargv)
    return run.main(rargv)


def _watch_paths() -> list[str]:
    """Files the render --watch loop polls: the design tokens + the modules that emit chrome."""
    from .reports import chrome as _c, delta as _d, formatters as _fm
    tokens = os.path.join(os.path.dirname(_c.__file__), 'design_tokens.toml')
    return [tokens, _c.__file__, _fm.__file__, _d.__file__]


def _render_watch(rargv: list[str]) -> int:
    """Alpha hot-reload (DESIGNER Track A): 500ms mtime poll on the token/chrome files; re-render in a
    fresh subprocess on change so edited modules/TOML are reloaded. No watchdog dependency."""
    import subprocess
    import time
    log = logging.getLogger('bobframes')
    watched = _watch_paths()

    def snapshot() -> dict:
        return {p: (os.stat(p).st_mtime if os.path.exists(p) else 0.0) for p in watched}

    cmd = [sys.executable, '-m', 'bobframes.run', *rargv]
    rc = subprocess.run(cmd).returncode
    log.info(f'watching {len(watched)} files; save an edit to re-render (Ctrl+C to stop)')
    last = snapshot()
    try:
        while True:
            time.sleep(0.5)
            now = snapshot()
            if now != last:
                last = now
                log.info('change detected; re-rendering')
                rc = subprocess.run(cmd).returncode
    except KeyboardInterrupt:
        return 4
    return rc


def _cmd_preview(args: argparse.Namespace) -> int:
    from .reports import preview
    out = preview.build(os.path.abspath(args.root))
    print(f'wrote {out}')
    return 0


def _cmd_export_tokens(args: argparse.Namespace) -> int:
    import json
    from .reports import _tokens, chrome
    if args.format == 'toml':
        sys.stdout.write(_tokens.tokens_toml_text())
    elif args.format == 'json':
        print(json.dumps(_tokens.load_tokens(), indent=2))
    else:  # css
        sys.stdout.write(chrome.design_tokens_css())
    return 0


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
    from . import config
    if args.write_config:
        path, written = config.write_config_stub(os.path.abspath('.'))
        print(f'wrote {path}' if written else f'{path} already exists; left unchanged')
        return 0
    from .errors import EXIT_TOOL_MISSING, ToolNotFound
    missing = False
    for name in ('renderdoccmd', 'qrenderdoc'):
        try:
            path, source = config.resolve_tool_verbose(name)
            # `source` is the winning step's description; for env/config/PATH it explains the
            # precedence, but for a known-path hit it IS the path -> don't print it twice.
            suffix = '' if source == path else f'  (via {source})'
            print(f'{name}: {path}{suffix}')
        except ToolNotFound as e:
            print(str(e), file=sys.stderr)
            missing = True
    return EXIT_TOOL_MISSING if missing else 0


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
    # End-to-end smoke (G-12). No --data → render-only against the bundled synthetic fixture;
    # --data DIR → full ingest + render against a real capture root.
    from .tests import smoke
    return smoke.main(data=args.data, pixel_grid=getattr(args, 'pixel_grid', 4))


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
    sp.add_argument('--replay-timeout', type=float, default=None,
                    help='per-capture qrenderdoc replay budget (s); overrides config')
    sp.add_argument('--convert-timeout', type=float, default=None,
                    help='per-file renderdoccmd convert budget (s); overrides config')
    sp.set_defaults(func=_cmd_ingest)

    sp = sub.add_parser('render', parents=[common],
                        help='render-only: rebuild HTML + catalog from existing Parquet')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--area')
    sp.add_argument('--label')
    sp.add_argument('--watch', action='store_true',
                    help='re-render on design_tokens.toml / chrome edits (alpha, 500ms mtime poll)')
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
    sp.add_argument('--write-config', action='store_true',
                    help='write a starter .bobframes.toml to the current dir (skip if present)')
    sp.set_defaults(func=_cmd_check)

    sp = sub.add_parser('version', parents=[common], help='print version, schema, pyarrow')
    sp.set_defaults(func=_cmd_version)

    sp = sub.add_parser('preview', parents=[common],
                        help='render the chrome preview gallery (_reports/_chrome_preview.html; no data)')
    sp.add_argument('root', nargs='?', default='.')
    sp.set_defaults(func=_cmd_preview)

    sp = sub.add_parser('export-tokens', parents=[common],
                        help='print design tokens to stdout as toml|json|css')
    sp.add_argument('--format', choices=['toml', 'json', 'css'], default='toml')
    sp.set_defaults(func=_cmd_export_tokens)

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
        # Load the config singleton against the verb's root so <root>/.bobframes.toml is honored
        # (§6) for report/catalog/ab/render/ingest/serve. Verbs without a root (version/check/lint)
        # lazily load bundled defaults (cwd) on first get_config(). ingest/render re-load via
        # run.main (idempotent). ConfigError surfaces as a typed BobFramesError below.
        root = getattr(args, 'root', None)
        if root is not None:
            from . import config
            config.load_config(os.path.abspath(root))
        return args.func(args)
    except KeyboardInterrupt:
        print('interrupted', file=sys.stderr)
        return 4
    except BobFramesError as e:
        # Typed pipeline/tool errors carry their own exit code (errors.py / ARCHITECTURE §4).
        print(str(e), file=sys.stderr)
        return e.exit_code


if __name__ == '__main__':
    sys.exit(main())
