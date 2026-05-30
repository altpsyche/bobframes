"""Console entry point for the ``bobframes`` command.

Interim dispatcher (c01 seed): ``version`` is handled here; every other invocation is
delegated to the legacy pipeline CLI (:func:`bobframes.run.main`, the old
``--root/--area/--label`` interface). The full subcommand surface
(ingest / render / ab / report / catalog / lint / check / serve / smoke) is built in c11,
which replaces this file's dispatch.
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        print("bobframes <verb> [args]")
        print("  version             print version, schema, and pyarrow versions")
        print("  <pipeline args>     delegated to the legacy pipeline (--root --area --label ...)")
        print()
        print("The full subcommand CLI (ingest/render/ab/report/catalog/lint/check/serve/smoke)")
        print("lands in c11. For now use the pipeline flags or `python -m bobframes.run --help`.")
        return 0

    if argv[0] == "version":
        from . import __version__, schemas
        try:
            import pyarrow
            pa = pyarrow.__version__
        except Exception:
            pa = "not installed"
        print(f"bobframes {__version__}  schema {schemas.SCHEMA_VERSION}  pyarrow {pa}")
        return 0

    from . import run
    return run.main(argv)


if __name__ == "__main__":
    sys.exit(main())
