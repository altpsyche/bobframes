"""v028_7: opt-in headless-browser smoke that the panel JS actually RUNS and populates state.

Marked ``browser`` -- DESELECTED by the default suite (``-m "not browser"``) and only run on demand
(``pytest -m browser``) where a local Chrome exists, mirroring ``test_browser_shots.py`` (ADR-43 gate-d).
This is the gate the v028_6 bug needed and node --check cannot give: ``node --check`` proves the script
PARSES; this proves it RUNS. Chrome loads the LIVE panel over http (token in the URL), the page's
``loadState()`` fetches ``/api/state``, and we assert the DOM populated (root path + tool rows + drops
table) -- i.e. the script parsed AND executed AND wired the fetch->render path.
"""
from __future__ import annotations

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
        estimate: document.getElementById('ingest_estimate').textContent
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
