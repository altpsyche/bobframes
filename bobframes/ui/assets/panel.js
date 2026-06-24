// bobframes ui -- control-panel client (v028_8).
// Served verbatim at GET /panel.js (vanilla JS, no framework / router / build step -- ADR-47). It reads
// the session token from its own page URL (?t=) and drives the token-gated /api/* surface. Living in a
// real .js file (not embedded in a Python string) is the structural fix for the v028_2 bug class -- the
// `"\n"` escape below can never again be turned into a real newline mid-literal, and node --check / lint
// validate it directly (tests/test_ui_js_parses.py + the ci.yml node --check step).
  var TOKEN = new URLSearchParams(location.search).get("t") || "";
  var RUNS = [];
  var RUN_T = { phase: "phase", log: "log", job: "job_run", cancel: "cancel_run" };
  var SHARE_T = { phase: "phase_share", log: "log_share", job: "job_share", cancel: "cancel_share" };
  var AB_T = { phase: "phase_ab", log: "log_ab", job: "job_ab", cancel: "cancel_ab" };
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
    el("tools_fix").hidden = !!allok;     // offer the starter-config helper only when a tool is missing
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
      var d = JSON.parse(ev.data), rc = d.rc;
      el(t.phase).innerHTML = d.cancelled ? '<span class="muted">cancelled</span>'
                            : (rc === 0) ? '<span class="ok">done</span>'
                            : '<span class="bad">failed (exit ' + esc(rc) + ')</span>';
      if (t.cancel) el(t.cancel).hidden = true;
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
    if (t.cancel) el(t.cancel).hidden = true;     // shown once we have a job id to cancel
    postJSON(path, body)
      .then(function(r){ if (r.status === 409) throw new Error("a job is already running"); if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function(j){ t.jobId = j.job; if (t.cancel) { el(t.cancel).hidden = false; el(t.cancel).disabled = false; } stream(j.job, t, onDone); })
      .catch(function(e){ el(t.phase).innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; });
  }
  function cancelJob(t){                           // stop the running job (POST /api/cancel/<job>)
    if (!t.jobId) return;
    el(t.cancel).disabled = true; el(t.phase).textContent = "cancelling...";
    // the stream's terminal 'done' (cancelled) sets the final phase + hides the button; re-enable on error.
    postJSON("/api/cancel/" + t.jobId, {}).catch(function(){ el(t.cancel).disabled = false; });
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
  el("cancel_run").onclick = function(){ cancelJob(RUN_T); };
  el("cancel_share").onclick = function(){ cancelJob(SHARE_T); };
  el("cancel_ab").onclick = function(){ cancelJob(AB_T); };
  el("set_root").onclick = function(){           // repoint the panel at another folder (POST /api/root)
    var p = el("root_input").value;
    if (!p) { el("root_msg").innerHTML = '<span class="bad">enter a folder path</span>'; return; }
    el("root_msg").textContent = "opening...";
    postJSON("/api/root", { path: p })
      .then(function(r){ return r.json().then(function(j){ if (!r.ok) throw new Error(j.error || ("HTTP " + r.status)); return j; }); })
      .then(function(s){ el("root_msg").textContent = ""; el("root_input").value = ""; render(s); })   // server returns fresh state
      .catch(function(e){ el("root_msg").innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; });
  };
  el("write_config").onclick = function(){
    el("config_msg").textContent = "writing...";
    postJSON("/api/config/stub", {})
      .then(function(r){ return r.json().then(function(j){ if (!r.ok) throw new Error(j.error || ("HTTP " + r.status)); return j; }); })
      .then(function(j){
        el("config_msg").innerHTML = (j.written ? "Wrote " : "Already exists: ") + "<code>" + esc(j.path)
          + "</code>. Edit its [tools] section to point at your RenderDoc, then reload this page.";
        loadState();   // re-resolve (tools stay missing until the user edits the stub; config_msg persists)
      })
      .catch(function(e){ el("config_msg").innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; });
  };
  loadState();
