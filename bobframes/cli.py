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
    # c1c (ADR-45): forward the one-shot theme flags to the render engine (and into the watch
    # subprocess, so an --accent preview hot-reloads on token/.bobframes.toml edits too).
    if getattr(args, 'accent', None):
        rargv += ['--accent', args.accent]
    if getattr(args, 'accent_data', None):
        rargv += ['--accent-data', args.accent_data]
    if getattr(args, 'watch', False):
        return _render_watch(rargv, root)
    return run.main(rargv)


def _watch_paths(root: str | None = None) -> list[str]:
    """Files the render --watch loop polls: the design tokens + the modules that emit chrome + the
    project ``.bobframes.toml`` (so a `[theme]` edit hot-reloads like a token edit; c1c/ADR-45)."""
    from .reports import chrome as _c, delta as _d, formatters as _fm
    tokens = os.path.join(os.path.dirname(_c.__file__), 'design_tokens.toml')
    paths = [tokens, _c.__file__, _fm.__file__, _d.__file__]
    if root:
        paths.append(os.path.join(root, '.bobframes.toml'))
    return paths


def _render_watch(rargv: list[str], root: str | None = None) -> int:
    """Alpha hot-reload (DESIGNER Track A): 500ms mtime poll on the token/chrome files; re-render in a
    fresh subprocess on change so edited modules/TOML are reloaded. No watchdog dependency."""
    import subprocess
    import time
    log = logging.getLogger('bobframes')
    watched = _watch_paths(root)

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
    from . import config
    from .reports import preview
    # c1c (ADR-45): preview a color override without rendered data; config [theme] + --accent overlay.
    theme = config.theme_for_render(config.get_config(),
                                    getattr(args, 'accent', None), getattr(args, 'accent_data', None))
    out = preview.build(os.path.abspath(args.root), theme=theme)
    print(f'wrote {out}')
    return 0


def _theme_template_text() -> str:
    """A ready-to-paste ``[theme]`` starter: the overridable color knobs (config.THEME_KEYS) with their
    current bundled defaults, commented out so an untouched paste is a no-op (c1c/ADR-45)."""
    from . import config
    from .reports import _tokens
    colors = _tokens.load_tokens().get('color', {})
    lines = [
        '# bobframes [theme] override -- paste into your .bobframes.toml and uncomment any line to',
        '# re-hue the chrome. Omitted keys inherit the bundled neutral default (so you never lose a',
        '# future default). Values are oklch()/light-dark() token strings: ASCII, no ; { }. Only these',
        '# COLOR keys are overridable; layout/spacing/type/radius stay bundled. See DESIGNER.md / ADR-45.',
        '[theme]',
    ]
    for k in sorted(config.THEME_KEYS):
        v = colors.get(k, '')
        lines.append(f'# {k} = {v!r}' if v else f'# {k} =')
    return '\n'.join(lines) + '\n'


def _cmd_export_tokens(args: argparse.Namespace) -> int:
    import json
    from .reports import _tokens, chrome
    if getattr(args, 'theme_template', False):
        sys.stdout.write(_theme_template_text())
        return 0
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
    # The static preview server body lives in serve.serve_forever so the `ui` panel can reuse the
    # same builder (serve.make_server) for its background click-to-serve (v028_3).
    from . import serve
    return serve.serve_forever(os.path.abspath(args.root), bind=args.bind, port=args.port)


def _cmd_ui(args: argparse.Namespace) -> int:
    # ADR-47: a zero-dependency local-web control panel that DRIVES the verbs for non-terminal users.
    # A frontend SURFACE above the verb taxonomy -- it emits no report HTML (golden gate untouched) and
    # pulls no dep into core. Lazy-imported so a core install never loads the ui package.
    from .ui import server
    return server.serve(os.path.abspath(args.root), bind=args.bind, port=args.port,
                        open_browser=not args.no_open)


def _cmd_package(args: argparse.Namespace) -> int:
    # Non-mutating stream transform of a rendered tree -> a shareable zip + standalone summary, both
    # OUTSIDE <root> (c16s, ADR-40). build() prints the one summary line and raises a typed
    # PackageError (exit 2) on a bad tree / unknown --run / output-inside-root; main() maps it.
    from . import package
    if args.redact_paths == 'fail' and not args.redact:
        raise package.PackageError('--redact-paths=fail requires --redact')
    package.build(os.path.abspath(args.root), out=args.out, light=args.light,
                  inline=args.inline, summary_file=not args.no_summary_file,
                  stage=args.stage, run=args.run,
                  redact=args.redact, redact_paths=args.redact_paths)
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
                    help='re-render on design_tokens.toml / .bobframes.toml / chrome edits (alpha, 500ms poll)')
    sp.add_argument('--accent', help='one-shot accent color override (oklch token); '
                                     'overrides [theme].accent_primary (ADR-45)')
    sp.add_argument('--accent-data', help='one-shot data-series / heatmap color override; '
                                          'overrides [theme].accent_data')
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
    sp.add_argument('--accent', help='preview an accent color override (oklch token); '
                                     'overrides [theme].accent_primary (ADR-45)')
    sp.add_argument('--accent-data', help='preview a data-series / heatmap color override; '
                                          'overrides [theme].accent_data')
    sp.set_defaults(func=_cmd_preview)

    sp = sub.add_parser('export-tokens', parents=[common],
                        help='print design tokens to stdout as toml|json|css')
    sp.add_argument('--format', choices=['toml', 'json', 'css'], default='toml')
    sp.add_argument('--theme-template', action='store_true',
                    help='print a ready-to-paste [theme] starter block (the overridable color knobs '
                         'with current defaults commented) for .bobframes.toml (ADR-45)')
    sp.set_defaults(func=_cmd_export_tokens)

    sp = sub.add_parser('serve', parents=[common], help='static preview server')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--port', type=int, default=8000)
    sp.add_argument('--bind', default='127.0.0.1')
    sp.set_defaults(func=_cmd_serve)

    sp = sub.add_parser('ui', parents=[common],
                        help='guided local-web control panel (ingest/generate/package in a browser)')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--port', type=int, default=8765)
    sp.add_argument('--bind', default='127.0.0.1',
                    help='bind address; localhost only by design (ADR-47)')
    sp.add_argument('--no-open', action='store_true',
                    help="don't auto-open the browser")
    sp.set_defaults(func=_cmd_ui)

    sp = sub.add_parser('package', parents=[common],
                        help='bundle a rendered tree into a shareable zip + standalone summary')
    sp.add_argument('root', nargs='?', default='.')
    sp.add_argument('--light', action='store_true',
                    help='bundle only index.html + the top-level reports (no drill/_pagedata/_data)')
    sp.add_argument('--inline', action='store_true',
                    help='self-contained per-page bundle (opt out of the deduped shared-assets default)')
    sp.add_argument('--out',
                    help='zip path/name (default: <project>-<rundate>-report.zip beside <root>)')
    sp.add_argument('--no-summary-file', action='store_true',
                    help='skip the standalone <project>-<rundate>-summary.html one-pager')
    sp.add_argument('--stage', action='store_true',
                    help='also materialize the bundle tree to a sibling .stage dir (debug)')
    sp.add_argument('--run',
                    help='package this run key instead of the newest (e.g. 2026-05-28_r110600)')
    sp.add_argument('--redact', action='store_true',
                    help='scrub device/host provenance + absolute paths for external sharing')
    sp.add_argument('--redact-paths', choices=['strip', 'fail'], default='strip',
                    help="abs-path handling under --redact: 'strip' -> <path redacted> (default); "
                         "'fail' exits nonzero if a path remains in any rendered page (CI check)")
    sp.set_defaults(func=_cmd_package)
    # NOTE: no --format and no --accent/--accent-data, ever (ADR-40/45 invariant -- `package` is a
    # PRESENTATION verb: it bundles whatever the render produced. Theme is a RENDER-time concern, so
    # the theme flags belong to `render`/`preview`; argparse rejects them here as unrecognized.)

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
