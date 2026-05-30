# c19 — release v0.1.0     release: v0.1 · phase: Finalize

## Goal
Tag `v0.1.0`; CI publishes to PyPI + GH Release; verify a clean install end-to-end.

## Depends on
All prior v0.1 commits (c01–c03, c11–c15, c17, c18).

## Files
- `_version.py` (confirm `0.1.0`), `CHANGELOG.md` (move Unreleased → `v0.1.0`, dated).

## Changes
1. **Verify PyPI name free** (`pip index versions bobframes`); fall back to `bob-frames` /
   `bobframescope` if taken (DECISIONS §15). Reserve + upload `0.0.0` placeholder beforehand if desired.
2. Finalize CHANGELOG; ensure `PYPI_API_TOKEN` GH secret set.
3. `git tag v0.1.0 && git push origin v0.1.0` → CI `publish` job runs.

## Done when (post-install verification — CLI_PLAN §16)
```
pipx install bobframes                              # exit 0
bobframes version                                   # bobframes 0.1.0  schema 3  pyarrow X.Y.Z
bobframes check                                      # exit 0; prints resolved paths
bobframes smoke                                      # exit 0; render-only against synthetic
cd "C:\path\to\captures"
bobframes ingest . --area "Chor bazar" --label r110565 --force
                                                     # exit 0; _data/.../*.parquet + drill index.html + root index
bobframes render .                                   # exit 0; same outputs, faster
bobframes serve .                                    # opens; visit /index.html + one drill page
```
Negative checks:
```
$env:BOBFRAMES_RENDERDOCCMD = 'C:/nope.exe'; bobframes check    # exit 3 (ADR-2: hardcoded-path discovery in v0.1)
bobframes ingest /nonexistent                                    # exit 2 (argparse)
# edit a _manifest.json schema_version to 99, then:
bobframes render .                                   # exit 1; message points to `ingest --force`
```

## Rollback
Delete the tag + yank the release if a blocker is found post-publish; fix forward in `v0.1.1`.

## Closes
Ships v0.1.0. v0.2 work ([commits/v02/](../v02/)) begins after this.

> **ADR-2 caveat for the negative check:** in v0.1 tool discovery is the existing inline/hardcoded
> path. `BOBFRAMES_*` env override + the rich §5 error message are part of c06 (v0.2). Adjust the
> exit-3 expectation accordingly if c06 hasn't been pulled forward.
