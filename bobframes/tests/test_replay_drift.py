"""c13 — replay-schema drift guardrail (H-6, supports D-2).

``replay/replay_main.py`` runs inside qrenderdoc's embedded Python and cannot reliably import the
host ``bobframes`` package, so it duplicates the schema column tuples from ``schemas.py``. Nothing
else fails the build when a ``schemas.py`` edit isn't mirrored into that copy, so this test diffs the
two literals and fails on drift — the duplication is safe to keep precisely because of this guard.

Per DECISIONS ADR-5 + ADR-9: match the ``*_COLS`` *suffix* (the original ``_COLS_`` *prefix* matched
zero and passed vacuously), map abbreviated vars to schema stems via an explicit alias, skip the
shared ``ID_COLS`` base, and assert a minimum table count so a future rename can't silently
re-disable the guard.

ADR-9 correction (verified empirically): replay defines 20 ``*_COLS`` tables (not 21), and three of
them — ``events`` / ``draws`` / ``passes`` — legitimately omit four columns that
``derive_post_merge.py`` computes host-side *after* replay. So the guard compares each replay tuple
against its schema tuple **minus a pinned set of host-derived columns**: that still catches any
raw-column add/remove/reorder and any new *unpinned* schema-only column, while staying green today.

Named ``test_replay_drift.py`` (not the c13 doc's ``replay_drift.py``) so default pytest collects it —
the repo defines no ``python_files`` override. Same reason as c03's ``test_hardening.py``.
"""
from __future__ import annotations

import ast
from pathlib import Path

import bobframes

from .. import schemas

_REPLAY_MAIN = Path(bobframes.__file__).resolve().parent / "replay" / "replay_main.py"

# var (sans _COLS) -> schemas stem; identity-lowercase unless listed.
_REPLAY_STEM = {
    "RT": "render_targets",
    "RT_TIMELINE": "rt_event_timeline",
    "STATE_CHANGE": "state_change_events",
    "COUNTERS": "counters_per_event",
}

# Columns schemas.py carries that the replay stage legitimately does NOT emit: they are derived
# host-side in derive_post_merge.py (see its module docstring) after the raw CSVs land. Keyed by
# schema stem. Anything schema-only and NOT listed here is treated as drift.
_DERIVED_COLS = {
    "events": ("parent_marker_path_norm",),
    "draws": ("parent_pass_path_norm", "draw_class"),
    "passes": ("marker_path_norm",),
}

_EXPECTED_REPLAY_TABLES = 20  # ADR-9: empirically 20 (ADR-5 estimated 21).


def _resolve_tuple(node: ast.AST, names: dict[str, tuple]) -> tuple:
    """Resolve a column-tuple expression: a literal tuple, a bare Name referring to an already-seen
    tuple (e.g. ``ID_COLS``), or any chain of ``+`` concatenations of those."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _resolve_tuple(node.left, names) + _resolve_tuple(node.right, names)
    if isinstance(node, ast.Name):
        return names[node.id]
    if isinstance(node, ast.Tuple):
        return tuple(elt.value for elt in node.elts)
    raise AssertionError(f"unexpected node in column tuple: {ast.dump(node)}")


def _extract_col_tuples(tree: ast.Module, suffix: str, skip: set[str]) -> dict[str, tuple]:
    """Parse top-level ``<NAME>_COLS = (...)`` assignments into full literal tuples.

    Tracks every resolved ``*_COLS`` name (incl. the skipped base) so later concatenations like
    ``ID_COLS + (...)`` resolve, but returns only names that end with ``suffix`` and aren't in
    ``skip``.
    """
    names: dict[str, tuple] = {}
    result: dict[str, tuple] = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        var = node.targets[0].id
        if not var.endswith(suffix):
            continue
        names[var] = _resolve_tuple(node.value, names)
        if var not in skip:
            result[var] = names[var]
    return result


def test_replay_main_schema_in_sync():
    tree = ast.parse(_REPLAY_MAIN.read_text(encoding="utf-8"))
    replay_tables = _extract_col_tuples(tree, suffix="_COLS", skip={"ID_COLS"})

    assert len(replay_tables) >= _EXPECTED_REPLAY_TABLES, (
        f"guard must not match near-zero: found {len(replay_tables)} replay *_COLS tables, "
        f"expected >= {_EXPECTED_REPLAY_TABLES} (a rename may have silently disabled the guard)"
    )

    for var, cols in replay_tables.items():
        base = var[: -len("_COLS")]
        stem = _REPLAY_STEM.get(base, base.lower())
        try:
            expected = schemas.expected_columns(stem)
        except KeyError:
            raise AssertionError(f"{var}: no schema stem {stem!r} in schemas.TABLES")

        derived = _DERIVED_COLS.get(stem, ())
        # Pinned derived columns must really be in the schema, or the allowlist is masking a typo /
        # a genuine raw column.
        for d in derived:
            assert d in expected, f"_DERIVED_COLS[{stem!r}] lists {d!r}, absent from schemas.{stem}"

        expected_raw = tuple(c for c in expected if c not in derived)
        assert cols == expected_raw, (
            f"{var} drifted from schemas.{stem}: "
            f"replay_only={[c for c in cols if c not in expected_raw]} "
            f"schema_only={[c for c in expected_raw if c not in cols]}"
        )
