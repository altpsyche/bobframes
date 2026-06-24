# v029_1 -- write-starter-config button     release: v0.2.9 · phase: ui

> MED finding: when no RenderDoc tool resolves, the panel is a first-run DEAD END -- it shows the
> ToolNotFound message but gives a non-terminal user no way forward. Wire `config.write_config_stub` to a
> button so they get a commented `.bobframes.toml` to edit. Zero new dep; no report HTML (golden untouched).

## Scope
- **`server.py`** -- `POST /api/config/stub` (token-gated) -> `_write_config_stub(root)` calls
  `config.write_config_stub(root)` and returns `{path, written}` (`written` False if it already exists --
  no overwrite).
- **`assets/panel.js` + shell** -- a `tools_fix` block in the RenderDoc-tools section (hidden by default;
  `render()` shows it only when a tool is missing -- `el("tools_fix").hidden = !!allok`) with a
  "Write starter config" button + a `config_msg` line. The button posts `/api/config/stub`, reports the
  written/already-exists path, tells the user to edit the `[tools]` section, and `loadState()`s. `render()`
  only toggles `tools_fix.hidden` (it does not rebuild the block), so the just-written message persists
  (the v028_6 "don't rebuild a region holding a fresh message" lesson).

## Gates / Done when
- `POST /api/config/stub` writes `<root>/.bobframes.toml` (`written: true`, contains `[tools]`); a second
  call returns `written: false` (idempotent, no overwrite); missing token -> 403.
- The button shows only when a tool is missing.
- `node --check bobframes/ui/assets/panel.js` green; the `browser` populate-smoke still green;
  `pytest -m "not browser"` green; `pytest -m golden_env` byte-parity unchanged, NO golden refresh.
- No new runtime dependency.

## As-built (DONE 2026-06-24)
- `server.py`: `POST /api/config/stub` -> `_write_config_stub` -> `config.write_config_stub(root)` ->
  `{path, written}`. `panel.js` + shell: `tools_fix` block (button `#write_config` + `#config_msg`),
  shown via `el("tools_fix").hidden = !!allok` only when a tool is missing; the handler reports the
  written/already-exists path and tells the user to edit `[tools]`.
- VERIFIED: `test_ui_config_stub` (2) -- writes `<root>/.bobframes.toml` (`written: true`, contains
  `[tools]`), second call `written: false` (no overwrite), missing token -> 403. `node --check` clean;
  `-m browser` populate-smoke green (the new block's init wiring does not throw); `-m "not browser"`
  **408 passed / 3 deselected** (was 406 at v029_0; +2); `-m golden_env` **5 passed BYTE-UNCHANGED, NO
  golden refresh**; no new dep.
