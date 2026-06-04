
(function(){
  const ROW_H = 32;
  const BUFFER = 8;

  // For ID kinds: where to jump when an ID cell is clicked (virtual mode).
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

  // SHARED comparator (ADR-24 natural-numeric). The comma-strip makes the numeric branch correct for
  // BOTH raw JSON numbers (virtual) and comma-formatted display text (static); the {numeric:true}
  // localeCompare natural-sorts mixed alphanumerics ("Mali-G78" < "Mali-G710"). Nulls sort last.
  function cmpVals(aa, bb, isNum, dir){
    if (aa == null && bb == null) return 0;
    if (aa == null) return 1;
    if (bb == null) return -1;
    if (isNum){
      const na = Number(String(aa).replace(/,/g, '')), nb = Number(String(bb).replace(/,/g, ''));
      const aok = na === na, bok = nb === nb;
      if (!aok && !bok) return 0;
      if (!aok) return 1;
      if (!bok) return -1;
      return (na - nb) * dir;
    }
    return String(aa).localeCompare(String(bb), undefined, {numeric: true}) * dir;
  }

  // SHARED heatmap tint: a UNIFORM color-mix shade as a background-IMAGE (so the class-driven
  // background-COLOR zebra/hover still shows through). tt is a pre-clamped magnitude in [0,1].
  function tintImage(tt){
    const c = 'color-mix(in oklch, var(--accent-data) ' + Math.round(tt * 30) + '%, transparent)';
    return 'linear-gradient(' + c + ', ' + c + ')';
  }

  // SHARED sort-header wiring (c16o, ADR-38 a11y tail). One contract for BOTH modes: the sortable
  // <th> (implicit role columnheader - where aria-sort belongs) is made keyboard-operable
  // (tabindex 0 + Enter/Space) on top of its click. cursor:pointer already comes from the
  // `table.data thead th` CSS rule, so it is not re-set here. onSort(ci) is the mode's own sort.
  function wireSortHeader(th, ci, onSort){
    th.setAttribute('tabindex', '0');
    th.addEventListener('click', () => onSort(ci));
    th.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); onSort(ci); }
    });
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

  // ---- VTable: virtual mode (windowed; rows come from the externalized _pagedata payload) ----
  class VTable {
    constructor(host, payload, labels, groups){
      this.host = host;
      this.cols = payload.cols;
      this.rows = payload.rows;
      this.labelCols = payload.labelCols || {};
      this.labels = labels;
      this.groups = groups || null;  // catalog-only column groups (c16i); null elsewhere
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

      // Type split (c16i): non-numeric ID/hash/path columns render mono. Decided by column NAME.
      this.monoCols = new Set();
      const MONO_RE = /(_id|_hash|_hex)$|^stable_key$|.*_path$|^capture$/;
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci) && MONO_RE.test(this.cols[ci])) this.monoCols.add(ci);
      }
      // c16m: known-long non-numeric columns get the WIDE clip tier (src paths, hashes, stable_keys);
      // other non-numeric columns get the default clip tier. Numeric cells are never clipped.
      this.wideCols = new Set();
      const WIDE_RE = /(_hash|_hex)$|^stable_key$|.*_path$/;
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci) && WIDE_RE.test(this.cols[ci])) this.wideCols.add(ci);
      }

      // Heatmap (c16i): per-column min/max for numeric MAGNITUDE columns. Exclude ID/reference cols
      // and cross-link label cols. Scanned over ALL rows so the scale is stable across sort/filter.
      const ID_RE = /_id$|^event_id$/;
      this.colStats = {};
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci)) continue;
        if (ID_RE.test(this.cols[ci]) || this.labelCols[this.cols[ci]]) continue;
        let lo = Infinity, hi = -Infinity, seen = 0;
        for (let ri = 0; ri < this.rows.length; ri++){
          const v = this.rows[ri][ci];
          if (v == null || v === '') continue;
          const n = +v;
          if (n !== n) continue;  // NaN guard
          if (n < lo) lo = n;
          if (n > hi) hi = n;
          seen++;
        }
        if (seen > 0 && hi > lo) this.colStats[ci] = {lo: lo, hi: hi};
      }

      // Collapsible column groups (c16i, catalog only).
      this.hiddenCols = new Set();
      this.colByName = {};
      for (let i = 0; i < this.cols.length; i++) this.colByName[this.cols[i]] = i;
      if (this.groups){
        this.groups.forEach(g => {
          if (!g.open){
            g.cols.forEach(c => {
              const ci = (typeof c === 'number') ? c : this.colByName[c];
              if (ci != null) this.hiddenCols.add(ci);
            });
          }
        });
      }

      this.slotKindCol = this.cols.indexOf('slot_kind');
      this.descriptorKindCol = this.cols.indexOf('descriptor_kind');

      this.build();
    }

    buildHead(){
      const tr = this.headRow;
      while (tr.firstChild) tr.removeChild(tr.firstChild);
      for (let i = 0; i < this.cols.length; i++){
        if (this.hiddenCols.has(i)) continue;
        const th = document.createElement('th');
        th.dataset.ci = i;
        th.appendChild(document.createTextNode(this.cols[i]));
        if (this.numericCols.has(i)) th.classList.add('numeric');
        const arrow = document.createElement('span');
        arrow.className = 'sort-arrow';
        if (i === this.sortCol) arrow.textContent = this.sortDir > 0 ? ' ▲' : ' ▼';
        th.appendChild(arrow);
        // a11y (c16o): announce sort state + keep it correct across group-toggle rebuilds.
        th.setAttribute('aria-sort', (i === this.sortCol) ? (this.sortDir > 0 ? 'ascending' : 'descending') : 'none');
        wireSortHeader(th, i, (ci) => this.sort(ci));
        tr.appendChild(th);
      }
    }

    buildGroupBar(){
      if (!this.groups) return;
      const section = this.host.closest('section');
      const bar = section ? section.querySelector('.col-groups') : null;
      if (!bar) return;
      this.groups.forEach(g => {
        const cis = g.cols.map(c => (typeof c === 'number') ? c : this.colByName[c]).filter(x => x != null);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'col-group-toggle';
        btn.dataset.group = g.name;
        btn.textContent = g.name;
        btn.setAttribute('aria-pressed', g.open ? 'true' : 'false');
        btn.addEventListener('click', () => {
          const next = btn.getAttribute('aria-pressed') !== 'true';
          btn.setAttribute('aria-pressed', next ? 'true' : 'false');
          cis.forEach(ci => { if (next) this.hiddenCols.delete(ci); else this.hiddenCols.add(ci); });
          this.buildHead();
          this.render();
        });
        bar.appendChild(btn);
      });
    }

    build(){
      const table = document.createElement('table');
      table.className = 'data';
      const thead = table.createTHead();
      this.headRow = thead.insertRow();
      this.buildHead();
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

      this.buildGroupBar();

      this.host.addEventListener('scroll', () => this.render());
      window.addEventListener('resize', () => this.render());
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
      requestAnimationFrame(() => this.render());
      setTimeout(() => this.render(), 50);
    }

    sort(ci){
      if (this.sortCol === ci) this.sortDir = -this.sortDir;
      else { this.sortCol = ci; this.sortDir = 1; }
      const dir = this.sortDir;
      const isNum = this.numericCols.has(ci);
      this.view.sort((a, b) => cmpVals(a[ci], b[ci], isNum, dir));
      const headers = this.host.querySelectorAll('thead th');
      for (let k = 0; k < headers.length; k++){
        const match = (+headers[k].dataset.ci === ci);
        const a = headers[k].querySelector('.sort-arrow');
        if (a) a.textContent = match ? (dir > 0 ? ' ▲' : ' ▼') : '';
        headers[k].setAttribute('aria-sort', match ? (dir > 0 ? 'ascending' : 'descending') : 'none');  // a11y (c16o)
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
      if (this.sortCol >= 0){
        const ci = this.sortCol, dir = this.sortDir;
        const isNum = this.numericCols.has(ci);
        this.view.sort((a, b) => cmpVals(a[ci], b[ci], isNum, dir));
      }
      this.host.scrollTop = 0;
      this.render();
    }

    cellNode(value, ri, ci){
      const td = document.createElement('td');
      if (this.numericCols.has(ci)) td.classList.add('numeric');
      else if (this.monoCols.has(ci)) td.classList.add('mono');

      const colName = this.cols[ci];
      const lc = this.labelCols[colName];
      let kind = lc;
      if (kind === 'auto_by_slot_kind' && this.slotKindCol >= 0){
        kind = autoKindForSlot(this.view[ri][this.slotKindCol]);
      } else if (kind === 'auto_by_kind' && this.descriptorKindCol >= 0){
        kind = autoKindForDescriptor(this.view[ri][this.descriptorKindCol]);
      }

      const formatted = fmt(value);
      // c16m: clip non-numeric cells on an inner element (the <a>, or a <span class="clip">) so the
      // .lbl label + heatmap background (set on the td below) ride OUTSIDE the clip and stay visible.
      // Numeric cells are never clipped. Re-applied every windowed render() (cellNode rebuilds nodes).
      const clipCls = this.numericCols.has(ci) ? '' : (this.wideCols.has(ci) ? 'clip clip-wide' : 'clip');
      const link = LINK_TARGET[kind];
      if (link && value != null && value !== '' && value !== 0 && value !== '0' && kind !== 'texture_list'){
        const a = document.createElement('a');
        a.href = '#' + link.table;
        a.textContent = formatted;
        a.title = 'jump to ' + link.table + ' filtered to ' + link.col + '=' + value;
        if (clipCls) a.className = clipCls;   // truncate long link text; keep the nav title
        a.addEventListener('click', (ev) => {
          ev.preventDefault();
          jumpToTable(link.table, String(value));
        });
        td.appendChild(a);
      } else if (clipCls){
        const span = document.createElement('span');
        span.className = clipCls;
        span.textContent = formatted;
        if (formatted && formatted.length > (this.wideCols.has(ci) ? 64 : 40)) span.title = formatted;
        td.appendChild(span);
      } else {
        td.textContent = formatted;
      }

      const stat = this.colStats[ci];
      if (stat != null && value != null && value !== ''){
        const n = +value;
        if (n === n){
          let tt = (n - stat.lo) / (stat.hi - stat.lo);
          tt = tt < 0 ? 0 : (tt > 1 ? 1 : tt);
          const pct = Math.round(tt * 100);
          td.style.backgroundImage = tintImage(tt);
          td.setAttribute('aria-label', formatted + ' (' + pct + '% of column max)');
        }
      }

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

      while (this.sTop.nextSibling !== this.sBot){
        this.tbody.removeChild(this.sTop.nextSibling);
      }
      const visible = this.cols.length - this.hiddenCols.size;
      this.tdTop.colSpan = visible;
      this.tdBot.colSpan = visible;
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
          if (this.hiddenCols.has(ci)) continue;
          tr.appendChild(this.cellNode(row[ci], i, ci));
        }
        frag.appendChild(tr);
      }
      this.tbody.insertBefore(frag, this.sBot);
    }
  }

  // ---- StaticTable: static mode (in-place; rows are server-baked) ----
  // Enhances an existing server-baked table.data WITHOUT removing rows from the DOM, so JS-off / print /
  // Ctrl-F keep every row (ADR-37). Sort reorders the live <tr> nodes (nested components ride along);
  // heatmap tints existing numeric <td>s; column-groups toggle display. Numeric cols are read from
  // the header class (no value-sniff); column groups come from window.__colgroups_<data-table> and
  // may key by column INDEX (reports, where header text can repeat) or NAME (the catalog path).
  class StaticTable {
    constructor(host){
      this.host = host;
      const table = host.querySelector('table');
      if (!table) return;
      this.table = table;
      const thead = table.tHead;
      this.ths = (thead && thead.rows[0]) ? Array.prototype.slice.call(thead.rows[0].cells) : [];
      this.cols = this.ths.map(th => th.textContent.trim());
      this.colByName = {};
      for (let i = 0; i < this.cols.length; i++) this.colByName[this.cols[i]] = i;
      this.tbody = table.tBodies[0];
      if (!this.tbody) return;
      this.trNodes = Array.prototype.slice.call(this.tbody.rows);
      this.sortCol = -1; this.sortDir = 1;
      this.hiddenCols = new Set();

      // numeric columns from header class (.numeric, or legacy .num from report markup)
      this.numericCols = new Set();
      this.ths.forEach((th, ci) => {
        if (th.classList.contains('numeric') || th.classList.contains('num')) this.numericCols.add(ci);
      });

      // colStats for the auto-heatmap (comma-stripped values). Skip a column whose cells already
      // carry an <rdc-heatmap-cell> (already shaded) so we never double-tint.
      this.colStats = {};
      for (let ci = 0; ci < this.cols.length; ci++){
        if (!this.numericCols.has(ci)) continue;
        const first = this.trNodes.length ? this.trNodes[0].cells[ci] : null;
        if (first && first.querySelector('rdc-heatmap-cell')) continue;
        let lo = Infinity, hi = -Infinity, seen = 0;
        for (let ri = 0; ri < this.trNodes.length; ri++){
          const cell = this.trNodes[ri].cells[ci];
          if (!cell) continue;
          const t = cell.textContent.trim();
          if (t === '') continue;
          const n = Number(t.replace(/,/g, ''));
          if (n !== n) continue;
          if (n < lo) lo = n;
          if (n > hi) hi = n;
          seen++;
        }
        if (seen > 0 && hi > lo) this.colStats[ci] = {lo: lo, hi: hi};
      }

      this._wireHeaders();
      this._applyHeatmap();
      this._buildGroups();

      // default sort (data-default-sort = header text; data-default-dir = asc|desc, default desc)
      const def = host.dataset.defaultSort;
      if (def){
        let idx = -1;
        for (let i = 0; i < this.cols.length; i++){
          if (this.cols[i].toLowerCase() === def.toLowerCase()){ idx = i; break; }
        }
        if (idx >= 0){
          this.sortCol = idx;
          this.sortDir = (host.dataset.defaultDir === 'asc') ? 1 : -1;
          this._paintSort(idx);
        }
      }
    }

    _wireHeaders(){
      this.ths.forEach((th, ci) => {
        th.setAttribute('aria-sort', 'none');   // a11y: report sort state (c16l - was on rdc-sortable-table)
        let arrow = th.querySelector('.sort-arrow');
        if (!arrow){ arrow = document.createElement('span'); arrow.className = 'sort-arrow'; th.appendChild(arrow); }
        wireSortHeader(th, ci, (i) => this.sort(i));   // a11y (c16o): keyboard-operable (shared with VTable)
      });
    }

    sort(ci){
      if (this.sortCol === ci) this.sortDir = -this.sortDir;
      else { this.sortCol = ci; this.sortDir = 1; }
      this._paintSort(ci);
    }

    _paintSort(ci){
      const dir = this.sortDir, isNum = this.numericCols.has(ci);
      const getv = (tr) => { const c = tr.cells[ci]; const t = c ? c.textContent.trim() : ''; return t === '' ? null : t; };
      this.trNodes.sort((ra, rb) => cmpVals(getv(ra), getv(rb), isNum, dir));
      const frag = document.createDocumentFragment();
      this.trNodes.forEach(tr => frag.appendChild(tr));
      this.tbody.appendChild(frag);
      this.ths.forEach((th, k) => {
        const a = th.querySelector('.sort-arrow');
        if (a) a.textContent = (k === ci) ? (dir > 0 ? ' ▲' : ' ▼') : '';
        th.setAttribute('aria-sort', (k === ci) ? (dir > 0 ? 'ascending' : 'descending') : 'none');
      });
    }

    _applyHeatmap(){
      for (const k in this.colStats){
        const ci = +k, stat = this.colStats[ci];
        this.trNodes.forEach(tr => {
          const td = tr.cells[ci];
          if (!td) return;
          const t = td.textContent.trim();
          if (t === '') return;
          const n = Number(t.replace(/,/g, ''));
          if (n !== n) return;
          let tt = (n - stat.lo) / (stat.hi - stat.lo);
          tt = tt < 0 ? 0 : (tt > 1 ? 1 : tt);
          td.style.backgroundImage = tintImage(tt);
          td.setAttribute('aria-label', t + ' (' + Math.round(tt * 100) + '% of column max)');
        });
      }
    }

    _buildGroups(){
      const groups = window['__colgroups_' + (this.host.dataset.table || '')];
      if (!groups) return;
      const section = this.host.closest('section');
      const bar = section ? section.querySelector('.col-groups') : null;
      if (!bar) return;
      const idx = (c) => (typeof c === 'number') ? c : this.colByName[c];
      groups.forEach(g => {
        if (!g.open) g.cols.forEach(c => { const ci = idx(c); if (ci != null) this.hiddenCols.add(ci); });
      });
      this._applyVisibility();
      groups.forEach(g => {
        const cis = g.cols.map(idx).filter(x => x != null);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'col-group-toggle';
        btn.dataset.group = g.name;
        btn.textContent = g.name;
        btn.setAttribute('aria-pressed', g.open ? 'true' : 'false');
        btn.addEventListener('click', () => {
          const next = btn.getAttribute('aria-pressed') !== 'true';
          btn.setAttribute('aria-pressed', next ? 'true' : 'false');
          cis.forEach(ci => { if (next) this.hiddenCols.delete(ci); else this.hiddenCols.add(ci); });
          this._applyVisibility();
        });
        bar.appendChild(btn);
      });
    }

    _applyVisibility(){
      this.ths.forEach((th, ci) => { th.style.display = this.hiddenCols.has(ci) ? 'none' : ''; });
      this.trNodes.forEach(tr => {
        for (let ci = 0; ci < tr.cells.length; ci++){
          tr.cells[ci].style.display = this.hiddenCols.has(ci) ? 'none' : '';
        }
      });
    }
  }

  function jumpToTable(tableName, idValue){
    const host = document.querySelector('rdc-table[data-table="' + tableName + '"]');
    if (!host || !host._vt) return;
    const section = host.closest('section');
    const input = section ? section.querySelector('input[type=search]') : null;
    if (input){
      input.value = idValue;
      host._vt.filter(idValue);
      const counter = section.querySelector('.ct.visible-count');
      if (counter){
        const v = host._vt.view.length, t = host._vt.rows.length;
        counter.textContent = v.toLocaleString() + ' / ' + t.toLocaleString() + ' visible';
      }
    }
    if (section) section.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  window.__jumpToTable = jumpToTable;

  // c16m: global expand/wrap toggle. Built in JS (enhancement) only when the table actually carries
  // clippable cells (no dead button on simple tables). Inserted before the host so it sits above the
  // table (static) / scroll box (virtual). Click flips data-expand on the host; the CSS does the rest
  // (full-width single line in both modes; static also wraps - virtual keeps one line so the windowed
  // ROW_H stays valid). JS-off: no toggle, but clip + title= + Ctrl-F keep nothing hidden.
  function buildExpandToggle(host){
    if (host._expandWired || !host.querySelector('.clip')) return;
    host._expandWired = true;
    const bar = document.createElement('div');
    bar.className = 'rdc-controls';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'rdc-expand-toggle';
    btn.textContent = 'Expand cells';
    btn.setAttribute('aria-pressed', 'false');
    btn.addEventListener('click', () => {
      const next = btn.getAttribute('aria-pressed') !== 'true';
      btn.setAttribute('aria-pressed', next ? 'true' : 'false');
      if (next) host.dataset.expand = 'true'; else host.removeAttribute('data-expand');
    });
    bar.appendChild(btn);
    if (host.parentNode) host.parentNode.insertBefore(bar, host);
  }

  window.addEventListener('DOMContentLoaded', () => {
    const labels = window.__labels || {};
    document.querySelectorAll('rdc-table[data-mode]').forEach(host => {
      if (host.dataset.mode === 'static'){
        host._vt = new StaticTable(host);
        buildExpandToggle(host);
        return;
      }
      // virtual
      const name = host.dataset.table;
      const payload = window['__data_' + name];
      if (!payload){ return; }
      const labelsForTable = Object.assign({}, labels);
      labelsForTable.capture = host.dataset.capture || (payload.rows[0] ? payload.rows[0][3] : '');
      const groups = window['__colgroups_' + name];
      const vt = new VTable(host, payload, labelsForTable, groups);
      host._vt = vt;
      buildExpandToggle(host);

      const section = host.closest('section');
      const input = section ? section.querySelector('input[type=search]') : null;
      const counter = section ? section.querySelector('.ct.visible-count') : null;
      if (counter){
        function updateCounter(){
          const v = vt.view.length, t = vt.rows.length;
          counter.textContent = v.toLocaleString() + ' / ' + t.toLocaleString() + ' visible';
        }
        updateCounter();
        if (input){
          let timer = null;
          input.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => { vt.filter(input.value); updateCounter(); }, 80);
          });
        }
      }
    });
  });
})();
