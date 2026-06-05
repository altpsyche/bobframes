# v0.2.6-0 — redesign tooling + replacement-gate machinery (dev-only)     release: v0.2.6 · phase: redesign

> The FIRST v0.2.6 commit. Builds the gate machinery the visual redesign depends on BEFORE any pixels
> move: the headless-Chrome screenshot harness (gate d), the contrast audit (the dark/print eye the
> golden isn't), and the JS-coupled-class rename guard. **Zero production output change** — no CSS/markup
> edit, no golden refresh. Plan: `~/.claude/plans/bobframes-v0-2-6-visual-enumerated-bachman.md`.

## Goal
Land the replacement-gate infrastructure (ADR-43 gates b/c/d) as dev/test-only code so every later
surface commit has a repeatable browser matrix + an automated contrast/rename check, and the
byte-parity safety net is replaced by a real contract rather than removed.

## Scope
1. **`tools/shoot.py`** — a stdlib-only deterministic headless-Chrome screenshot harness over CDP
   (a minimal RFC-6455 WebSocket client + a tiny request/response loop): captures a `file://` page in
   **light / dark / print** (`Emulation.setEmulatedMedia` prefers-color-scheme + media + reduced-motion),
   full-page via `Page.getLayoutMetrics` + `captureBeyondViewport`. DEV-ONLY: not in the wheel
   (`packages=["bobframes"]`), not imported by the package; PNGs are review artifacts under `c:/tmp`,
   never goldens. Dev-only ⇒ sockets + `os.urandom` masks are fine (the ADR-37 no-random/offline rules
   govern the rendered REPORT, not this tool).
2. **`tests/test_contrast.py`** — dependency-free oklch → linear-sRGB (Ottosson) → WCAG luminance →
   contrast ratio over the design-token `light-dark()` pairs. Converter validated against the WCAG
   reference (black/white = 21.0). Audits fg/text-2 AA both themes; **`--text-3` AA is a STRICT xfail**
   (fails ~3:1 today, flips to a hard XPASS-strict failure the moment v0.2.6-1a fixes it — ADR-23 tracks
   the known gap, does not hide it).
3. **`tests/test_js_coupled_classes.py`** — the do-not-rename guard: the rdc-table engine's structural
   classes/host-attrs (`rdc-table[data-mode`, `col-groups`, `col-group-toggle`, `sort-arrow`,
   `rdc-controls`, `rdc-expand-toggle`, `data-mode/-table/-expand`, `.table-scroll`) must co-occur in
   BOTH `chrome._compose_css()`/`template._compose_css()` AND `chrome._compose_js()`. A redesign rename
   of one side without the other (silent sort/heatmap/columns breakage) goes red.
4. **`browser` pytest marker** (pyproject) — opt-in; deselected by the default `-m "not browser"` suite.
   `tests/test_browser_shots.py` smokes the harness (light/dark/print PNGs; light ≠ dark proves
   prefers-color-scheme emulation — the CDP win over a plain `--screenshot`).

## Constraints
ADR-37 holds for the package (unchanged here — no rendered output touched). The harness/tests add NO
runtime dependency to `bobframes`; `tools/` ships in neither wheel nor sdist.

## Done when
- `tools/shoot.py <tree-or-file>` produces light/dark/print PNGs; verified on the real-Perf tree at
  `c:/tmp/perf` (9 curated captures) and the `-m browser` smoke (light ≠ dark).
- The default suite is GREEN with **NO golden refresh**: `test_parity` + `test_parquet_parity` unchanged
  (no production edit); new tests pass (`--text-3` xfail). As-built: 319 → 326 passed + 1 xfailed.
- `bobframes` import surface unchanged (the package imports nothing from `tools/`).

## As-built (2026-06-05)
Shipped exactly as scoped on `plan/v0.2.6`. The QUALITY_GATES write-up of the full v0.2.6 replacement-gate
set (the browser-matrix protocol + contrast/rename gates as the contract) lands with **v0.2.6-1a** — the
first commit where byte-parity is actually broken and the replacement gates begin to bind; -0 only builds
the machinery (deliberate scoping, ADR-23; recorded here + in STATE). Canonical env confirmed = the repo
`.venv` (py3.12.13 / pyarrow 21.0.0), so goldens bake here via `.venv\Scripts\python.exe`; the py3.14
system Python must NOT bake goldens (ADR-11).

## Closes / next
No FINDINGS row (pure tooling). Next: **v0.2.6-1a** (ADR-44 + token/type/spacing lift; the contrast
xfail flips green and the pinned-byte token tests update in-commit).
