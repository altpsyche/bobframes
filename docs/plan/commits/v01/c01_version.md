# c01 — add `__version__`     release: v0.1 · phase: Safety net

## Goal
The package exposes `__version__`. Zero behavior change — the foundation for `bobframes version` and
`[tool.hatch.version]`.

## Depends on
[BOOTSTRAP.md](../../BOOTSTRAP.md) (repo exists, tree copied in).

## Files
- `_version.py` — NEW: `__version__ = "0.1.0"`
- `__init__.py` — add `from ._version import __version__`

(Package is still named `_analysis` at this commit; renamed at [c14](c14_rename.md).)

## Changes
1. Create `_version.py` with the single assignment.
2. Add the re-export line to `__init__.py`.
3. Confirm `[tool.hatch.version] path = "<pkg>/_version.py"` in `pyproject.toml` resolves.

## Done when
- `python -c "import _analysis; print(_analysis.__version__)"` → `0.1.0`.
- Golden parity green (no rendered-output change). _(Parity harness lands in c02; until then this is
  trivially safe — no output path touched.)_

## Rollback
Delete `_version.py`; revert the `__init__.py` line.

## Closes
None — foundation. Enables `version` verb ([c11](c11_cli_dispatcher.md)) and release tagging
([c19](c19_release.md)).
