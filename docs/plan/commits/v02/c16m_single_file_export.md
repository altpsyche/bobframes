# c16m — single-file static export (ADR-36, phase 4)     release: v0.2

## Goal
Keep the "hand someone one byte-deterministic `.html`" use case after the move to an app folder: a
`DataSink` abstraction lets the SAME view renderers emit either external `<script src>` (the app, c16j-l)
or **inlined** data + CSS + JS + font (a self-contained single file) — the latter exposed as
`bobframes export --single-file <view>` (and/or `render --single-file`).

## Depends on
[c16l](c16l_rehome_reports.md) (views render as fragments via the shared renderers). ADR-36.

## Scope
- **`DataSink`** seam: the renderers ask a sink for "emit this dataset" — the app sink writes
  `_data/<key>.js` + a `<script src>`; the single-file sink inlines `<script type=application/json>` /
  `window.__data` + the CSS/JS/font. One renderer, two modes.
- `export --single-file <view>` emits one self-contained `.html` for a given route (a report / drill /
  the dashboard) = today's format, reproduced from the unified renderer (proves the renderer still works
  standalone — the safety net for the whole epic).
- The shell's `<noscript>` (c16j) links the single-file export so a JS-disabled viewer still has a path.

## Constraints (do not regress)
- The single-file export is **byte-deterministic + offline** (data + assets inlined; no network) and is
  **golden-gated** in its own right (a representative view's single-file output in the golden).
- The app folder and the export must render the SAME content for a view (the fragment renderer is shared);
  guard with a test that the inlined-vs-external emit differ ONLY in the data-loading mechanism.
- `test_parquet_parity` untouched (§21.9); ASCII lint; a11y/print preserved.

## Done when
- `export --single-file` produces a self-contained, offline, byte-deterministic `.html` per view, golden-
  gated; the app folder + export share one renderer via `DataSink`. Golden green; parquet parity unchanged;
  smoke lint clean; browser-verified (double-click the exported file, offline).

## Closes
ADR-36 phase 4. Preserves the standalone-file workflow that the app-folder move would otherwise drop.
