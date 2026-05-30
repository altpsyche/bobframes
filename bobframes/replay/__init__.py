"""bobframes.replay — qrenderdoc-side replay entry point.

``replay_main.py`` runs *inside* qrenderdoc's embedded Python, launched as
``qrenderdoc --python <path>``. It must be locatable as a real on-disk file even when bobframes is
installed as a wheel, so ``replay_script_path()`` resolves it via ``importlib.resources`` instead of
walking the source tree (c12).
"""
from __future__ import annotations

from contextlib import contextmanager
from importlib.resources import as_file, files


@contextmanager
def replay_script_path():
    """Yield a real on-disk path to ``replay_main.py`` for the duration of the context.

    Uses ``importlib.resources`` so it resolves from an installed wheel, not just an in-tree
    checkout. ``as_file()`` extracts to a temp file only if the wheel is ever zipped; hatchling
    builds non-zip wheels and force-includes this file (ARCHITECTURE §3), so normally a direct path
    is yielded. Any temp extraction lives until the context exits — keep the qrenderdoc subprocess
    inside the ``with`` block.
    """
    resource = files(__name__).joinpath('replay_main.py')
    with as_file(resource) as path:
        yield path
