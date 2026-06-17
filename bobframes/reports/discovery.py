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


# --- Run model (c16e, ADR-35) -------------------------------------------------
# A report is rendered FOR ONE current run (a DropSet). The current run's contents
# are the reported truth; prior runs are baselines for delta/trend, never summed.
# These resolve against the in-memory `drops` list a report already holds, so the
# full list stays available for comparison columns (no catalog re-read).

def current_run(drops: list, *, run_label: str | None = None,
                run_date: str | None = None) -> 'DropSet | None':
    """The current run: an override (by label/date) else the newest (drops[-1]).

    `drops` come date-asc from discover_drops, so the last is newest. "Newest" thus
    assumes label monotonicity within a single date (ISO dates are the dominant key,
    unique per run in practice) - see ADR-35.
    """
    if not drops:
        return None
    if run_label is None and run_date is None:
        return drops[-1]
    for d in drops:
        if run_label and d.label != run_label:
            continue
        if run_date and d.date != run_date:
            continue
        return d
    return None


def baseline_run(drops: list, current: 'DropSet | None', *,
                 baseline_label: str | None = None,
                 baseline_date: str | None = None) -> 'DropSet | None':
    """The baseline the current run is compared against (deltas + resolved-since).

    Default = the run immediately prior to `current`; None when current is the oldest
    or there is a single run. An explicit (label/date) override picks any other run.
    """
    if not drops or current is None:
        return None
    if baseline_label is not None or baseline_date is not None:
        for d in drops:
            if d is current:
                continue
            if baseline_label and d.label != baseline_label:
                continue
            if baseline_date and d.date != baseline_date:
                continue
            return d
        return None
    idx = next((i for i, d in enumerate(drops) if d.key == current.key), -1)
    return drops[idx - 1] if idx > 0 else None


@dataclass
class RunContext:
    """The single carrier of the run model (ADR-35) threaded into every report.

    Resolved once per build() via `run_context`; carries the current run, its
    baseline, and the full drop list so comparison columns stay available.
    """
    drops: list
    current: 'DropSet | None'
    baseline: 'DropSet | None'

    @property
    def n_runs(self) -> int:
        return len(self.drops)

    @property
    def index(self) -> int:
        """0-based position of current in drops; -1 when there is no current run."""
        if not self.current:
            return -1
        return next((i for i, d in enumerate(self.drops)
                     if d.key == self.current.key), -1)

    @property
    def ordinal(self) -> str:
        """Human run ordinal e.g. '2 of 2'; '' when there is no current run."""
        return f'{self.index + 1} of {self.n_runs}' if self.current else ''

    @property
    def is_newest(self) -> bool:
        return bool(self.current) and self.index == self.n_runs - 1

    @property
    def history(self) -> list:
        """Drops up to AND INCLUDING the current run (chronological) -- the data scope for cross-drop
        CHARTS/TABLES on a per-run page, so an OLDER run's page never shows data for runs that came
        AFTER it (ADR-35; R-22). The run picker still lists every run (from `drops`); only the rendered
        data is scoped. Equals `drops` on the newest page (index == n_runs - 1)."""
        i = self.index
        return list(self.drops) if i < 0 else self.drops[:i + 1]

    @property
    def run_label(self) -> str:
        """current.key (e.g. '2026-06-01_r110788'); '' when there is no current run."""
        return self.current.key if self.current else ''


def run_context(drops: list, *, run_label: str | None = None,
                run_date: str | None = None,
                baseline_label: str | None = None,
                baseline_date: str | None = None) -> RunContext:
    cur = current_run(drops, run_label=run_label, run_date=run_date)
    bl = baseline_run(drops, cur, baseline_label=baseline_label,
                      baseline_date=baseline_date)
    return RunContext(list(drops), cur, bl)


def prerendered_runs(drops: list, max_older: int) -> list:
    """The runs that get a pre-rendered page / picker option (c16f): the newest plus the `max_older`
    most-recent OLDER runs, returned date-asc. Bounds the per-run page explosion as history accrues
    (the orchestrator logs anything dropped beyond the cap - no silent truncation, ADR-23). Runs
    beyond the cap stay reachable via `trend_table`. Returns the drops verbatim for < 2 runs.
    """
    if len(drops) < 2:
        return list(drops)
    older = drops[:-1]
    if max_older is not None and max_older >= 0:
        older = older[-max_older:]
    return list(older) + [drops[-1]]


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
