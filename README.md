# BobFrames

RenderDoc capture pipeline: ingest, analyze, render. A folder of `.rdc` captures in →
`_data/` (Parquet) + `_reports/` (HTML) out. Windows-only in v1.

> **Status: pre-release scaffold.** The full README ships in commit c18. Implementation is
> plan-driven — see [`docs/plan/INDEX.md`](docs/plan/INDEX.md), and read
> [`docs/plan/STATE.md`](docs/plan/STATE.md) first to find the current commit.

## Requirements (target)
- Windows 10+
- Python 3.10+
- RenderDoc 1.x+ (or Arm Performance Studio with `renderdoccmd` + `qrenderdoc`)

## Install (target)
```
pipx install bobframes
bobframes check
```

See [`docs/plan/ARCHITECTURE.md`](docs/plan/ARCHITECTURE.md) for the CLI surface and layout.
