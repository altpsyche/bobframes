# Vendored font asset (c16d, ADR-34)

`inter-subset.woff2` is a **subset** of the Inter typeface, baked into the wheel and inlined into
every report page as a base64 `@font-face` data URI by `chrome.py`. This keeps reports a single
self-contained HTML file that renders identically on every OS **with no network** (a CDN/web-font
fetch would break offline rendering + byte-determinism). Inter is licensed under the SIL Open Font
License 1.1 (`Inter-OFL.txt`), which permits embedding/redistribution.

## What is in the subset
- Source: Inter **variable** font `InterVariable.woff2` (`https://rsms.me/inter/font-files/`),
  version 4.66.
- Glyphs: printable ASCII only (`U+0020-007E`) + NBSP (`U+00A0`) - reports are ASCII by lint policy.
- Axis: `wght` instanced to the **400-600** range (the only weights the report CSS uses: 400 body,
  500 h3, 600 headings/KPI display). Trimming the range cut the file from ~43 KB (full axis) to
  ~29 KB.
- Layout features: hatchling default set **+ `tnum`** (tabular figures, used by KPI / table numerics).

## Reproduce (dev-time only; the OUTPUT is committed, never regenerated at build/runtime)
`fonttools` is a dev/build dependency only - it does not enter the runtime output contract. Run via
`uvx` so it does not pollute the runtime venv:

```
curl -sSL -o InterVariable.woff2 https://rsms.me/inter/font-files/InterVariable.woff2
uvx --from "fonttools[woff]" fonttools varLib.instancer InterVariable.woff2 "wght=400:600" -o tmp.ttf
uvx --from "fonttools[woff]" pyftsubset tmp.ttf \
    --unicodes=U+0020-007E,U+00A0 --layout-features+=tnum \
    --flavor=woff2 --output-file=inter-subset.woff2
```

Determinism note: the committed `inter-subset.woff2` bytes are fixed; the report golden depends on
the base64 of THESE bytes, not on re-running the subset (which could vary by fonttools version).
Replacing the asset is an intentional, golden-refreshing change.
