"""v028_7: opt-in headless-browser smoke that the panel JS actually RUNS and populates state.

Marked ``browser`` -- DESELECTED by the default suite (``-m "not browser"``) and only run on demand
(``pytest -m browser``) where a local Chrome exists, mirroring ``test_browser_shots.py`` (ADR-43 gate-d).
This is the gate the v028_6 bug needed and node --check cannot give: ``node --check`` proves the script
PARSES; this proves it RUNS. Chrome loads the LIVE panel over http (token in the URL), the page's
``loadState()`` fetches ``/api/state``, and we assert the DOM populated (root path + tool rows + drops
table) -- i.e. the script parsed AND executed AND wired the fetch->render path.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

from ._ui_util import make_capture_root, running

_TOOLS = pathlib.Path(__file__).resolve().parents[2] / 'tools'
sys.path.insert(0, str(_TOOLS))
import shoot  # noqa: E402  (path injected above; dev-only CDP harness, never shipped)

pytestmark = pytest.mark.browser


def _eval(chrome, expr, *, await_promise=False):
    """Runtime.evaluate in the attached page; returns the by-value result. Raises on a JS exception
    (a thrown panel script is a failure, not a None)."""
    r = chrome.cdp.call('Runtime.evaluate',
                        {'expression': expr, 'returnByValue': True, 'awaitPromise': await_promise},
                        session=chrome.session)
    if 'exceptionDetails' in r:
        raise AssertionError(f'panel JS threw: {r["exceptionDetails"]}')
    return r['result'].get('value')


# An awaited promise that resolves once render() has replaced the "Loading..." placeholder (loadState's
# fetch is async, so it completes AFTER Page.loadEventFired). Times out to a {timeout:true} marker so a
# dead script fails the assert instead of hanging.
_WAIT_POPULATED = """
new Promise(function(resolve){
  var waited = 0, step = 50, deadline = 5000;
  var timer = setInterval(function(){
    var root = document.getElementById('root');
    var ready = root && root.textContent.indexOf('Loading') === -1;
    if (ready) {
      clearInterval(timer);
      resolve({
        root: root.textContent,
        tools: document.getElementById('tools').innerHTML,
        drops: document.getElementById('drops').innerHTML,
        estimate: document.getElementById('ingest_estimate').textContent,
        phaseLive: document.getElementById('phase').getAttribute('aria-live'),
        logTools: !!document.getElementById('copy_run') && !!document.getElementById('dl_run')
      });
    } else if ((waited += step) >= deadline) {
      clearInterval(timer);
      resolve({timeout: true, root: root ? root.textContent : null});
    }
  }, step);
})
"""


def test_panel_js_runs_and_populates_state(tmp_path):
    if not shoot.find_chrome():
        pytest.skip('Chrome not found')
    root = make_capture_root(tmp_path)            # Town + Bay drops with .rdc files
    with running(root) as (httpd, port):
        url = f'http://127.0.0.1:{port}/?t={httpd.bobframes_token}'
        with shoot.Chrome() as chrome:
            s = chrome.session
            chrome.cdp.call('Page.navigate', {'url': url}, session=s)
            chrome.cdp.wait_event('Page.loadEventFired', session=s)
            state = _eval(chrome, _WAIT_POPULATED, await_promise=True)

    assert not state.get('timeout'), f'panel never populated -- the JS did not run: {state!r}'
    # The script parsed, ran, fetched /api/state, and render() filled the DOM:
    assert 'Loading' not in state['root'] and 'proj' in state['root'], state['root']
    assert 'renderdoccmd' in state['tools'], 'tool rows did not render'
    assert 'Town' in state['drops'] or 'Bay' in state['drops'], 'drops table did not render'
    # v029_3: the honest ingest estimate computed in-browser (4 captures x 600s budget -> ~40 min).
    assert '4 capture' in state['estimate'] and 'min' in state['estimate'], state['estimate']
    # v029_4: the aria-live attribute survives to the live DOM (screen-reader announce).
    assert state['phaseLive'] == 'polite', state['phaseLive']
    # v029_7: the log copy/download controls are wired into the live DOM.
    assert state['logTools'] is True


_RUN_CELLS = "JSON.stringify([].slice.call(document.querySelectorAll('#drops tbody tr')).map(function(tr){return tr.children[1].textContent;}))"


def test_run_column_dedupes_shared_run(tmp_path):
    """v029_10: two areas captured in the SAME run show the run key once -- the second row's Run cell is
    blank (the existing populate smoke uses two DISTINCT runs, so it can't exercise the de-dup)."""
    if not shoot.find_chrome():
        pytest.skip('Chrome not found')
    root = tmp_path / 'proj'
    for area in ('Alpha', 'Bravo'):                    # same dated run -> the Run key repeats
        d = root / area / '2026-06-01_r1'
        os.makedirs(d)
        (d / '1.rdc').write_text('', encoding='utf-8')
    with running(str(root)) as (httpd, port):
        url = f'http://127.0.0.1:{port}/?t={httpd.bobframes_token}'
        with shoot.Chrome() as chrome:
            s = chrome.session
            chrome.cdp.call('Page.navigate', {'url': url}, session=s)
            chrome.cdp.wait_event('Page.loadEventFired', session=s)
            _eval(chrome, _WAIT_POPULATED, await_promise=True)
            cells = json.loads(_eval(chrome, _RUN_CELLS))
    assert len(cells) == 2, cells
    assert cells[0] == '2026-06-01_r1' and cells[1] == '', cells   # shown once, then de-duped


def test_narrow_viewport_has_no_horizontal_overflow(tmp_path):
    """v029_12: at a narrow viewport the page must not overflow horizontally (the panel.css breakpoint
    reflows fixed-width inputs + lets a wide table scroll)."""
    if not shoot.find_chrome():
        pytest.skip('Chrome not found')
    root = make_capture_root(tmp_path)
    with running(root) as (httpd, port):
        url = f'http://127.0.0.1:{port}/?t={httpd.bobframes_token}'
        with shoot.Chrome() as chrome:
            s = chrome.session
            chrome.cdp.call('Emulation.setDeviceMetricsOverride',
                            {'width': 480, 'height': 800, 'deviceScaleFactor': 1, 'mobile': False}, session=s)
            chrome.cdp.call('Page.navigate', {'url': url}, session=s)
            chrome.cdp.wait_event('Page.loadEventFired', session=s)
            _eval(chrome, _WAIT_POPULATED, await_promise=True)
            overflow = _eval(chrome, "document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 1, f'horizontal overflow at 480px: scrollWidth - innerWidth = {overflow}'


_FEED_REPLAY = """(function(){
  applyProgress(RUN_T, {line:'replay: 3 captures', phase:'replay', replay_done:0, replay_total:3});
  applyProgress(RUN_T, {line:'  2: rc=0', phase:'replay', replay_done:2, replay_total:3});
  var b = document.getElementById('bar_run');
  return JSON.stringify({hidden: b.hidden, value: b.value, max: b.max});
})()"""


def test_replay_progress_bar_fills(tmp_path):
    """v029_14: feeding scripted replay lines through the real panel JS fills the per-capture progress
    bar (value/max bound to replay_done/replay_total). Drives applyProgress() in a real browser."""
    if not shoot.find_chrome():
        pytest.skip('Chrome not found')
    root = make_capture_root(tmp_path)
    with running(root) as (httpd, port):
        url = f'http://127.0.0.1:{port}/?t={httpd.bobframes_token}'
        with shoot.Chrome() as chrome:
            s = chrome.session
            chrome.cdp.call('Page.navigate', {'url': url}, session=s)
            chrome.cdp.wait_event('Page.loadEventFired', session=s)
            _eval(chrome, _WAIT_POPULATED, await_promise=True)
            bar = json.loads(_eval(chrome, _FEED_REPLAY))
    assert bar['hidden'] is False, 'progress bar stayed hidden during replay'
    assert bar['value'] == 2 and bar['max'] == 3, bar          # 2 of 3 captures replayed
