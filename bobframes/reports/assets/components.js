
(function(){
  if (typeof customElements === 'undefined') return;

  class RdcBase extends HTMLElement {
    connectedCallback(){
      if (this._rdcUp) return;
      this._rdcUp = true;
      const run = () => {
        try { this.init(); } catch(e) { console.error('rdc init error', this.tagName, e); }
      };
      // The component JS rides in <head> (adjacent to the CSS), so a custom element upgrades as its
      // START tag is parsed -- BEFORE its light-DOM children (e.g. the run <select>) exist. Inits that
      // querySelector a child would see nothing and bail. Defer to DOMContentLoaded while the document
      // is still parsing so children are present; run immediately for elements created after load.
      // (Mirrors the _wireRowDrill deferral below.)
      if (document.readyState === 'loading'){
        document.addEventListener('DOMContentLoaded', run, { once: true });
      } else {
        run();
      }
    }
    init(){}
  }

  class RdcCopyButton extends RdcBase {
    init(){
      const value = this.dataset.value || '';
      const label = this.dataset.label || ('copy ' + value);
      this.setAttribute('role', 'button');
      this.setAttribute('tabindex', '0');
      this.setAttribute('aria-label', label);
      const handler = async () => {
        try {
          await navigator.clipboard.writeText(value);
        } catch (e) {
          const ta = document.createElement('textarea');
          ta.value = value;
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand('copy'); } catch(e2){}
          ta.remove();
        }
        this.classList.add('copied');
        setTimeout(() => this.classList.remove('copied'), 1000);
      };
      this.addEventListener('click', handler);
      this.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' '){
          e.preventDefault();
          handler();
        }
      });
    }
  }
  customElements.define('rdc-copy-button', RdcCopyButton);

  class RdcStickyH2 extends RdcBase {
    init(){
      const h2 = this.querySelector('h2');
      if (!h2) return;
      const io = new IntersectionObserver((entries) => {
        entries.forEach(e => {
          if (e.isIntersecting){
            h2.setAttribute('aria-current', 'section');
          } else {
            h2.removeAttribute('aria-current');
          }
        });
      }, { rootMargin: '-50% 0px -50% 0px', threshold: 0 });
      io.observe(h2);
    }
  }
  customElements.define('rdc-sticky-h2', RdcStickyH2);

  class RdcHeatmapCell extends RdcBase {
    init(){
      const v = parseFloat(this.dataset.value);
      const lo = parseFloat(this.dataset.min);
      const hi = parseFloat(this.dataset.max);
      const dir = this.dataset.direction || 'hot';
      if (isNaN(v) || isNaN(lo) || isNaN(hi) || hi <= lo) return;
      let t = (v - lo) / (hi - lo);
      if (dir === 'cold') t = 1 - t;
      t = Math.max(0, Math.min(1, t));
      const pct = Math.round(t * 25);
      this.style.background = 'color-mix(in oklch, var(--accent-data) ' + pct + '%, transparent)';
      if (t >= 0.72){
        this.style.color = 'light-dark(black, white)';
      }
      this.setAttribute('aria-label', v + ' (relative ' + Math.round(t * 100) + '%)');
    }
  }
  customElements.define('rdc-heatmap-cell', RdcHeatmapCell);

  class RdcRowDrill extends RdcBase {
    init(){
      const href = this.dataset.href;
      if (!href) return;
      this.setAttribute('role', 'link');
      this.setAttribute('tabindex', '0');
      this.style.cursor = 'pointer';
      const go = (ev) => {
        if (ev.target && ev.target.closest('a')) return;
        if (ev.target && ev.target.closest('rdc-copy-button')) return;
        window.location.href = href;
      };
      this.addEventListener('click', go);
      this.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter'){
          ev.preventDefault();
          window.location.href = href;
        }
      });
    }
  }
  customElements.define('rdc-row-drill', RdcRowDrill);

  class RdcSearchCards extends RdcBase {
    init(){
      const target = this.dataset.target || '.dash-grid';
      const cards = document.querySelectorAll(target + ' > *');
      const input = this.querySelector('input');
      if (!input || !cards.length) return;
      const counter = this.querySelector('.rdc-count');
      const update = () => {
        const q = input.value.trim().toLowerCase();
        let shown = 0;
        cards.forEach(c => {
          const text = (c.textContent || '').toLowerCase();
          const match = !q || text.indexOf(q) >= 0;
          c.style.display = match ? '' : 'none';
          if (match) shown++;
        });
        if (counter) counter.textContent = shown + ' / ' + cards.length;
      };
      input.addEventListener('input', update);
      update();
    }
  }
  customElements.define('rdc-search-cards', RdcSearchCards);

  class RdcAlarmBanner extends RdcBase {
    init(){
      const sev = this.dataset.severity || 'high';
      const role = sev === 'high' ? 'alert' : 'status';
      this.setAttribute('role', role);
      this.setAttribute('aria-live', sev === 'high' ? 'assertive' : 'polite');
    }
  }
  customElements.define('rdc-alarm-banner', RdcAlarmBanner);

  class RdcAbPicker extends RdcBase {
    init(){
      const select = this.querySelector('select');
      if (!select) return;
      this.setAttribute('role', 'combobox');
      select.addEventListener('change', () => {
        const url = select.value;
        if (url) window.location.href = url;
      });
    }
  }
  customElements.define('rdc-ab-picker', RdcAbPicker);

  // Whole-row drill: any <tr> containing <a data-link-kind="drill"> becomes clickable.
  function _wireRowDrill(){
    const seen = new WeakSet();
    document.querySelectorAll('a[data-link-kind="drill"]').forEach(a => {
      const tr = a.closest('tr');
      if (!tr || seen.has(tr)) return;
      seen.add(tr);
      tr.addEventListener('click', (ev) => {
        if (ev.target.closest('a')) return;
        if (ev.target.closest('rdc-copy-button')) return;
        a.click();
      });
      tr.style.cursor = 'pointer';
    });
  }
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', _wireRowDrill);
  } else {
    _wireRowDrill();
  }
})();
