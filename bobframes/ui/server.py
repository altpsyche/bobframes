"""The ``bobframes ui`` server (ADR-47).

A zero-dependency local-web control panel on the stdlib ``http.server`` that DRIVES the existing verbs
for QA / product who are not comfortable in a terminal. It emits no report HTML (golden gate / ADR-37
untouched) and pulls no dependency into core (ADR-17).

v028_0 spine: a localhost ``ThreadingHTTPServer`` that starts/stops cleanly.
v028_1 (this): the generated control page on ``/``, a read-only ``GET /api/state`` (tools + drops), and
the security guard -- localhost bind + a random per-session token required on every ``/api/*`` call.
v028_2: the subprocess job runner + SSE progress + ``POST /api/ingest``.
v028_3: the share & explore actions -- ``POST /api/render`` (re-generate reports, render-only),
``POST /api/package`` (a streamed `bobframes package` job; light / redact toggles), ``POST /api/open``
(open the rendered index in the browser), ``POST /api/serve`` (a background static file server over the
root, reusing ``serve.make_server``).
v028_4 (this): A/B + theming -- ``runs`` added to ``/api/state`` for the picker; ``POST /api/ab`` (a
streamed `bobframes ab` job for a baseline/compare pair); the ``/api/render`` accent / accent-data
overrides (ADR-45); and the opt-in ``POST /api/scaffold`` (create a convention-correct capture folder).

Security (ADR-47): the panel will spawn subprocesses on POST in later commits, so it (a) binds
``127.0.0.1`` only and (b) mints a random per-session token at startup that the auto-opened URL carries
and every ``/api/*`` request must present (else 403). The control page reads the token from its own URL.

Exit codes mirror the CLI (errors.py / ARCHITECTURE §4): 0 clean stop, 1 port unavailable, 4 Ctrl+C.
"""
from __future__ import annotations

import http.server
import json
import logging
import os
import queue
import re
import secrets
import sys
import threading
import webbrowser
from importlib.resources import files as _files
from urllib.parse import parse_qs, urlparse

from .. import errors
from . import jobs, progress

_logger = logging.getLogger('bobframes')

# The capture-folder convention surfaced to the user when no drops are found (matches discovery).
_CONVENTION = '<Area>/<YYYY-MM-DD[_label]>/*.rdc'
# Strict ISO date for the opt-in scaffold (matches the discovery default dated_re's date group).
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# Characters never allowed in a user-supplied area / label name (path traversal / drive / ADS guard).
_NAME_BAD = ('/', '\\', '..', ':')


# --- read-only state (in-process; no side effects) ---------------------------------------------

def _tool_state() -> list[dict]:
    """Resolve the external tools exactly as `bobframes check` does (cli._cmd_check)."""
    from .. import config
    from ..errors import ToolNotFound
    out: list[dict] = []
    for name in ('renderdoccmd', 'qrenderdoc'):
        try:
            path, source = config.resolve_tool_verbose(name)
            out.append({'name': name, 'found': True, 'path': os.path.normpath(path),  # tidy mixed / \ for display
                        'source': '' if source == path else source})
        except ToolNotFound as e:
            out.append({'name': name, 'found': False, 'message': e.format_message()})
    return out


def _drop_state(root: str) -> list[dict] | None:
    """Discovered drops via discovery.find_drops (one per area, newest). None if the root is missing."""
    from .. import discovery
    try:
        drops = discovery.find_drops(root)
    except FileNotFoundError:
        return None
    return [{'area': d.area, 'date': d.drop_date, 'label': d.drop_label,
             'captures': list(d.captures), 'n_captures': len(d.captures)} for d in drops]


def _run_state(root: str) -> list[dict]:
    """Rendered runs (DropSets from the catalog) for the A/B picker; [] before any ingest/render."""
    from ..reports import discovery as rdisc
    try:
        return [{'key': d.key, 'label': d.label, 'date': d.date, 'n_captures': d.n_captures}
                for d in rdisc.discover_drops(root)]
    except Exception:
        return []


def _replay_timeout_s(root: str) -> float:
    """The per-capture qrenderdoc replay budget for the honest ingest estimate (v029_3). Read from the
    resolved config for this root (``cfg.pipeline.replay_timeout_s``) via the non-mutating builder so the
    panel never disturbs the global ``config._ACTIVE`` singleton; falls back to the documented default."""
    from .. import config
    try:
        return float(config._build_config(root).pipeline.replay_timeout_s)
    except Exception:
        return 600.0


def panel_state(root: str) -> dict:
    """The full read-only state the control page renders. Pure: resolves tools + discovers drops +
    enumerates rendered runs (for the A/B picker) + the per-capture replay budget (for the estimate)."""
    return {
        'root': os.path.abspath(root),
        'platform': sys.platform,
        'windows': sys.platform == 'win32',
        'convention': _CONVENTION,
        'tools': _tool_state(),
        'drops': _drop_state(root),
        'runs': _run_state(root),
        'replay_timeout_s': _replay_timeout_s(root),
    }


# --- control page (server-rendered HTML shell; static JS/CSS served from assets/) ----------------

def _asset(name: str) -> str:
    """Read a packaged static asset (``bobframes/ui/assets/<name>``) the same way the report chrome
    reads its own (importlib.resources), so it resolves whether running from source or an installed
    wheel -- the wheel ships ``bobframes/ui/assets/*`` via ``packages=["bobframes"]`` (recursive; ADR-10,
    no pyproject change)."""
    return _files('bobframes.ui').joinpath('assets', name).read_text(encoding='utf-8')


def panel_js() -> str:
    """The control-panel client JS, served at ``GET /panel.js`` (v028_8: externalized from the page so a
    real ``.js`` file is ``node --check`` / lint-able and the v028_2 ``\\n``-in-an-r-string bug class --
    a ``"\\n"`` turned into a real newline mid-JS-literal -- is structurally impossible)."""
    return _asset('panel.js')


def panel_css() -> str:
    """The control-panel static CSS, served at ``GET /panel.css``. The ``:root`` design tokens are NOT
    here -- ``control_page()`` injects them inline (the only dynamic, theme-derived CSS); this is the
    static half, every rule referencing those token vars."""
    return _asset('panel.css')


def control_page() -> str:
    """The control-page shell: server-rendered HTML + a tiny inline ``<style>`` carrying the design
    tokens (``chrome.design_tokens_css()`` -- the only dynamic, theme-derived CSS; neutral default theme,
    the panel chrome is not user-themed -- the REPORT is, via render --accent), linking the static
    ``/panel.css`` and ``/panel.js``. No JS is embedded in this Python string, so the v028_2 bug class is
    structurally impossible (the JS lives in a real file -- see ``panel_js``)."""
    from ..reports import chrome
    return _SHELL.replace('/*TOKENS*/', chrome.design_tokens_css())


# Raw string: this shell is HTML only (no embedded JS), but kept r-prefixed so a literal backslash in
# any attribute (e.g. a Windows-path placeholder) is never mangled into a Python escape -- the same
# v028_2 lesson that moved the JS out. The token marker is substituted by control_page(); the bulk CSS
# + all JS are served as static files (/panel.css, /panel.js).
_SHELL = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bobframes ui</title>
<style>/*TOKENS*/</style>
<link rel="stylesheet" href="/panel.css">
</head><body>
<h1>bobframes</h1>
<p class="sub">Guided control panel &mdash; turn RenderDoc captures into shareable reports.</p>
<p class="muted" id="root">Loading...</p>
<div class="fields">
  <label>Project folder <input id="root_input" placeholder="C:/path/to/captures" style="width:24rem"></label>
  <button id="set_root">Open folder</button>
</div>
<p id="root_msg" class="hint" aria-live="polite"></p>

<section class="step">
  <div class="step-head"><h2>RenderDoc tools</h2><span id="tools_badge" class="badge">...</span></div>
  <div id="tools">Loading...</div>
  <div id="tools_fix" hidden>
    <p class="hint">No RenderDoc tool found. Write a starter <code>.bobframes.toml</code> here, then edit its <code>[tools]</code> section to point at your RenderDoc install (or add RenderDoc to your PATH).</p>
    <button id="write_config">Write starter config</button>
    <p id="config_msg" class="hint" aria-live="polite"></p>
  </div>
</section>

<section class="step">
  <div class="step-head"><h2>Captures</h2><span id="drops_badge" class="badge">...</span></div>
  <div id="drops">Loading...</div>
  <details><summary>Create a capture folder</summary>
    <div class="fields">
      <label>area <input id="sc_area" placeholder="Town" style="width:9rem"></label>
      <label>date <input id="sc_date" placeholder="2026-06-24" style="width:9rem"></label>
      <label>label <input id="sc_label" placeholder="r110600 (optional)" style="width:11rem"></label>
      <button id="scaffold">Create folder</button>
    </div>
    <p id="sc_msg" class="hint" aria-live="polite"></p>
  </details>
</section>

<section class="step">
  <div class="step-head"><h2>Generate reports</h2></div>
  <div class="actions">
    <button id="ingest" class="primary">Ingest captures</button>
    <button id="render">Rebuild reports only</button>
  </div>
  <p class="hint">Ingest replays every capture (slow; needs RenderDoc). Rebuild reports only re-renders the HTML from data you already ingested (fast, no replay).</p>
  <p class="hint" id="ingest_estimate"></p>
  <details><summary>Options</summary>
    <div class="fields">
      <label><input type="checkbox" id="force"> Force re-ingest (rebuild from captures)</label>
      <label>Workers <input type="number" id="workers" min="1" style="width:4rem"></label>
    </div>
    <div class="fields">
      <label>Accent color <input id="accent" placeholder="oklch(0.55 0.2 250)" style="width:15rem"></label>
      <label>Data accent <input id="accent_data" placeholder="optional" style="width:11rem"></label>
    </div>
    <p class="hint">Accent colors re-hue the report; applied by "Rebuild reports only".</p>
  </details>
  <div class="job" id="job_run" hidden><div class="actions"><p id="phase" class="phase" aria-live="polite"></p><button id="cancel_run" style="margin-left:auto" hidden>Cancel</button></div><pre id="log"></pre></div>
</section>

<section class="step">
  <div class="step-head"><h2>Share &amp; explore</h2></div>
  <div class="actions">
    <button id="open" class="primary">Open report</button>
    <button id="serve">Serve over http</button>
    <button id="package">Package for sharing</button>
  </div>
  <div class="fields">
    <label><input type="checkbox" id="pkg_light"> Light bundle (index + top reports only)</label>
    <label><input type="checkbox" id="pkg_redact"> Redact (scrub provenance + paths)</label>
  </div>
  <div id="share_result" class="result" hidden aria-live="polite"></div>
  <div class="job" id="job_share" hidden><div class="actions"><p id="phase_share" class="phase" aria-live="polite"></p><button id="cancel_share" style="margin-left:auto" hidden>Cancel</button></div><pre id="log_share"></pre></div>
</section>

<section class="step">
  <div class="step-head"><h2>Compare two runs (A/B)</h2></div>
  <div id="ab_pick" class="actions">
    <label>Baseline <select id="ab_base"></select></label>
    <label>Compare <select id="ab_cmp"></select></label>
    <button id="ab" class="primary">Compare</button>
  </div>
  <p id="ab_hint" class="hint" aria-live="polite"></p>
  <div id="ab_result" class="result" hidden aria-live="polite"></div>
  <div class="job" id="job_ab" hidden><div class="actions"><p id="phase_ab" class="phase" aria-live="polite"></p><button id="cancel_ab" style="margin-left:auto" hidden>Cancel</button></div><pre id="log_ab"></pre></div>
</section>
<script src="/panel.js"></script>
</body></html>
"""


# --- HTTP handler ------------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    """Serves the control page on ``/``, the token-gated read-only ``/api/state``, the SSE job stream,
    and the token-gated POST actions (ingest / render / package / ab jobs + open / serve / scaffold)."""

    server_version = 'bobframes-ui'
    protocol_version = 'HTTP/1.1'

    def _has_valid_token(self, query: dict) -> bool:
        want = getattr(self.server, 'bobframes_token', '')
        got = (self.headers.get('X-Bobframes-Token')
               or (query.get('t', [''])[0] if query else ''))
        return bool(want) and bool(got) and secrets.compare_digest(str(got), str(want))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode('utf-8'), 'application/json; charset=utf-8')

    def do_GET(self) -> None:  # noqa: N802 (stdlib handler contract)
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path in ('/', '/index.html'):
            self._send(200, control_page().encode('utf-8'), 'text/html; charset=utf-8')
            return
        if path == '/panel.js':         # static client (no token: holds no secret; carries no state)
            self._send(200, panel_js().encode('utf-8'), 'text/javascript; charset=utf-8')
            return
        if path == '/panel.css':
            self._send(200, panel_css().encode('utf-8'), 'text/css; charset=utf-8')
            return
        if path == '/api/state':
            if not self._has_valid_token(query):
                self._send_json({'error': 'forbidden'}, code=403)
                return
            root = getattr(self.server, 'bobframes_root', '.')
            self._send_json(panel_state(root))
            return
        if path == '/api/ab/reports':
            if not self._has_valid_token(query):
                self._send_json({'error': 'forbidden'}, code=403)
                return
            self._ab_reports(getattr(self.server, 'bobframes_root', '.'), query)
            return
        if path.startswith('/api/stream/'):
            if not self._has_valid_token(query):           # EventSource can only auth via the query
                self._send_json({'error': 'forbidden'}, code=403)
                return
            job = self.server.bobframes_jobs.get(path[len('/api/stream/'):])  # type: ignore[attr-defined]
            if job is None:
                self.send_error(404, 'no such job')
                return
            self._stream(job)
            return
        self.send_error(404, 'not found')

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if not self._has_valid_token(query):
            self._send_json({'error': 'forbidden'}, code=403)
            return
        root = self.server.bobframes_root  # type: ignore[attr-defined]
        if path == '/api/ingest':
            opts = self._ingest_opts(self._read_json_body())
            self._start_job(lambda: jobs.spawn(jobs.build_run_argv(root, **opts)))
            return
        if path == '/api/render':
            # Re-generate reports from existing parquet (render-only -> no GPU / replay), optionally
            # re-hued by the one-shot accent / accent-data overrides (ADR-45).
            opts = self._render_opts(self._read_json_body())
            self._start_job(lambda: jobs.spawn(jobs.build_render_argv(root, **opts)))
            return
        if path == '/api/package':
            opts = self._package_opts(self._read_json_body())
            self._start_job(lambda: jobs.spawn_cli(jobs.build_package_argv(root, **opts)))
            return
        if path == '/api/ab':
            opts = self._ab_opts(self._read_json_body())
            if not opts['baseline_label'] or not opts['compare_label']:
                self._send_json({'error': 'baseline and compare runs are required'}, code=400)
                return
            self._start_job(lambda: jobs.spawn_cli(jobs.build_ab_argv(root, **opts)))
            return
        if path == '/api/open':
            self._open_report(root, self._str_or_none(self._read_json_body().get('path')))
            return
        if path == '/api/serve':
            self._serve_static(root, self._read_json_body())
            return
        if path == '/api/scaffold':
            self._scaffold(root, self._read_json_body())
            return
        if path == '/api/config/stub':
            self._write_config_stub(root)
            return
        if path == '/api/root':
            self._set_root(self._read_json_body())
            return
        if path.startswith('/api/cancel/'):
            self._cancel_job(path[len('/api/cancel/'):])
            return
        self.send_error(404, 'not found')

    # --- job helpers ---------------------------------------------------------------------------

    def _read_json_body(self) -> dict:
        n = int(self.headers.get('Content-Length') or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return {}

    @staticmethod
    def _ingest_opts(body: dict) -> dict:
        """Coerce the POST body into build_run_argv kwargs (defensive: never trust the client)."""
        workers = body.get('workers')
        return {
            'force': bool(body.get('force')),
            'render_only': bool(body.get('render_only')),
            'workers': int(workers) if str(workers or '').isdigit() else None,
            'pixel_grid': int(body['pixel_grid']) if str(body.get('pixel_grid') or '').isdigit() else 4,
        }

    @staticmethod
    def _package_opts(body: dict) -> dict:
        """Coerce the POST body into build_package_argv kwargs (the friendly light / redact toggles)."""
        return {'light': bool(body.get('light')), 'redact': bool(body.get('redact'))}

    @staticmethod
    def _str_or_none(v) -> str | None:
        """A trimmed non-empty string, else None (so a blank UI field becomes 'flag omitted')."""
        return v.strip() if isinstance(v, str) and v.strip() else None

    def _render_opts(self, body: dict) -> dict:
        """Coerce the POST body into build_render_argv kwargs (the one-shot accent overrides)."""
        return {'accent': self._str_or_none(body.get('accent')),
                'accent_data': self._str_or_none(body.get('accent_data'))}

    def _ab_opts(self, body: dict) -> dict:
        """Coerce the POST body into build_ab_argv kwargs (the A/B picker's baseline + compare runs)."""
        return {'baseline_label': self._str_or_none(body.get('baseline_label')),
                'compare_label': self._str_or_none(body.get('compare_label')),
                'baseline_date': self._str_or_none(body.get('baseline_date')),
                'compare_date': self._str_or_none(body.get('compare_date'))}

    def _start_job(self, make_proc) -> None:
        """Start a streamed subprocess job from a zero-arg proc factory. One job at a time (single-user
        panel); the factory runs only AFTER the busy check, so a 409 never spawns a process."""
        registry = self.server.bobframes_jobs                # type: ignore[attr-defined]
        if any(j.running() for j in registry.values()):
            self._send_json({'error': 'busy'}, code=409)
            return
        job = jobs.Job(make_proc())
        jid = secrets.token_urlsafe(6)
        registry[jid] = job
        self._send_json({'job': jid}, code=202)

    def _cancel_job(self, jid: str) -> None:
        """Stop a running job from the UI (the v029_0 Cancel button). Terminates the spawned verb
        process via ``jobs.Job.cancel()``; the stream then emits its terminal event with ``cancelled``
        set so the panel reads 'cancelled' rather than 'failed'. 404 if there is no such job."""
        job = self.server.bobframes_jobs.get(jid)              # type: ignore[attr-defined]
        if job is None:
            self._send_json({'error': 'no such job'}, code=404)
            return
        job.cancel()
        self._send_json({'ok': True, 'cancelled': True})

    def _open_report(self, root: str, rel: str | None = None) -> None:
        """Open a rendered page in the user's default browser (in-process; the panel runs on the user's
        own machine -- ADR-47 localhost). ``rel`` (a path relative to root, e.g. an A/B pair's
        ``_reports/ab/<pair>/summary.html``) is validated to stay inside root; default is the root
        index. 400 on a traversal attempt, 409 if the target is not rendered yet."""
        from .. import paths
        if rel:
            target = os.path.normpath(os.path.join(root, rel))
            if target != root and not target.startswith(root + os.sep):
                self._send_json({'error': 'path escapes the project root'}, code=400)
                return
        else:
            target = paths.root_index_html(root)
        if not os.path.exists(target):
            self._send_json({'error': 'not rendered yet; run ingest / render / a-b first', 'path': target},
                            code=409)
            return
        webbrowser.open(target)
        self._send_json({'ok': True, 'path': target})

    def _ab_reports(self, root: str, query: dict) -> None:
        """List every report in an A/B pair's output dir ``_reports/ab/<base>_vs_<cmp>/`` (v029_5) so the
        panel can link them all, not just summary.html. Returns ``{reports: [{name, rel}]}`` (rel is a
        root-relative path the traversal-guarded ``/api/open`` accepts). The run keys form a directory
        name, so they are guarded against separators / ``..`` (400); an un-rendered pair -> empty list."""
        base = (query.get('base', [''])[0] or '').strip()
        cmp_ = (query.get('cmp', [''])[0] or '').strip()
        if not base or not cmp_ or any(b in (base + cmp_) for b in _NAME_BAD):
            self._send_json({'error': 'valid base and cmp run keys are required'}, code=400)
            return
        rel_dir = f'_reports/ab/{base}_vs_{cmp_}'
        abs_dir = os.path.normpath(os.path.join(root, rel_dir))
        if abs_dir != root and not abs_dir.startswith(root + os.sep):   # belt-and-suspenders
            self._send_json({'error': 'invalid pair'}, code=400)
            return
        reports = []
        if os.path.isdir(abs_dir):
            for name in sorted(os.listdir(abs_dir)):
                if name.endswith('.html'):
                    reports.append({'name': name[:-len('.html')], 'rel': f'{rel_dir}/{name}'})
        self._send_json({'reports': reports})

    def _serve_static(self, root: str, body: dict) -> None:
        """Start (once) a background static file server over ``<root>`` so the report can be browsed over
        http (not file://). Idempotent: a second call returns the already-running server's URL. Default
        ephemeral port (0) so it never collides with the panel or a stale serve; a body ``port`` pins it."""
        existing = getattr(self.server, 'bobframes_serve', None)  # type: ignore[attr-defined]
        if existing is not None:
            self._send_json(existing)
            return
        from .. import serve as _serve
        port = int(body['port']) if str(body.get('port') or '').isdigit() else 0
        try:
            httpd = _serve.make_server(root, port=port)
        except OSError as e:
            self._send_json({'error': f'cannot serve ({e.strerror or e})'}, code=409)
            return
        actual = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        info = {'url': f'http://127.0.0.1:{actual}/', 'port': actual}
        self.server.bobframes_serve = info             # type: ignore[attr-defined]
        self.server.bobframes_serve_httpd = httpd      # type: ignore[attr-defined]
        self._send_json(info)

    def _set_root(self, body: dict) -> None:
        """Repoint the panel at another folder without relaunching from a terminal (the v029_2 root
        input). Validates the path is an existing directory, updates the server's active root, and
        returns fresh state so the client can re-render. Single-user local action (ADR-47 localhost +
        token); 400 on a missing / non-directory path. A job already running keeps its original root
        (its argv was fixed at spawn)."""
        new = body.get('path')
        if not isinstance(new, str) or not new.strip():
            self._send_json({'error': 'path is required'}, code=400)
            return
        new = os.path.abspath(new.strip())
        if not os.path.isdir(new):
            self._send_json({'error': f'not a folder: {new}'}, code=400)
            return
        self.server.bobframes_root = new       # type: ignore[attr-defined]
        self._send_json(panel_state(new))

    def _write_config_stub(self, root: str) -> None:
        """Write a starter ``.bobframes.toml`` to ``root`` (the v029_1 first-run helper when a RenderDoc
        tool is missing -- a config dead end today). Idempotent: ``written`` is False if it already
        exists (no overwrite). The user then edits its ``[tools]`` section to point at their install."""
        from .. import config
        path, written = config.write_config_stub(root)
        self._send_json({'path': path, 'written': written})

    def _scaffold(self, root: str, body: dict) -> None:
        """Opt-in: create a convention-correct empty capture folder ``<root>/<area>/<date[_label]>/`` so
        a non-terminal user gets the layout exactly right, then drops their ``.rdc`` files in. Names are
        validated against path traversal (no separators / ``..`` / ``:``); the date must be ISO."""
        from .. import paths
        area = str(body.get('area') or '').strip()
        date = str(body.get('date') or '').strip()
        label = str(body.get('label') or '').strip()
        if not area or any(b in area for b in _NAME_BAD) or any(b in label for b in _NAME_BAD):
            self._send_json({'error': 'area is required; area/label cannot contain path separators'}, code=400)
            return
        if not _DATE_RE.match(date):
            self._send_json({'error': 'date must be YYYY-MM-DD'}, code=400)
            return
        target = os.path.join(root, area, paths.drop_dirname(date, label))
        created = not os.path.exists(target)
        os.makedirs(target, exist_ok=True)
        self._send_json({'created': created, 'path': target})

    def _stream(self, job: jobs.Job) -> None:
        """Server-Sent Events: relay the job's stdout (classified) until DONE; final `done` event
        carries the return code. No Content-Length (streamed); connection closes at end."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        cls = progress.Classifier()
        try:
            while True:
                try:
                    item = job.q.get(timeout=1.0)
                except queue.Empty:
                    self.wfile.write(b': keepalive\n\n')    # keep the slow 600s replay connection warm
                    self.wfile.flush()
                    continue
                if item is jobs.DONE:
                    self.wfile.write(f'event: done\ndata: {json.dumps({"rc": job.rc, "cancelled": job.cancelled})}\n\n'.encode('utf-8'))
                    self.wfile.flush()
                    return
                self.wfile.write(f'data: {json.dumps(cls.feed(item))}\n\n'.encode('utf-8'))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return                                            # client navigated away; the job keeps running

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        _logger.debug('ui: %s - %s', self.address_string(), fmt % args)


# --- server lifecycle --------------------------------------------------------------------------

def build_server(root: str, *, bind: str = '127.0.0.1', port: int = 8765) -> http.server.ThreadingHTTPServer:
    """Build (do not start) the panel server. Localhost-only bind (ADR-47). Mints a per-session token
    and stashes it + the abspath root on the server for the handlers. ``port=0`` binds an ephemeral
    port (used by tests; read it back from ``server_address[1]``)."""
    httpd = http.server.ThreadingHTTPServer((bind, port), _Handler)
    httpd.daemon_threads = True
    httpd.bobframes_root = os.path.abspath(root)         # type: ignore[attr-defined]
    httpd.bobframes_token = secrets.token_urlsafe(32)    # type: ignore[attr-defined]
    httpd.bobframes_jobs = {}                            # type: ignore[attr-defined]  id -> jobs.Job
    httpd.bobframes_serve = None                         # type: ignore[attr-defined]  {url, port} once started
    httpd.bobframes_serve_httpd = None                  # type: ignore[attr-defined]  the background static server
    return httpd


def _shutdown_aux(httpd: http.server.ThreadingHTTPServer) -> None:
    """Stop the panel's background static serve (if `/api/serve` ever started one) so the panel and its
    helper both release their ports on shutdown."""
    aux = getattr(httpd, 'bobframes_serve_httpd', None)
    if aux is not None:
        aux.shutdown()
        aux.server_close()


def serve(root: str, *, bind: str = '127.0.0.1', port: int = 8765, open_browser: bool = True) -> int:
    """Start the panel and block until Ctrl+C. Returns a CLI exit code."""
    root = os.path.abspath(root)
    try:
        httpd = build_server(root, bind=bind, port=port)
    except OSError as e:
        _logger.error(f'ui: cannot bind {bind}:{port} ({e.strerror or e}); try a different --port')
        return errors.EXIT_FAILURE

    # The token rides in the opened URL; every /api/* call must present it (ADR-47).
    url = f'http://{bind}:{port}/?t={httpd.bobframes_token}'  # type: ignore[attr-defined]
    with httpd:
        _logger.info(f'ui: serving {root} at {url} (Ctrl+C to stop)')
        if open_browser:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return errors.EXIT_INTERRUPTED
        finally:
            _shutdown_aux(httpd)
            httpd.shutdown()
    return errors.EXIT_OK
