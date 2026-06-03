# c16m — controllable cell truncation + hover-reveal on `rdc-table`     release: v0.2 · phase: De-hardcoding

> **ADR-38.** Third of three. Lands on the ONE `rdc-table` component (built in c16k, rolled out in c16l), so
> truncation behaves identically across every report + the catalog/drill in one place.

## Goal
Long cell values (shader src paths, mesh hashes, marker strings, labels) currently either blow column width
or wrap raggedly, hurting the dense-table scan. Make truncation **controllable** and always recoverable: clip
to a per-column max width with an ellipsis, and reveal the full value on hover via a native `title=` tooltip
(zero-JS, Ctrl-F-safe, works in both `static` and `virtual` modes).

## Depends on
`c16k` + `c16l` (the unified `rdc-table` component — truncation lands once, both modes). ADR-38.

## Scope
1. **Default: truncate + hover-reveal.** Cells clip with `text-overflow: ellipsis` at a per-column max width;
   the full text is exposed via the cell's `title=` attribute (server-set in `static` mode so it survives
   JS-off + print; set on the windowed cell in `virtual` mode, re-applied as rows recycle). Native tooltip,
   no JS popover, no banned unicode (ASCII ellipsis behaviour via CSS, not a literal U+2026 in text).
2. **Controllable.** A per-column max-width (sensible default; wider for known-long columns like src paths),
   plus a **global expand/wrap toggle** on the table (a real `<button aria-pressed>`) that switches between
   truncated and full-wrap views. Deterministic; state is client-only (no effect on the server-baked bytes
   beyond the static `title=` + the toggle markup).
3. **Both modes, one code path.** The truncation CSS/markup lives on `rdc-table` so reports and the
   catalog/drill share it. In `virtual` mode, truncation + `title=` re-apply on the recycled windowed rows.
4. **Don't break copy/links.** `rdc-copy-button` payloads + in-cell links keep the FULL value (truncation is
   display-only); the copyable/linked value is never the clipped text (c16c contract).

## Constraints (do not regress)
- **`static` mode stays golden-visible + JS-optional + printable + Ctrl-F-able:** the `title=` + the clip CSS
  are server-rendered; JS-off still shows clipped cells with working hover tooltips and full text via Ctrl-F
  (Ctrl-F matches the real `<td>` text, not the visual clip). Print shows either the wrapped full text or the
  clipped form per a print rule — decide in review (recommend full-wrap in print so nothing is hidden on
  paper).
- Offline + byte-deterministic (no `random`/`Date`), ASCII lint; `test_parquet_parity` untouched (§21.9).
- Copy/link payloads = full value (never the truncated display).

## Done when
- Long cells clip with an ellipsis at a controllable per-column width; hovering reveals the full value via
  `title=`; a global expand/wrap toggle works; copy-buttons + links still carry the full value.
- Works in BOTH modes (a report + the heaviest drill); `static` mode verified JS-off (clip + tooltip + Ctrl-F
  on the full text) and in print.
- Golden refreshed + reviewed; `test_parity` green; `test_parquet_parity` green with no digests refresh;
  `bobframes smoke` lint clean exit 0; browser-verified offline (light + dark; real Perf: a long src-path
  column truncates + reveals on hover).
- `test_report_structure` gains a c16m guard: truncatable columns carry `title=` (static, server-rendered),
  the expand/wrap toggle is a real `<button aria-pressed>`, copy/link payloads are the full value.

## Closes
Cell-truncation/readability for the unified table. Completes the c16k–c16m table-unification epic;
finalize QUALITY_GATES §21.1m (the `rdc-table` contract incl. truncation).
