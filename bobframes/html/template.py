"""Per-drop data browser HTML + root cross-drop directory HTML.

Tables render via virtual scrolling: data ships as JSON in <script> blocks,
JS renders only the rows visible inside each scroll container, so the DOM
stays cheap regardless of dataset size. Sort/filter rebuild the visible
window in O(window-size).

Resource ID cells are enriched with labels from `_resource_labels.json`
(e.g. `tex_id=2184` displays as `2184  SceneDepthZ`).

CSS and JS are inlined for self-contained file:// browsing.
"""

from __future__ import annotations

import csv
import html as _html
import json
import os
from typing import Iterable

import pyarrow.parquet as papq

from ..reports import base as reports_base


_CATEGORY_MAP = {
    'aggregates': ['passes', 'pass_class_breakdown', 'frame_totals',
                   'texture_usage'],
    'entities':   ['shaders', 'textures', 'render_targets', 'programs',
                   'samplers', 'buffers', 'fbos'],
    'actions':    ['draws', 'draw_bindings', 'events', 'clears', 'dispatches',
                   'state_change_events', 'vertex_inputs', 'indirect_args',
                   'descriptor_access', 'rt_event_timeline',
                   'program_transitions', 'resource_creation',
                   'counters_per_event'],
    'samples':    ['vbo_samples', 'ibo_samples', 'post_vs_samples',
                   'texture_samples', 'pixel_history'],
}
_CATEGORY_ORDER = ['aggregates', 'entities', 'actions', 'samples', 'sidecars']
_DEFAULT_OPEN = {'aggregates'}


# Map of (table_name, column_name) -> resource kind key in _resource_labels.json
_LABEL_COLS: dict[str, dict[str, str]] = {
    'draws': {
        'program_id': 'program',
        'vs_shader_id': 'shader',
        'fs_shader_id': 'shader',
        'depth_rt_id': 'texture',
        'color_rt_ids': 'texture_list',  # semicolon-joined
        'ibo_id': 'buffer',
    },
    'draw_bindings': {
        # resource_id meaning depends on slot_kind; resolved in JS
        'resource_id': 'auto_by_slot_kind',
        'sampler_id': 'sampler',
    },
    'passes': {
        'color_rt_id_first': 'texture',
        'depth_rt_id_first': 'texture',
    },
    'shaders': {
        # shader_id self-references; no need.
    },
    'render_targets': {
        # has its own label column already
    },
    'textures': {},
    'programs': {
        'vs_shader_id': 'shader',
        'fs_shader_id': 'shader',
        'cs_shader_id': 'shader',
    },
    'samplers': {},
    'fbos': {
        'resource_id': 'texture',
    },
    'events': {
        'output_color_rt_id': 'texture',
        'output_depth_rt_id': 'texture',
        'copy_source_id': 'texture',
        'copy_destination_id': 'texture',
    },
    'clears': {
        'fbo_id': 'fbo',
    },
    'dispatches': {
        'program_id': 'program',
        'cs_shader_id': 'shader',
    },
    'rt_event_timeline': {
        'rt_id': 'texture',
    },
    'descriptor_access': {
        'resource_id': 'auto_by_kind',
    },
    'pixel_history': {
        'rt_id': 'texture',
    },
    'texture_usage': {
        'tex_id': 'texture',
    },
    'pass_class_breakdown': {},
    'program_transitions': {
        'from_program_id': 'program',
        'to_program_id': 'program',
    },
    'state_change_events': {},
    'indirect_args': {
        'indirect_buffer_id': 'buffer',
    },
    'vertex_inputs': {
        'buffer_id': 'buffer',
    },
    'resource_creation': {},
    'counters_per_event': {},
    'frame_totals': {},
    'vbo_samples': {'buffer_id': 'buffer'},
    'ibo_samples': {'buffer_id': 'buffer'},
    'post_vs_samples': {},
    'texture_samples': {'tex_id': 'texture'},
}


_PER_DROP_CSS = """
:root { --label: #4a6a3a; --th-bg: var(--surface-2); --th-bg-active: var(--row-hover); }
@media (prefers-color-scheme: dark) {
  :root { --label: #a3d39c; }
}

body { max-width: 1800px; }

nav.toc a { display: flex; justify-content: space-between; padding: 2px 0; gap: 1rem; }
nav.toc a .ct { color: var(--text-3); font-variant-numeric: tabular-nums; }

.controls {
  display: flex; gap: var(--sp-3); align-items: center;
  font-size: var(--fs-small); flex-wrap: wrap;
  margin: var(--sp-2) 0 var(--sp-2);
}
.controls input[type=search] {
  font: inherit; padding: 4px 8px;
  border: 1px solid var(--border-2); background: var(--surface-0); color: var(--text-1);
  border-radius: 2px; min-width: 22rem;
}
.controls input[type=search]:focus { outline: 1px solid var(--accent); }
.controls .ct { color: var(--text-2); font-variant-numeric: tabular-nums; }
.controls .dl { font-size: var(--fs-small); color: var(--accent); }

.table-scroll {
  height: 60vh; overflow: auto;
  border: 1px solid var(--border-1);
  background: var(--surface-0);
  position: relative;
}
.table-scroll.short { height: auto; max-height: 60vh; }
table.data {
  border-collapse: separate; border-spacing: 0;
  font: var(--fs-mono) ui-monospace, 'Cascadia Code', Consolas, monospace;
  width: max-content; min-width: 100%; table-layout: auto;
}
table.data thead th {
  position: sticky; top: 0; z-index: 2;
  background: var(--th-bg);
  text-align: left; cursor: pointer; user-select: none;
  color: var(--accent); font-weight: 600;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border-2);
  white-space: nowrap;
}
table.data thead th:hover { background: var(--th-bg-active); }
table.data thead th .sort-arrow { display: inline-block; width: 10px; color: var(--text-3); }
table.data thead th.numeric, table.data tbody td.numeric {
  text-align: right; font-variant-numeric: tabular-nums;
}
table.data tbody td {
  padding: 2px 8px;
  border-bottom: 1px solid var(--border-1);
  vertical-align: top; white-space: nowrap;
  max-width: 380px; overflow: hidden; text-overflow: ellipsis;
  background: var(--surface-0);
}
table.data tbody tr.alt td { background: var(--surface-1); }
table.data tbody tr:hover td { background: var(--row-hover); }
table.data tbody td .lbl {
  color: var(--label); margin-left: 6px;
  font-style: italic; opacity: .85;
}
table.data tbody td a {
  color: inherit; text-decoration: none;
  border-bottom: 1px dotted var(--accent);
}
table.data tbody td a:hover { color: var(--accent); border-bottom-style: solid; }
.spacer td { padding: 0; border: 0; background: var(--surface-0); }

.sidecar-list a { font-family: ui-monospace, monospace; font-size: var(--fs-small); }
.sidecar-list span { color: var(--text-2); margin-left: .4rem; font-size: var(--fs-small); }
ul.sidecar-list { list-style: none; padding: 0; margin: var(--sp-2) 0;
                  columns: 5; column-gap: var(--sp-6); column-rule: 1px solid var(--border-1); }
ul.sidecar-list li { padding: 1px 0; break-inside: avoid; }

/* Per-drop table sections: inline (no full card chrome) */
section.table-section {
  margin: 0 0 var(--sp-4);
}
section.table-section > header.table-header {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--sp-3); margin: 0 0 var(--sp-2);
  padding: 0 0 0 var(--sp-3);
  border-left: 3px solid var(--border-2);
}
section.table-section > header.table-header h2 {
  margin: 0; padding: 0; border: 0;
  font-size: var(--fs-h3); color: var(--text-1);
}
section.table-section .table-meta {
  font: var(--fs-small) ui-monospace, monospace;
  color: var(--text-3);
}

details.category > .cat-body {
  background: var(--surface-0);
}
"""


def _compose_css() -> str:
    return (reports_base.design_tokens_css()
            + reports_base.chrome_css()
            + _PER_DROP_CSS)


_CSS = _compose_css()

# Virtual-scroll JS. One VTable per table.
_JS = r"""
(function(){
  const ROW_H = 22;
  const BUFFER = 8;

  // For ID kinds: where to jump when an ID cell is clicked
  const LINK_TARGET = {
    shader: { table: 'shaders', col: 'shader_id' },
    program: { table: 'programs', col: 'program_id' },
    texture: { table: 'textures', col: 'tex_id' },
    sampler: { table: 'samplers', col: 'sampler_id' },
    buffer: { table: 'buffers', col: 'buffer_id' },
    fbo: { table: 'fbos', col: 'fbo_id' },
  };

  function isNumeric(v){
    return v != null && (typeof v === 'number' || (typeof v === 'string' && /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v)));
  }
  function fmt(v){
    if (v == null) return '';
    if (typeof v === 'number'){
      if (v === 0) return '0';
      if (Math.abs(v) < 1e-4 || Math.abs(v) >= 1e7) return v.toExponential(4);
      return (Math.round(v * 1e6) / 1e6).toString();
    }
    return String(v);
  }

  function lookupLabel(labels, kind, id){
    if (!labels || !kind || id == null || id === '' || id === 0 || id === '0') return '';
    const k = String(id);
    const cap = labels.capture;
    if (!cap || !labels.by_capture || !labels.by_capture[cap]) return '';
    const buckets = labels.by_capture[cap];
    if (kind === 'auto_by_slot_kind' || kind === 'auto_by_kind') return '';
    if (kind === 'texture_list') return '';
    return (buckets[kind] && buckets[kind][k]) || '';
  }

  function autoKindForSlot(slotKind){
    if (slotKind === 'texture') return 'texture';
    if (slotKind === 'sampler') return 'sampler';
    if (slotKind === 'ubo' || slotKind === 'ssbo') return 'buffer';
    return '';
  }
  function autoKindForDescriptor(descriptorKind){
    if (descriptorKind === 'ReadOnlyResource' || descriptorKind === 'ImageSampler' || descriptorKind === 'TypedBuffer') return 'texture';
    if (descriptorKind === 'Sampler') return 'sampler';
    if (descriptorKind === 'ConstantBuffer' || descriptorKind === 'ReadWriteResource' || descriptorKind === 'ReadWriteBuffer') return 'buffer';
    return '';
  }

  class VTable {
    constructor(host, payload, labels){
      this.host = host;
      this.cols = payload.cols;
      this.rows = payload.rows;
      this.labelCols = payload.labelCols || {};
      this.labels = labels;
      this.view = this.rows.slice();
      this.sortCol = -1;
      this.sortDir = 1;

      // detect numeric columns from first 50 non-null cells
      this.numericCols = new Set();
      for (let ci = 0; ci < this.cols.length; ci++){
        let count = 0, num = 0;
        for (let ri = 0; ri < this.rows.length && count < 50; ri++){
          const v = this.rows[ri][ci];
          if (v == null || v === '') continue;
          count++;
          if (typeof v === 'number' || (typeof v === 'string' && /^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v))) num++;
        }
        if (count > 0 && num / count > 0.7) this.numericCols.add(ci);
      }

      // detect slot_kind column for draw_bindings (resource_id auto-label)
      this.slotKindCol = this.cols.indexOf('slot_kind');
      this.descriptorKindCol = this.cols.indexOf('descriptor_kind');

      this.build();
    }

    build(){
      const table = document.createElement('table');
      table.className = 'data';
      const thead = table.createTHead();
      const tr = thead.insertRow();
      for (let i = 0; i < this.cols.length; i++){
        const th = document.createElement('th');
        const txt = document.createTextNode(this.cols[i]);
        th.appendChild(txt);
        if (this.numericCols.has(i)) th.classList.add('numeric');
        const arrow = document.createElement('span');
        arrow.className = 'sort-arrow';
        th.appendChild(arrow);
        th.addEventListener('click', () => this.sort(i));
        tr.appendChild(th);
      }
      const tbody = document.createElement('tbody');
      const sTop = document.createElement('tr');
      const sBot = document.createElement('tr');
      sTop.className = 'spacer'; sBot.className = 'spacer';
      const tdTop = document.createElement('td');
      const tdBot = document.createElement('td');
      tdTop.colSpan = this.cols.length;
      tdBot.colSpan = this.cols.length;
      sTop.appendChild(tdTop); sBot.appendChild(tdBot);
      tbody.appendChild(sTop); tbody.appendChild(sBot);
      table.appendChild(tbody);
      this.host.appendChild(table);

      this.tbody = tbody;
      this.sTop = sTop;
      this.sBot = sBot;
      this.tdTop = tdTop;
      this.tdBot = tdBot;

      this.host.addEventListener('scroll', () => this.render());
      window.addEventListener('resize', () => this.render());
      // Re-render when a containing <details class="category"> opens.
      const detailsEl = this.host.closest('details');
      if (detailsEl){
        detailsEl.addEventListener('toggle', () => {
          if (detailsEl.open){
            requestAnimationFrame(() => this.render());
            setTimeout(() => this.render(), 50);
          }
        });
      }
      this.render();
      // Re-render after layout settles (initial clientHeight can be 0)
      requestAnimationFrame(() => this.render());
      // And once more after fonts/sizes stabilize
      setTimeout(() => this.render(), 50);
    }

    sort(ci){
      if (this.sortCol === ci) this.sortDir = -this.sortDir;
      else { this.sortCol = ci; this.sortDir = 1; }
      const dir = this.sortDir;
      const isNum = this.numericCols.has(ci);
      this.view.sort((a, b) => {
        const aa = a[ci], bb = b[ci];
        if (aa == null && bb == null) return 0;
        if (aa == null) return 1;
        if (bb == null) return -1;
        if (isNum){
          const na = +aa, nb = +bb;
          return (na - nb) * dir;
        }
        return String(aa).localeCompare(String(bb)) * dir;
      });
      const headers = this.host.querySelectorAll('thead th');
      for (let i = 0; i < headers.length; i++){
        const a = headers[i].querySelector('.sort-arrow');
        if (a) a.textContent = (i === ci) ? (dir > 0 ? ' ▲' : ' ▼') : '';
      }
      this.host.scrollTop = 0;
      this.render();
    }

    filter(query){
      const q = (query || '').trim().toLowerCase();
      if (!q){
        this.view = this.rows.slice();
      } else {
        const labels = this.labels;
        const labelCols = this.labelCols;
        const cols = this.cols;
        const slotKindCol = this.slotKindCol;
        const descriptorKindCol = this.descriptorKindCol;
        this.view = this.rows.filter(r => {
          for (let i = 0; i < r.length; i++){
            const v = r[i];
            if (v == null) continue;
            if (String(v).toLowerCase().indexOf(q) >= 0) return true;
            // also match against the resolved label, if any
            const lc = labelCols[cols[i]];
            if (!lc || v === 0 || v === '0' || v === '') continue;
            let kind = lc;
            if (kind === 'auto_by_slot_kind' && slotKindCol >= 0) kind = autoKindForSlot(r[slotKindCol]);
            else if (kind === 'auto_by_kind' && descriptorKindCol >= 0) kind = autoKindForDescriptor(r[descriptorKindCol]);
            if (kind === 'texture_list'){
              const ids = String(v).split(';').filter(x => x);
              for (const id of ids){
                const lbl = lookupLabel(labels, 'texture', id);
                if (lbl && lbl.toLowerCase().indexOf(q) >= 0) return true;
              }
            } else if (kind){
              const lbl = lookupLabel(labels, kind, v);
              if (lbl && lbl.toLowerCase().indexOf(q) >= 0) return true;
            }
          }
          return false;
        });
      }
      // resort if a sort was active
      if (this.sortCol >= 0){
        const ci = this.sortCol, dir = this.sortDir;
        const isNum = this.numericCols.has(ci);
        this.view.sort((a, b) => {
          const aa = a[ci], bb = b[ci];
          if (aa == null && bb == null) return 0;
          if (aa == null) return 1;
          if (bb == null) return -1;
          if (isNum) return (+aa - +bb) * dir;
          return String(aa).localeCompare(String(bb)) * dir;
        });
      }
      this.host.scrollTop = 0;
      this.render();
    }

    cellNode(value, ri, ci){
      const td = document.createElement('td');
      if (this.numericCols.has(ci)) td.classList.add('numeric');

      const colName = this.cols[ci];
      const lc = this.labelCols[colName];
      let kind = lc;
      if (kind === 'auto_by_slot_kind' && this.slotKindCol >= 0){
        kind = autoKindForSlot(this.view[ri][this.slotKindCol]);
      } else if (kind === 'auto_by_kind' && this.descriptorKindCol >= 0){
        kind = autoKindForDescriptor(this.view[ri][this.descriptorKindCol]);
      }

      // primary cell value: cross-link if we have a target for this kind
      const formatted = fmt(value);
      const link = LINK_TARGET[kind];
      if (link && value != null && value !== '' && value !== 0 && value !== '0' && kind !== 'texture_list'){
        const a = document.createElement('a');
        a.href = '#' + link.table;
        a.textContent = formatted;
        a.title = 'jump to ' + link.table + ' filtered to ' + link.col + '=' + value;
        a.addEventListener('click', (ev) => {
          ev.preventDefault();
          jumpToTable(link.table, String(value));
        });
        td.appendChild(a);
      } else {
        td.textContent = formatted;
      }

      // label enrichment (appears after the value/link)
      if (lc && value != null && value !== '' && value !== 0 && value !== '0'){
        if (kind === 'texture_list'){
          const ids = String(value).split(';').filter(x => x);
          const labels = ids.map(id => lookupLabel(this.labels, 'texture', id))
                            .filter(x => x);
          if (labels.length){
            const span = document.createElement('span');
            span.className = 'lbl';
            span.textContent = labels.join(', ');
            td.appendChild(span);
          }
        } else if (kind){
          const label = lookupLabel(this.labels, kind, value);
          if (label){
            const span = document.createElement('span');
            span.className = 'lbl';
            span.textContent = label;
            td.appendChild(span);
          }
        }
      }
      return td;
    }

    render(){
      const scrollTop = this.host.scrollTop;
      const height = this.host.clientHeight || 600;
      const len = this.view.length;
      const start = Math.max(0, Math.floor(scrollTop / ROW_H) - BUFFER);
      const end = Math.min(len, Math.ceil((scrollTop + height) / ROW_H) + BUFFER);

      // clear data rows between spacers
      while (this.sTop.nextSibling !== this.sBot){
        this.tbody.removeChild(this.sTop.nextSibling);
      }
      // height on <tr> directly; <td> alone doesn't make a row tall in all browsers
      this.sTop.style.height = (start * ROW_H) + 'px';
      this.sBot.style.height = ((len - end) * ROW_H) + 'px';
      this.tdTop.style.height = (start * ROW_H) + 'px';
      this.tdBot.style.height = ((len - end) * ROW_H) + 'px';

      const frag = document.createDocumentFragment();
      for (let i = start; i < end; i++){
        const tr = document.createElement('tr');
        tr.style.height = ROW_H + 'px';
        if (i % 2 === 1) tr.className = 'alt';
        const row = this.view[i];
        for (let ci = 0; ci < this.cols.length; ci++){
          tr.appendChild(this.cellNode(row[ci], i, ci));
        }
        frag.appendChild(tr);
      }
      this.tbody.insertBefore(frag, this.sBot);
    }
  }

  function jumpToTable(tableName, idValue){
    const host = document.querySelector('div.table-scroll[data-table="' + tableName + '"]');
    if (!host || !host._vt) return;
    const section = host.closest('section');
    const input = section ? section.querySelector('input[type=search]') : null;
    if (input){
      input.value = idValue;
      // trigger filter immediately (no debounce on programmatic set)
      host._vt.filter(idValue);
      const counter = section.querySelector('.ct.visible-count');
      if (counter){
        const v = host._vt.view.length, t = host._vt.rows.length;
        counter.textContent = v.toLocaleString() + ' / ' + t.toLocaleString() + ' visible';
      }
    }
    section.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  window.__jumpToTable = jumpToTable;

  window.addEventListener('DOMContentLoaded', () => {
    const labels = window.__labels || {};
    document.querySelectorAll('div.table-scroll[data-table]').forEach(host => {
      const name = host.dataset.table;
      const payload = window['__data_' + name];
      if (!payload){ return; }
      const labelsForTable = Object.assign({}, labels);
      // Per-section: capture from data is row-level; use the section's data-capture if set
      labelsForTable.capture = host.dataset.capture || (payload.rows[0] ? payload.rows[0][3] : '');
      const vt = new VTable(host, payload, labelsForTable);
      host._vt = vt;

      const section = host.closest('section');
      const input = section.querySelector('input[type=search]');
      const counter = section.querySelector('.ct.visible-count');
      function updateCounter(){
        const v = vt.view.length, t = vt.rows.length;
        counter.textContent = v.toLocaleString() + ' / ' + t.toLocaleString() + ' visible';
      }
      updateCounter();
      let timer = null;
      input.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => { vt.filter(input.value); updateCounter(); }, 80);
      });
    });
  });
})();
"""


def _h(s) -> str:
    return _html.escape(str(s if s is not None else ''))


def _row_count(pq_path: str) -> int:
    try:
        return papq.read_metadata(pq_path).num_rows
    except Exception:
        return 0


def _file_size_label(path: str) -> str:
    if not os.path.exists(path):
        return ''
    n = os.path.getsize(path)
    if n < 1024:
        return f'{n} B'
    if n < 1024 * 1024:
        return f'{n / 1024:.1f} KB'
    return f'{n / 1024 / 1024:.1f} MB'


def _table_payload(table_name: str, out_dir: str) -> dict | None:
    pq = os.path.join(out_dir, f'{table_name}.parquet')
    if not os.path.exists(pq):
        return None
    t = papq.read_table(pq)
    if t.num_rows == 0:
        return None
    cols = t.column_names
    # Build rows as a list-of-lists. Pyarrow's to_pylist on a Table doesn't
    # exist; use per-column extraction.
    arrays = [t.column(c).to_pylist() for c in cols]
    n = t.num_rows
    rows = [[arrays[ci][ri] for ci in range(len(cols))] for ri in range(n)]
    label_cols = _LABEL_COLS.get(table_name, {})
    return {'cols': cols, 'rows': rows, 'labelCols': label_cols}


def _inline_table_with_data(table_name: str, out_dir: str,
                             sidecar_rel: str = '.') -> tuple[str, str] | None:
    """Returns (section_html, script_html) or None if table empty.

    sidecar_rel: relative path from rendered HTML to the data dir, used to
    construct CSV/parquet download links. Default '.' for legacy callers
    where HTML lives next to data.
    """
    payload = _table_payload(table_name, out_dir)
    if payload is None:
        return None
    n_total = len(payload['rows'])
    n_cols = len(payload['cols'])
    pq_sz = _file_size_label(os.path.join(out_dir, f'{table_name}.parquet'))
    csv_sz = _file_size_label(os.path.join(out_dir, f'{table_name}.csv'))

    prefix = '' if sidecar_rel in ('.', '') else sidecar_rel.rstrip('/') + '/'

    section = []
    section.append(f'<section class="table-section" id="{table_name}">')
    section.append('<header class="table-header">')
    section.append(f'<h2>{_h(table_name)}</h2>')
    section.append(f'<span class="table-meta">{n_total:,} rows, {n_cols} cols</span>')
    section.append('</header>')
    section.append('<div class="controls">')
    section.append(f'<input type="search" placeholder="filter {table_name}...">')
    section.append('<span class="ct visible-count"></span>')
    section.append(f'<a class="dl" href="{prefix}{table_name}.csv">CSV ({csv_sz})</a>')
    section.append(f'<a class="dl" href="{prefix}{table_name}.parquet">parquet ({pq_sz})</a>')
    section.append('</div>')
    section.append(f'<div class="table-scroll" data-table="{table_name}"></div>')
    section.append('</section>')

    script = (f'<script>window.__data_{table_name}='
              f'{json.dumps(payload, separators=(",", ":"))};</script>')
    return '\n'.join(section), script


def _categorize(table_specs: list[tuple[str, int, int]]) -> dict:
    """Return {category: [(name, n_rows, n_cols), ...]} preserving order."""
    by_cat: dict[str, list] = {cat: [] for cat in _CATEGORY_ORDER if cat != 'sidecars'}
    spec_by_name = {name: (name, n_rows, n_cols)
                    for (name, n_rows, n_cols) in table_specs}
    used: set = set()
    for cat in _CATEGORY_ORDER:
        if cat == 'sidecars':
            continue
        for name in _CATEGORY_MAP.get(cat, []):
            if name in spec_by_name:
                by_cat[cat].append(spec_by_name[name])
                used.add(name)
    # Anything uncategorized goes into 'actions' as a tail bucket
    for name, n_rows, n_cols in table_specs:
        if name not in used:
            by_cat.setdefault('actions', []).append((name, n_rows, n_cols))
    return by_cat


def _toc(by_cat: dict) -> str:
    """Category-aware TOC. Each category links to its <details> anchor."""
    parts = ['<nav class="toc">']
    for cat in _CATEGORY_ORDER:
        if cat == 'sidecars':
            parts.append(f'<a href="#cat-sidecars"><span>sidecars</span></a>')
            continue
        items = by_cat.get(cat, [])
        if not items:
            continue
        total_rows = sum(r for _, r, _ in items)
        parts.append(f'<a href="#cat-{_h(cat)}"><span>{_h(cat)}</span>'
                     f'<span class="ct">{len(items)}t, {total_rows:,}r</span></a>')
    parts.append('</nav>')
    return '\n'.join(parts)


def _category_block(cat: str, items: list, table_sections: dict,
                    is_open: bool) -> str:
    """Render <details class='category'> wrapping its table sections."""
    if not items:
        return ''
    total_rows = sum(r for _, r, _ in items)
    open_attr = ' open' if is_open else ''
    parts = [
        f'<details class="category" id="cat-{_h(cat)}"{open_attr}>',
        '<summary>',
        f'<span class="cat-name">{_h(cat)}</span>',
        f'<span class="cat-meta">{len(items)} tables, {total_rows:,} rows</span>',
        '</summary>',
        '<div class="cat-body">',
    ]
    for name, _, _ in items:
        sec_html = table_sections.get(name)
        if sec_html:
            parts.append(sec_html)
    parts.append('</div></details>')
    return '\n'.join(parts)


def _sidecar_category(out_dir: str, sidecar_rel: str = '.') -> str:
    """Render the sidecars category as <details class='category'>.

    sidecar_rel: relative path from rendered HTML to data dir, used to
    construct download links. Default '.' for legacy callers.
    """
    body_parts = []
    counts = []
    prefix = '' if sidecar_rel in ('.', '') else sidecar_rel.rstrip('/') + '/'

    src_dir = os.path.join(out_dir, 'shader_src')
    if os.path.isdir(src_dir):
        files = os.listdir(src_dir)
        files.sort(key=lambda f: int(f.split('.', 1)[0]) if f.split('.', 1)[0].isdigit() else 0)
        counts.append(f'shader_src {len(files)}')
        body_parts.append(f'<h3>shader_src ({len(files)} files)</h3>')
        body_parts.append('<ul class="sidecar-list">')
        for f in files:
            sz = os.path.getsize(os.path.join(src_dir, f))
            sz_str = f'{sz // 1024}K' if sz >= 1024 else f'{sz}B'
            body_parts.append(f'<li><a href="{prefix}shader_src/{_h(f)}">{_h(f)}</a><span>{sz_str}</span></li>')
        body_parts.append('</ul>')

    hist_dir = os.path.join(out_dir, 'histogram')
    if os.path.isdir(hist_dir):
        files = sorted(os.listdir(hist_dir))
        if files:
            counts.append(f'histogram {len(files)}')
            body_parts.append(f'<h3>histogram ({len(files)} files)</h3>')
            body_parts.append('<ul class="sidecar-list">')
            for f in files:
                body_parts.append(f'<li><a href="{prefix}histogram/{_h(f)}">{_h(f)}</a></li>')
            body_parts.append('</ul>')

    for jsonl in ('frame_metadata.jsonl', 'uniforms_per_pass.jsonl'):
        p = os.path.join(out_dir, jsonl)
        if os.path.exists(p):
            counts.append(jsonl)
            body_parts.append(f'<h3>{_h(jsonl)}</h3>')
            body_parts.append(f'<p><a href="{prefix}{_h(jsonl)}">download</a> '
                              f'<span class="ct">{_file_size_label(p)}</span></p>')

    if not body_parts:
        return ''

    meta = ' / '.join(counts)
    return ('<details class="category" id="cat-sidecars">'
            '<summary>'
            '<span class="cat-name">sidecars</span>'
            f'<span class="cat-meta">{_h(meta)}</span>'
            '</summary>'
            '<div class="cat-body">'
            + '\n'.join(body_parts)
            + '</div></details>')


def _read_gl_renderer(out_dir: str) -> str:
    p = os.path.join(out_dir, 'frame_metadata.jsonl')
    if not os.path.exists(p):
        return ''
    try:
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                s = o.get('gl_renderer_string') or o.get('gl_renderer') or ''
                if s:
                    return s
    except OSError:
        pass
    return ''


def render_drop(drill_dir: str, *, data_dir: str,
                area: str, drop_date: str, drop_label: str,
                captures: list[str], schema_version: int, build_timestamp: str,
                row_counts: dict[str, int]) -> str:
    """Render the per-drop browser HTML into drill_dir, reading data from data_dir.

    drill_dir: <root>/_reports/drill/<area>/<drop>/  (HTML output target)
    data_dir:  <root>/_data/<area>/<drop>/           (parquet + sidecars source)

    Returns path to drill_dir/index.html. Sidecar links (shader_src, histogram)
    point at data_dir via relative path.
    """
    total_rows = sum(row_counts.values())

    table_specs: list[tuple[str, int, int]] = []
    for table_name, n in sorted(row_counts.items()):
        if n <= 0:
            continue
        pq = os.path.join(data_dir, f'{table_name}.parquet')
        if not os.path.exists(pq):
            continue
        n_cols = len(papq.read_schema(pq).names)
        table_specs.append((table_name, n, n_cols))

    # Load labels sidecar (small JSON) from data_dir
    labels_path = os.path.join(data_dir, '_resource_labels.json')
    labels_json = '{}'
    if os.path.exists(labels_path):
        with open(labels_path, 'r', encoding='utf-8') as f:
            labels_json = f.read()

    drop_key = f'{drop_date}_{drop_label}' if drop_label else drop_date
    gl_renderer = _read_gl_renderer(data_dir)

    kpis = [
        {'label': 'rows total',  'value': reports_base.fmt_int(total_rows)},
        {'label': 'captures',    'value': reports_base.fmt_int(len(captures))},
        {'label': 'tables',      'value': reports_base.fmt_int(len(table_specs))},
    ]

    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">']
    parts.append(f'<title>{_h(area)} {_h(drop_date)}</title>')
    parts.append(f'<link rel="icon" href="{reports_base._FAVICON_HREF}">')
    parts.append(f'<style>{_CSS}</style></head>'
                 f'<body data-page-kind="drop-browser" style="--hdr-offset: 120px">')

    parts.append(f'<h1>{_h(area)} / {_h(drop_key)}</h1>')
    parts.append('<header class="strip">')
    parts.append(f'<span>area <strong>{_h(area)}</strong></span>')
    parts.append(f'<span>drop <strong>{_h(drop_key)}</strong></span>')
    parts.append(f'<span>rows <strong>{total_rows:,}</strong></span>')
    parts.append(f'<span>built <strong>{_h(build_timestamp)}</strong></span>')
    parts.append('</header>')
    # drill_dir = <root>/_reports/drill/<area>/<drop>/ → up 4 to reach <root>
    parts.append('<nav class="crumb">'
                 '<a href="../../../../index.html" data-link-kind="crumb">root catalog</a>'
                 '<a href="../../../index.html" data-link-kind="crumb">dashboard</a>'
                 '</nav>')

    # Summary bar: per-drop aggregates
    n_passes = row_counts.get('passes', 0)
    n_draws = row_counts.get('draws', 0)
    parts.append(reports_base.summary_bar(
        'this drop',
        f'{_h(area)} / {_h(drop_key)}',
        sub=f'{reports_base.fmt_int(n_draws)} draws; {reports_base.fmt_int(n_passes)} passes; {reports_base.fmt_int(len(captures))} captures',
        tone='neutral',
    ))

    if gl_renderer:
        parts.append(f'<div class="device-strip">{_h(gl_renderer)}</div>')

    parts.append(reports_base.kpi_strip(kpis))

    by_cat = _categorize(table_specs)
    parts.append(_toc(by_cat))

    # Compute relative path from drill_dir → data_dir for sidecar/shader_src links.
    data_rel = os.path.relpath(data_dir, drill_dir).replace('\\', '/')

    table_sections: dict[str, str] = {}
    scripts: list[str] = []
    for name, _, _ in table_specs:
        result = _inline_table_with_data(name, data_dir, sidecar_rel=data_rel)
        if result is None:
            continue
        sec, scr = result
        table_sections[name] = sec
        scripts.append(scr)

    for cat in _CATEGORY_ORDER:
        if cat == 'sidecars':
            sidecar_html = _sidecar_category(data_dir, sidecar_rel=data_rel)
            if sidecar_html:
                parts.append(sidecar_html)
            continue
        block = _category_block(cat, by_cat.get(cat, []), table_sections,
                                 is_open=(cat in _DEFAULT_OPEN))
        if block:
            parts.append(block)

    parts.append(f'<script>window.__labels={labels_json};</script>')
    parts.extend(scripts)
    parts.append(f'<script>{_JS}</script>')
    parts.append('</body></html>')

    out_path = os.path.join(drill_dir, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return out_path


def render_root(root: str) -> str:
    from .. import paths as _paths
    cat_pq = _paths.catalog_parquet(root)
    cat_json = _paths.catalog_json(root)
    root_index = _paths.root_index_html(root)
    if not os.path.exists(cat_pq):
        with open(root_index, 'w', encoding='utf-8') as f:
            f.write('<!doctype html><html><body>no catalog yet</body></html>')
        return root_index

    t = papq.read_table(cat_pq)
    summary = {}
    if os.path.exists(cat_json):
        with open(cat_json, 'r', encoding='utf-8') as f:
            summary = json.load(f)

    cols = t.column_names
    arrays = [t.column(c).to_pylist() for c in cols]
    n = t.num_rows
    rows = [[arrays[ci][ri] for ci in range(len(cols))] for ri in range(n)]

    # analysis_out_path column stored relative under _data/. Transform link
    # target to the per-drop browser at _reports/drill/<area>/<drop>/index.html.
    path_idx = cols.index('analysis_out_path') if 'analysis_out_path' in cols else -1
    if path_idx >= 0:
        for r in rows:
            v = str(r[path_idx])
            # Replace leading "_data/" with "_reports/drill/" and append index.html.
            if v.startswith(_paths.DATA_DIR + '/') or v.startswith(_paths.DATA_DIR + '\\'):
                drill_rel = (_paths.REPORTS_DIR + '/' + _paths.DRILL_DIR + '/'
                             + v[len(_paths.DATA_DIR) + 1:].replace('\\', '/'))
            elif os.path.isabs(v):
                drill_rel = os.path.relpath(
                    _paths.drop_dir_to_drill_dir(v), root).replace('\\', '/')
            else:
                drill_rel = v.replace('\\', '/')
            r[path_idx] = drill_rel.rstrip('/') + '/index.html'

    payload = {'cols': cols, 'rows': rows, 'labelCols': {}}

    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">']
    parts.append('<title>capture analysis catalog</title>')
    parts.append(f'<link rel="icon" href="{reports_base._FAVICON_HREF}">')
    parts.append(f'<style>{_CSS}</style></head><body style="--hdr-offset: 120px">')
    parts.append('<header class="strip">')
    parts.append(f'<span>built <strong>{_h(summary.get("build_timestamp", ""))}</strong></span>')
    parts.append(f'<span>drops <strong>{summary.get("drop_count", 0)}</strong></span>')
    parts.append('</header>')

    # Summary bar: latest drop + area/capture counts
    area_idx = cols.index('area') if 'area' in cols else -1
    date_idx = cols.index('drop_date') if 'drop_date' in cols else -1
    label_idx = cols.index('drop_label') if 'drop_label' in cols else -1
    unique_areas: set = set()
    latest_date = ''
    latest_label = ''
    for r in rows:
        if area_idx >= 0 and r[area_idx]:
            unique_areas.add(str(r[area_idx]))
        if date_idx >= 0 and r[date_idx]:
            dval = str(r[date_idx])
            if dval > latest_date:
                latest_date = dval
                latest_label = str(r[label_idx]) if label_idx >= 0 else ''
    if latest_date:
        head_text = f'{latest_date}'
        if latest_label:
            head_text = f'{latest_date} / {latest_label}'
        parts.append(reports_base.summary_bar(
            'latest drop',
            head_text,
            sub=f'{len(unique_areas)} areas; {n} catalog rows',
            link_href=f'{_paths.REPORTS_DIR}/{_paths.INDEX_HTML}',
            link_text='dashboard',
            tone='neutral',
        ))

    # Reports section
    reports_dir = _paths.reports_dir(root)
    if os.path.isdir(reports_dir):
        dashboard = os.path.join(reports_dir, _paths.INDEX_HTML)
        if os.path.exists(dashboard):
            parts.append('<section><h2 id="dashboard">dashboard</h2>'
                         '<div class="chip-cluster">'
                         f'<a href="{_paths.REPORTS_DIR}/{_paths.INDEX_HTML}" data-link-kind="primary">'
                         'cumulative reports dashboard</a>'
                         '</div></section>')

        report_files = sorted(
            f for f in os.listdir(reports_dir)
            if f.endswith('.html') and f != _paths.INDEX_HTML
        )
        if report_files:
            parts.append('<section><h2 id="reports">reports</h2>'
                         '<div class="catalog-grid">')
            for f in report_files:
                parts.append(f'<a href="{_paths.REPORTS_DIR}/{_h(f)}" data-link-kind="primary">'
                             f'{_h(f[:-5])}</a>')
            parts.append('</div></section>')

        ab_dir = os.path.join(reports_dir, _paths.AB_DIR)
        if os.path.isdir(ab_dir):
            pairs = sorted(
                d for d in os.listdir(ab_dir)
                if os.path.isdir(os.path.join(ab_dir, d))
            )
            if pairs:
                parts.append('<section><h2 id="ab">a/b comparisons</h2>'
                             '<div class="pair-list">')
                for pair in pairs:
                    pair_files = sorted(
                        f for f in os.listdir(os.path.join(ab_dir, pair))
                        if f.endswith('.html')
                    )
                    chips = ''.join(
                        f'<a href="{_paths.REPORTS_DIR}/{_paths.AB_DIR}/{_h(pair)}/{_h(f)}" data-link-kind="primary">'
                        f'{_h(f[:-5])}</a>'
                        for f in pair_files
                    )
                    parts.append(
                        f'<div class="pair-group">'
                        f'<h3>{_h(pair)}</h3>'
                        f'<div class="chip-cluster">{chips}</div>'
                        f'</div>'
                    )
                parts.append('</div></section>')

    parts.append('<section><h2>catalog</h2>')
    parts.append('<div class="controls">')
    parts.append('<input type="search" placeholder="filter">')
    parts.append('<span class="ct visible-count"></span>')
    parts.append(f'<a class="dl" href="{_paths.DATA_DIR}/_catalog.csv" data-link-kind="inline">CSV</a>')
    parts.append(f'<a class="dl" href="{_paths.DATA_DIR}/_catalog.parquet" data-link-kind="inline">parquet</a>')
    parts.append('</div>')
    parts.append(f'<div class="table-scroll" data-table="catalog"></div>')
    parts.append('</section>')

    parts.append(f'<script>window.__data_catalog={json.dumps(payload, separators=(",", ":"))};</script>')
    parts.append(f'<script>window.__labels={{}};</script>')
    parts.append(f'<script>{_JS}</script>')
    parts.append('</body></html>')

    out_path = root_index
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return out_path
