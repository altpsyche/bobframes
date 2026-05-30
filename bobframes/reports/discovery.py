"""Catalog enumeration and drop-metadata dataclasses."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field

import pyarrow.parquet as papq

from .. import paths as _paths


@dataclass
class DropRow:
    area: str
    drop_date: str
    drop_label: str
    drop_dir: str
    ok_captures: int


@dataclass
class DropSet:
    """All (area, drop_date, drop_label, drop_dir) tuples for one label+date."""
    label: str
    date: str
    rows: list[DropRow] = field(default_factory=list)

    @property
    def key(self) -> str:
        if self.date and self.label:
            return f'{self.date}_{self.label}'
        return self.label or self.date or 'unknown'

    @property
    def n_captures(self) -> int:
        return sum(r.ok_captures for r in self.rows)

    @property
    def areas(self) -> list[str]:
        return sorted({r.area for r in self.rows})


def discover_drops(root: str) -> list[DropSet]:
    """Read _catalog.parquet, group by (drop_date, drop_label), filter replay_status='ok'.

    Returns list of DropSet sorted by drop_date asc then drop_label asc.
    """
    cat_path = _paths.catalog_parquet(root)
    if not os.path.exists(cat_path):
        return []
    cols_wanted = ['area', 'drop_date', 'drop_label', 'capture',
                   'replay_status', 'analysis_out_path']
    try:
        t = papq.read_table(cat_path, columns=cols_wanted)
    except Exception:
        return []

    areas = t.column('area').to_pylist()
    dates = t.column('drop_date').to_pylist()
    labels = t.column('drop_label').to_pylist()
    statuses = t.column('replay_status').to_pylist()
    aop = t.column('analysis_out_path').to_pylist()

    ok_by_drop: dict[tuple[str, str, str], int] = Counter()
    path_by_drop: dict[tuple[str, str, str], str] = {}
    for a, d, l, s, p in zip(areas, dates, labels, statuses, aop):
        if s == 'ok':
            ok_by_drop[(a, d, l)] += 1
        path_by_drop.setdefault((a, d, l), p)

    seen_sets: dict[tuple[str, str], DropSet] = {}
    for (a, d, l), p in path_by_drop.items():
        key = (d, l)
        if key not in seen_sets:
            seen_sets[key] = DropSet(label=l, date=d)
        # New: analysis_out_path stored relative under _data/. resolve_drop_dir
        # already points at <root>/_data/<area>/<drop> (the data dir).
        seen_sets[key].rows.append(DropRow(
            area=a, drop_date=d, drop_label=l,
            drop_dir=_paths.resolve_drop_dir(root, p) if p else '',
            ok_captures=ok_by_drop.get((a, d, l), 0),
        ))

    return sorted(seen_sets.values(), key=lambda s: (s.date, s.label))


def resolve_drop_set(root: str, *,
                     label: str | None,
                     date: str | None = None) -> DropSet | None:
    drops = discover_drops(root)
    for d in drops:
        if label and d.label != label:
            continue
        if date and d.date != date:
            continue
        return d
    return None


def ok_capture_set(root: str) -> set[tuple]:
    """Return {(area, drop_date, drop_label, capture)} where replay_status='ok'."""
    cat_path = _paths.catalog_parquet(root)
    if not os.path.exists(cat_path):
        return set()
    try:
        t = papq.read_table(cat_path, columns=['area', 'drop_date', 'drop_label',
                                                'capture', 'replay_status'])
    except Exception:
        return set()
    cols = {c: t.column(c).to_pylist() for c in t.column_names}
    out = set()
    for i in range(t.num_rows):
        if cols['replay_status'][i] == 'ok':
            out.add((cols['area'][i], cols['drop_date'][i],
                     cols['drop_label'][i], cols['capture'][i]))
    return out
