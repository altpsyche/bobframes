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


def panel_state(root: str) -> dict:
    """The full read-only state the control page renders. Pure: resolves tools + discovers drops +
    enumerates rendered runs (for the A/B picker)."""
    return {
        'root': os.path.abspath(root),
        'platform': sys.platform,
        'windows': sys.platform == 'win32',
        'convention': _CONVENTION,
        'tools': _tool_state(),
        'drops': _drop_state(root),
        'runs': _run_state(root),
    }


# --- control page (server-rendered HTML + vanilla JS; no framework, no build step) --------------

def control_page() -> str:
    """The single control page. ASCII-only; reads the session token from its own URL (``?t=``) and
    fetches ``/api/state`` to render tools + drops. On-brand styling (v028_5): the ``/*TOKENS*/`` marker
    is replaced with ``chrome.design_tokens_css()`` so the panel shares the report's design tokens
    (neutral default theme; the panel chrome is not user-themed -- the REPORT is, via render --accent)."""
    # NOTE: JS lives in a normal <script>; { } in the JS are fine (this is a plain string, not a
    # str.Template). Keep ASCII and avoid backticks-in-Python by building the JS with regular quotes.
    from ..reports import chrome
    return _CONTROL_PAGE.replace('/*TOKENS*/', chrome.design_tokens_css())


# RAW string: the embedded JS contains `"\n"` (and could grow other escapes); a normal string would let
# Python turn that into a real newline mid-JS-literal, breaking the whole <script> parse (v028_2 bug --
# pytest never executed the panel JS so it went unseen until a browser ran it). Keep this r-prefixed.
_CONTROL_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bobframes ui</title>
<style>
/*TOKENS*/
  body { font: var(--fs-body)/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
         max-width: 56rem; margin: var(--sp-10) auto var(--sp-12); padding: 0 var(--sp-4);
         background: var(--bg); color: var(--text-1); }
  h1 { font-size: var(--fs-h1); margin: 0; }
  .sub { color: var(--text-2); margin: var(--sp-1) 0 var(--sp-6); }
  h2 { font-size: var(--fs-h2); margin: 0; }
  .muted { color: var(--text-2); }
  .hint { color: var(--text-2); font-size: var(--fs-small); margin: var(--sp-2) 0 0; }
  .ok { color: var(--status-ok); } .bad { color: var(--status-alarm); }
  .step { border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface-1);
          padding: var(--sp-4) var(--sp-5); margin: var(--sp-4) 0; }
  .step-head { display: flex; align-items: center; gap: var(--sp-3); margin-bottom: var(--sp-3); }
  .badge { margin-left: auto; font-size: var(--fs-micro); text-transform: uppercase; letter-spacing: .04em;
           padding: 2px var(--sp-2); border-radius: var(--radius-sm); border: 1px solid var(--border); color: var(--text-2); }
  .badge.good { color: var(--status-ok); border-color: var(--status-ok); }
  .badge.warn { color: var(--status-alarm); border-color: var(--status-alarm); }
  .actions { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: center; }
  .fields { display: flex; flex-wrap: wrap; gap: var(--sp-3); align-items: baseline; margin-top: var(--sp-3); }
  code { background: var(--code-bg); padding: 2px var(--sp-1); border-radius: var(--radius-sm);
         font: var(--fs-mono)/1.4 ui-monospace, "Cascadia Code", monospace; word-break: break-all; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; padding: var(--sp-1) var(--sp-2); border-bottom: 1px solid var(--border); }
  th { font-size: var(--fs-micro); text-transform: uppercase; letter-spacing: .04em; color: var(--text-2); }
  pre { white-space: pre-wrap; font: var(--fs-mono)/1.45 ui-monospace, "Cascadia Code", monospace;
        color: var(--text-2); background: var(--surface-2); border-radius: var(--radius-sm);
        padding: var(--sp-2); max-height: 16rem; overflow: auto; margin: var(--sp-2) 0 0; }
  label { display: inline-flex; gap: .4rem; align-items: baseline; }
  button { font: inherit; padding: var(--sp-1) var(--sp-3); border-radius: var(--radius-sm);
           border: 1px solid var(--border-strong); background: var(--surface-0); color: var(--text-1);
           cursor: pointer; transition: box-shadow var(--motion-hover); }
  button:hover { box-shadow: var(--elev-2); }
  button:focus-visible { outline: 2px solid var(--accent-data); outline-offset: 2px; }
  button.primary { background: var(--accent-primary); color: var(--bg); border-color: var(--accent-primary); }
  button:disabled { opacity: .45; cursor: not-allowed; box-shadow: none; }
  input, select { font: inherit; padding: var(--sp-1) var(--sp-2); border-radius: var(--radius-sm);
                  border: 1px solid var(--border); background: var(--surface-0); color: var(--text-1); }
  input:focus-visible, select:focus-visible { outline: 2px solid var(--accent-data); outline-offset: 1px; }
  a { color: var(--accent-data); }
  summary { cursor: pointer; color: var(--text-2); font-size: var(--fs-small); }
  details { margin-top: var(--sp-3); }
  .result { border-left: 3px solid var(--accent-data); background: var(--surface-2);
            padding: var(--sp-2) var(--sp-3); border-radius: var(--radius-sm); margin-top: var(--sp-3); }
  .phase { margin: 0; color: var(--text-2); font-size: var(--fs-small); }
  .job { margin-top: var(--sp-3); }
  [hidden] { display: none !important; }
</style>
</head><body>
<h1>bobframes</h1>
<p class="sub">Guided control panel &mdash; turn RenderDoc captures into shareable reports.</p>
<p class="muted" id="root">Loading...</p>

<section class="step">
  <div class="step-head"><h2>RenderDoc tools</h2><span id="tools_badge" class="badge">...</span></div>
  <div id="tools">Loading...</div>
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
    <p id="sc_msg" class="hint"></p>
  </details>
</section>

<section class="step">
  <div class="step-head"><h2>Generate reports</h2></div>
  <div class="actions">
    <button id="ingest" class="primary">Ingest captures</button>
    <button id="render">Rebuild reports only</button>
  </div>
  <p class="hint">Ingest replays every capture (slow; needs RenderDoc). Rebuild reports only re-renders the HTML from data you already ingested (fast, no replay).</p>
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
  <div class="job" id="job_run" hidden><p id="phase" class="phase"></p><pre id="log"></pre></div>
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
  <div id="share_result" class="result" hidden></div>
  <div class="job" id="job_share" hidden><p id="phase_share" class="phase"></p><pre id="log_share"></pre></div>
</section>

<section class="step">
  <div class="step-head"><h2>Compare two runs (A/B)</h2></div>
  <div id="ab_pick" class="actions">
    <label>Baseline <select id="ab_base"></select></label>
    <label>Compare <select id="ab_cmp"></select></label>
    <button id="ab" class="primary">Compare</button>
  </div>
  <p id="ab_hint" class="hint"></p>
  <div id="ab_result" class="result" hidden></div>
  <div class="job" id="job_ab" hidden><p id="phase_ab" class="phase"></p><pre id="log_ab"></pre></div>
</section>
<script>
  var TOKEN = new URLSearchParams(location.search).get("t") || "";
  var RUNS = [];
  var RUN_T = { phase: "phase", log: "log", job: "job_run" };
  var SHARE_T = { phase: "phase_share", log: "log_share", job: "job_share" };
  var AB_T = { phase: "phase_ab", log: "log_ab", job: "job_ab" };
  function esc(s){var d=document.createElement("div");d.textContent=(s==null?"":String(s));return d.innerHTML;}
  function el(id){return document.getElementById(id);}
  function badge(id, good, text){ el(id).className = "badge " + (good ? "good" : "warn"); el(id).textContent = text; }
  function result(id, html){ var r = el(id); r.hidden = false; r.innerHTML = html; }
  function enable(id, ok, why){ el(id).disabled = !ok; el(id).title = ok ? "" : (why || ""); }
  function renderRuns(runs){
    RUNS = runs || [];
    if (RUNS.length < 2) {
      el("ab_pick").hidden = true;
      el("ab_hint").textContent = "Need at least two ingested runs to compare.";
      return;
    }
    el("ab_pick").hidden = false; el("ab_hint").textContent = "";
    var opts = RUNS.map(function(r, i){ return '<option value="'+i+'">'+esc(r.key)+' ('+esc(r.n_captures)+' captures)</option>'; }).join("");
    el("ab_base").innerHTML = opts; el("ab_cmp").innerHTML = opts;
    el("ab_base").selectedIndex = RUNS.length - 2;     // default: prior vs newest
    el("ab_cmp").selectedIndex = RUNS.length - 1;
  }
  function render(s){
    renderRuns(s.runs);
    el("root").innerHTML = "Project root: <code>" + esc(s.root) + "</code>";
    var allok = s.tools.length && s.tools.every(function(x){ return x.found; });
    badge("tools_badge", allok, allok ? "ready" : "missing");
    var t = s.tools.map(function(x){
      return x.found
        ? '<div><span class="ok">OK</span> <strong>'+esc(x.name)+'</strong> <code>'+esc(x.path)+'</code> <span class="muted">'+esc(x.source)+'</span></div>'
        : '<div><span class="bad">missing</span> <strong>'+esc(x.name)+'</strong><pre>'+esc(x.message)+'</pre></div>';
    }).join("");
    el("tools").innerHTML = t || '<p class="muted">none</p>';
    if (s.drops === null) {
      el("drops").innerHTML = '<p class="bad">Folder not found: <code>'+esc(s.root)+'</code></p>';
      badge("drops_badge", false, "no folder");
    } else if (s.drops.length === 0) {
      el("drops").innerHTML = '<p class="muted">No captures found. Expected layout: <code>'+esc(s.convention)+'</code></p>';
      badge("drops_badge", false, "empty");
    } else {
      var rows = s.drops.map(function(d){
        var key = esc(d.date) + (d.label ? "_" + esc(d.label) : "");
        return "<tr><td>"+esc(d.area)+"</td><td>"+key+"</td><td>"+esc(d.n_captures)+" capture(s)</td></tr>";
      }).join("");
      el("drops").innerHTML = "<table><thead><tr><th>Area</th><th>Run</th><th>Captures</th></tr></thead><tbody>"+rows+"</tbody></table>";
      badge("drops_badge", true, s.drops.length + " areas");
    }
    // Only let an action run when its inputs exist: Ingest needs tools + captures; the report actions
    // need data already ingested (a non-empty run list implies a rendered tree).
    var hasCaptures = s.drops && s.drops.length > 0;
    var hasReports = s.runs && s.runs.length > 0;
    enable("ingest", s.windows && allok && hasCaptures,
           !s.windows ? "Windows only (qrenderdoc replay)" : !allok ? "install RenderDoc tools first" : "no captures found in this folder");
    enable("render", hasReports, "nothing ingested yet - run Ingest first");
    enable("open", hasReports, "no report yet - run Ingest first");
    enable("serve", hasReports, "no report yet - run Ingest first");
    enable("package", hasReports, "no report yet - run Ingest first");
  }
  function loadState(){
    fetch("/api/state?t=" + encodeURIComponent(TOKEN))
      .then(function(r){ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
      .then(render)
      .catch(function(e){
        el("root").innerHTML = '<span class="bad">Could not load state ('+esc(e.message)+'). Open the panel via the link printed in the terminal (it carries the session token).</span>';
      });
  }
  function stream(job, t, onDone){
    var es = new EventSource("/api/stream/" + job + "?t=" + encodeURIComponent(TOKEN));
    var log = el(t.log);
    es.onmessage = function(ev){
      var d = JSON.parse(ev.data);
      log.textContent += d.line + "\n"; log.scrollTop = log.scrollHeight;
      var p = d.phase || "running";
      if (d.replay_total) p += "  -  replay " + d.replay_done + "/" + d.replay_total;
      el(t.phase).textContent = p;
    };
    es.addEventListener("done", function(ev){
      var rc = JSON.parse(ev.data).rc;
      el(t.phase).innerHTML = (rc === 0) ? '<span class="ok">done</span>' : '<span class="bad">failed (exit ' + esc(rc) + ')</span>';
      es.close();
      if (onDone) onDone(rc, log.textContent);   // caller surfaces results / refreshes state (per-action)
    });
  }
  function postJSON(path, body){
    return fetch(path + "?t=" + encodeURIComponent(TOKEN), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Bobframes-Token": TOKEN },
      body: JSON.stringify(body || {})
    });
  }
  function startJob(path, body, t, onDone){       // streamed subprocess (ingest / render / package / ab)
    el(t.job).hidden = false; el(t.log).textContent = ""; el(t.phase).textContent = "starting...";
    postJSON(path, body)
      .then(function(r){ if (r.status === 409) throw new Error("a job is already running"); if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function(j){ stream(j.job, t, onDone); })
      .catch(function(e){ el(t.phase).innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; });
  }
  function action(path, body, onok, errId){       // one-shot (open / serve): show the JSON result
    errId = errId || "share_result";
    postJSON(path, body)
      .then(function(r){ return r.json().then(function(j){ if (!r.ok) throw new Error(j.error || ("HTTP " + r.status)); return j; }); })
      .then(onok)
      .catch(function(e){ result(errId, '<span class="bad">' + esc(e.message) + '</span>'); });
  }
  function refreshOnOk(rc){ if (rc === 0) loadState(); }   // re-read tools/drops/runs after a state-changing job
  el("ingest").onclick = function(){
    startJob("/api/ingest", { force: el("force").checked, workers: el("workers").value }, RUN_T, refreshOnOk);
  };
  el("render").onclick = function(){
    startJob("/api/render", { accent: el("accent").value, accent_data: el("accent_data").value }, RUN_T, refreshOnOk);
  };
  el("package").onclick = function(){
    startJob("/api/package", { light: el("pkg_light").checked, redact: el("pkg_redact").checked }, SHARE_T, function(rc, logText){
      if (rc !== 0) return;
      var m = /zip (.+)$/m.exec(logText);
      result("share_result", m ? ('Bundle written: <code>' + esc(m[1].trim()) + '</code> (beside your project folder).')
                                : 'Bundle written beside your project folder.');
    });
  };
  el("open").onclick = function(){ action("/api/open", {}, function(j){ result("share_result", 'Opened <code>' + esc(j.path) + '</code> in your browser.'); }); };
  el("serve").onclick = function(){ action("/api/serve", {}, function(j){ result("share_result", 'Serving at <a href="' + esc(j.url) + '" target="_blank" rel="noopener">' + esc(j.url) + '</a> &mdash; browse the report over http.'); }); };
  el("ab").onclick = function(){
    var b = RUNS[el("ab_base").value], c = RUNS[el("ab_cmp").value];
    if (!b || !c) { el("ab_hint").innerHTML = '<span class="bad">pick a baseline and a compare run</span>'; return; }
    if (b.key === c.key) { el("ab_hint").innerHTML = '<span class="bad">pick two different runs</span>'; return; }
    el("ab_result").hidden = true; el("ab_hint").textContent = "comparing " + b.key + " vs " + c.key + "...";
    var rel = "_reports/ab/" + b.key + "_vs_" + c.key + "/summary.html";
    startJob("/api/ab", { baseline_label: b.label, baseline_date: b.date, compare_label: c.label, compare_date: c.date }, AB_T,
      function(rc){
        if (rc !== 0) return;
        el("ab_hint").textContent = "";
        result("ab_result", esc(b.key) + ' vs ' + esc(c.key) + ' &mdash; <a href="#" id="ab_open">open comparison</a>');
        el("ab_open").onclick = function(e){ e.preventDefault();
          action("/api/open", { path: rel }, function(j){ result("ab_result", 'Opened <code>' + esc(j.path) + '</code> in your browser.'); }, "ab_result"); };
      });
  };
  el("scaffold").onclick = function(){
    el("sc_msg").textContent = "creating...";
    postJSON("/api/scaffold", { area: el("sc_area").value, date: el("sc_date").value, label: el("sc_label").value })
      .then(function(r){ return r.json().then(function(j){ if (!r.ok) throw new Error(j.error || ("HTTP " + r.status)); return j; }); })
      .then(function(j){ el("sc_msg").innerHTML = (j.created ? "Created " : "Already exists: ") + "<code>" + esc(j.path) + "</code>. Drop your .rdc files there, then Ingest."; loadState(); })
      .catch(function(e){ el("sc_msg").innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; });
  };
  loadState();
</script>
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
        if path == '/api/state':
            if not self._has_valid_token(query):
                self._send_json({'error': 'forbidden'}, code=403)
                return
            root = getattr(self.server, 'bobframes_root', '.')
            self._send_json(panel_state(root))
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
                    self.wfile.write(f'event: done\ndata: {json.dumps({"rc": job.rc})}\n\n'.encode('utf-8'))
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
