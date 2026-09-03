/* ─────────────────────────────────────────────────────────────────────────
   Lane Lab · frontend logic
   Home-page setup flow: pick teams · load profiles · manage roster · run.
   ──────────────────────────────────────────────────────────────────────── */

/* ─── Custom searchable combobox ────────────────────────────────────────
   Progressive enhancement: finds any <select data-combo> on the page,
   hides it, and renders a custom popup with a search box + filtered list.
   Keeps the original <select> in sync so existing code (getConfig, etc.)
   reads .value unchanged.
   ──────────────────────────────────────────────────────────────────────── */

function initCombobox(select) {
  if (select.dataset.comboReady === '1') return;
  select.dataset.comboReady = '1';

  // Build options model from the <select>
  const options = Array.from(select.options).map(o => ({
    value: o.value,
    label: o.textContent.trim(),
    selected: o.selected,
  }));

  // Wrap the select in .combo and inject combobox UI
  const wrap = document.createElement('div');
  wrap.className = 'combo';
  wrap.dataset.open = 'false';
  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(select);
  select.classList.add('combo-source');

  const placeholder = select.dataset.placeholder || 'Select...';

  wrap.insertAdjacentHTML('beforeend', `
    <button type="button" class="combo-trigger" aria-haspopup="listbox" aria-expanded="false">
      <span class="combo-value-text"></span>
      <svg class="combo-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
    </button>
    <div class="combo-popup" role="listbox">
      <div class="combo-search-wrap">
        <input type="search" class="combo-search" placeholder="Search..." autocomplete="off">
      </div>
      <div class="combo-list"></div>
    </div>
  `);

  const trigger     = wrap.querySelector('.combo-trigger');
  const valueText   = wrap.querySelector('.combo-value-text');
  const popup       = wrap.querySelector('.combo-popup');
  const searchInput = wrap.querySelector('.combo-search');
  const searchWrap  = wrap.querySelector('.combo-search-wrap');
  const list        = wrap.querySelector('.combo-list');

  // Short lists (year, week, home/away) opt out of the search box via
  // data-no-search; the trigger then handles keyboard nav directly.
  const showSearch = select.dataset.noSearch === undefined;
  if (!showSearch) searchWrap.style.display = 'none';

  let activeIndex = -1;
  let visibleOptions = [];

  function renderTrigger() {
    const sel = options.find(o => o.selected);
    if (sel && sel.value) {
      valueText.textContent = sel.label;
      valueText.classList.remove('combo-placeholder');
    } else {
      valueText.textContent = placeholder;
      valueText.classList.add('combo-placeholder');
    }
  }

  function renderList(filter) {
    const q = (filter || '').toLowerCase().trim();
    visibleOptions = options.filter(o => {
      if (!o.label) return false;
      // skip placeholder-style empty values when searching
      if (q && !o.label.toLowerCase().includes(q)) return false;
      return true;
    });
    if (visibleOptions.length === 0) {
      list.innerHTML = `<div class="combo-empty">No matches</div>`;
      activeIndex = -1;
      return;
    }
    list.innerHTML = visibleOptions.map((o, i) =>
      `<div class="combo-option" data-value="${escapeAttr(o.value)}" data-selected="${o.selected ? 'true' : 'false'}" data-active="${i === activeIndex ? 'true' : 'false'}">${escapeHtml(o.label)}</div>`
    ).join('');
  }

  function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]); }
  function escapeAttr(s) { return escapeHtml(s); }

  function open() {
    if (wrap.dataset.open === 'true') return;
    wrap.dataset.open = 'true';
    trigger.setAttribute('aria-expanded', 'true');
    searchInput.value = '';
    activeIndex = options.findIndex(o => o.selected && o.value);
    renderList('');
    if (showSearch) setTimeout(() => searchInput.focus(), 0);
    else trigger.focus();
  }
  function close() {
    wrap.dataset.open = 'false';
    trigger.setAttribute('aria-expanded', 'false');
  }
  function toggle() { wrap.dataset.open === 'true' ? close() : open(); }

  function selectOption(value) {
    options.forEach(o => o.selected = (o.value === value));
    // mirror to native <select> so onchange + getConfig work
    select.value = value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    renderTrigger();
    close();
  }

  // Shared keyboard navigation — used by the search box, and by the trigger
  // itself when search is hidden (short lists).
  function navKeydown(e) {
    if (e.key === 'Escape') { close(); trigger.focus(); }
    else if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = Math.min(visibleOptions.length - 1, activeIndex + 1);
      updateActive();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = Math.max(0, activeIndex - 1);
      updateActive();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && visibleOptions[activeIndex]) {
        selectOption(visibleOptions[activeIndex].value);
        trigger.focus();
      }
    }
  }

  trigger.addEventListener('click', toggle);
  trigger.addEventListener('keydown', (e) => {
    if (wrap.dataset.open === 'true') { navKeydown(e); return; }
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
      e.preventDefault(); open();
    }
  });

  searchInput.addEventListener('input', () => {
    activeIndex = visibleOptions.length > 0 ? 0 : -1;
    renderList(searchInput.value);
  });
  searchInput.addEventListener('keydown', navKeydown);

  // Mouse hover drives the same single 'active' highlight as the keyboard, so
  // the previously-selected row never stays highlighted next to the hovered one.
  list.addEventListener('mouseover', (e) => {
    const opt = e.target.closest('.combo-option');
    if (!opt) return;
    const idx = visibleOptions.findIndex(o => o.value === opt.dataset.value);
    if (idx >= 0 && idx !== activeIndex) { activeIndex = idx; updateActive(); }
  });

  function updateActive() {
    list.querySelectorAll('.combo-option').forEach((el, i) => {
      el.dataset.active = (i === activeIndex) ? 'true' : 'false';
    });
    const activeEl = list.querySelector('.combo-option[data-active="true"]');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
  }

  list.addEventListener('click', (e) => {
    const opt = e.target.closest('.combo-option');
    if (opt && opt.dataset.value !== undefined) {
      selectOption(opt.dataset.value);
      trigger.focus();
    }
  });

  document.addEventListener('click', (e) => {
    if (!wrap.contains(e.target)) close();
  });

  // Programmatic value changes (reset, Excel load) set select.value directly —
  // dispatch 'combo:sync' on the select afterwards to refresh the custom UI.
  select.addEventListener('combo:sync', () => {
    options.forEach(o => o.selected = (o.value === select.value));
    renderTrigger();
  });

  renderTrigger();
}

/* ─── Liquid highlight: a goo-filtered blob that morphs between targets ── */
function initLiquidTrack(container) {
  if (container.dataset.liquidReady) return;
  container.dataset.liquidReady = '1';
  container.classList.add('liquid-track');

  const itemSelector = container.dataset.liquidItem
    || ':scope > a, :scope > button, :scope > .liquid-item';
  const activeSelector = container.dataset.liquidActive || null;

  const layer = document.createElement('div');
  layer.className = 'liquid-layer';
  const main = document.createElement('div');
  main.className = 'liquid-blob';
  const trail = document.createElement('div');
  trail.className = 'liquid-blob liquid-blob-trail';
  layer.append(trail, main);
  container.prepend(layer);

  let current = null;

  function place(blob, rect, opts = {}) {
    if (opts.instant) blob.style.transition = 'none';
    blob.style.left = rect.x + 'px';
    blob.style.top  = rect.y + 'px';
    blob.style.width  = rect.w + 'px';
    blob.style.height = rect.h + 'px';
    if (opts.opacity != null) blob.style.opacity = opts.opacity;
    if (opts.instant) {
      void blob.offsetWidth;
      blob.style.transition = '';
    }
  }

  function rectFor(el) {
    const cr = container.getBoundingClientRect();
    const er = el.getBoundingClientRect();
    return { x: er.left - cr.left, y: er.top - cr.top, w: er.width, h: er.height };
  }

  function entryDrop(prev, next) {
    // A thin slice on the entry edge, spanning the full perpendicular extent —
    // so the fill animation reads as water sweeping across, not a circle bloating out.
    const dx = (next.x + next.w / 2) - (prev.x + prev.w / 2);
    const dy = (next.y + next.h / 2) - (prev.y + prev.h / 2);
    const slice = 12;
    if (Math.abs(dx) >= Math.abs(dy)) {
      return {
        x: dx > 0 ? next.x : next.x + next.w - slice,
        y: next.y,
        w: slice,
        h: next.h,
      };
    } else {
      return {
        x: next.x,
        y: dy > 0 ? next.y : next.y + next.h - slice,
        w: next.w,
        h: slice,
      };
    }
  }

  function moveTo(el) {
    if (!el) {
      main.style.opacity = '0';
      trail.style.opacity = '0';
      current = null;
      return;
    }
    if (el === current) return;
    const next = rectFor(el);

    if (current) {
      const prev = rectFor(current);
      // Trail: snap onto the OLD target at full size, then drain toward the entry drop
      const drop = entryDrop(prev, next);
      place(trail, prev, { instant: true, opacity: 0.9 });
      // Main: snap onto the entry edge of the NEW target as a small drop
      place(main, drop, { instant: true, opacity: 1 });
      // Next frame: trail flows toward the entry slice and fades; main expands to fill
      requestAnimationFrame(() => {
        place(trail, drop, { opacity: 0 });
        place(main, next, { opacity: 1 });
      });
    } else {
      // First hover after entering the track: just fill from a tiny center drop
      place(main, { x: next.x + next.w / 2 - 6, y: next.y + next.h / 2 - 6, w: 12, h: 12 },
            { instant: true, opacity: 1 });
      requestAnimationFrame(() => place(main, next, { opacity: 1 }));
    }
    current = el;
  }

  function activeEl() {
    return activeSelector ? container.querySelector(activeSelector) : null;
  }

  const staticMode = container.dataset.liquidStatic === 'true';

  if (!staticMode) {
    container.addEventListener('pointerover', e => {
      const el = e.target.closest(itemSelector);
      if (el && container.contains(el)) moveTo(el);
    });
    container.addEventListener('pointerleave', () => {
      moveTo(activeEl());
    });
  } else if (activeSelector) {
    // Static mode: blob follows whichever item carries the active class.
    // Watch for class changes on the items so click-driven tab swaps animate the blob.
    const observer = new MutationObserver(() => {
      const next = activeEl();
      if (next && next !== current) moveTo(next);
    });
    container.querySelectorAll(itemSelector).forEach(item => {
      observer.observe(item, { attributes: true, attributeFilter: ['class'] });
    });
  }

  // Initial placement: settle silently on the active element if one exists
  const start = activeEl();
  if (start) {
    requestAnimationFrame(() => {
      const r = rectFor(start);
      place(main, { x: r.x + r.w / 2, y: r.y + r.h / 2, w: 0, h: 0 },
            { instant: true, opacity: 0 });
      requestAnimationFrame(() => {
        place(main, r, { opacity: 1 });
        current = start;
      });
    });
  }

  // Reposition on resize / font load so the blob stays glued to its target
  const reflow = () => {
    const el = current;
    if (!el) return;
    current = null;
    moveTo(el);
  };
  window.addEventListener('resize', reflow);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(reflow);
}

function initInfoTabs(root) {
  const tabs   = root.querySelectorAll('.info-tab');
  const panels = root.querySelectorAll('.info-panel');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.target;
      tabs.forEach(t => t.classList.toggle('active', t === tab));
      panels.forEach(p => {
        const match = p.dataset.panel === target;
        // Re-trigger the keyframe animation when switching in
        if (match) { p.classList.remove('active'); void p.offsetWidth; }
        p.classList.toggle('active', match);
      });
    });
  });
}

function initRevealOnScroll() {
  const howCards = document.querySelectorAll('.how-card');
  howCards.forEach((el, i) => el.style.setProperty('--card-i', i));
  // Everything else swims in via .reveal-pending → .reveal-in (CSS motion pack).
  const others = document.querySelectorAll(
    '.lineup-event, .relay-card, .total-cell, .scenarios-section, .check-event');
  const targets = [...howCards, ...others];
  if (!targets.length) return;

  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finish = el => { el.classList.add('revealed', 'reveal-in'); el.classList.remove('reveal-pending'); };

  // Reduced motion or no IntersectionObserver → reveal everything immediately.
  if (reduce || !('IntersectionObserver' in window)) {
    targets.forEach(finish);
    return;
  }
  others.forEach(el => el.classList.add('reveal-pending'));

  // Items revealed in the same observer tick cascade 70ms apart, so a fresh
  // viewport-full of cards reads as a wave instead of a simultaneous blink.
  let batchN = 0, batchTimer = null;
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.style.setProperty('--reveal-delay', Math.min(batchN * 45, 270) + 'ms');
      batchN += 1;
      finish(entry.target);
      io.unobserve(entry.target);
    });
    clearTimeout(batchTimer);
    batchTimer = setTimeout(() => { batchN = 0; }, 200);
  }, { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });
  targets.forEach(el => io.observe(el));
}

/* ─── Motion pack: click ripples, hero cursor wake, win-water gauge ────── */

const _reducedMotion = () =>
  window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Results page: fill the headline panel with "water" up to the win %, with
// two wave layers drifting along the surface.
function initWinGauge() {
  const headline = document.querySelector('.lineup-headline');
  if (!headline || headline.querySelector('.win-water')) return;
  const pctEl = headline.querySelector('.headline-pct');
  const wp = parseFloat(pctEl && (pctEl.getAttribute('data-countup') || pctEl.textContent));
  if (isNaN(wp)) return;

  const wavePath = 'M0 16 Q 75 6 150 16 T 300 16 T 450 16 T 600 16 V 30 H 0 Z';
  const svg = `<svg viewBox="0 0 600 30" preserveAspectRatio="none" aria-hidden="true"><path d="${wavePath}"/></svg>`;
  const water = document.createElement('div');
  water.className = 'win-water';
  water.setAttribute('aria-hidden', 'true');
  water.innerHTML = `<div class="win-water-fill">`
                  + `<div class="win-wave-row">${svg}${svg}</div>`
                  + `<div class="win-wave-row win-wave-row2">${svg}${svg}</div>`
                  + `</div>`;
  headline.appendChild(water);

  // Clamp so a tiny win% still shows a sliver of water and a huge one keeps
  // the waves inside the panel. Double-rAF so the height transition runs.
  const level = Math.max(6, Math.min(90, wp));
  const fill = water.querySelector('.win-water-fill');
  if (_reducedMotion()) { fill.style.height = level + '%'; return; }

  // Bubbles drifting up through the water — in their own clipped layer so
  // they vanish at the surface without clipping the waves above it.
  let bb = '<div class="win-bubble-layer">';
  for (let i = 0; i < 7; i++) {
    const s = 4 + (i % 3) * 2;
    bb += `<span class="gauge-bubble" style="left:${8 + i * 13}%; width:${s}px; height:${s}px;`
        + ` animation-duration:${3.5 + (i % 4)}s; animation-delay:${-(i * 1.3)}s"></span>`;
  }
  bb += '</div>';
  fill.insertAdjacentHTML('beforeend', bb);

  // Strong lineups (≥75%) get a droplet burst off the waterline + a bounce
  // from the headline number once the pool finishes filling.
  if (wp >= 75) {
    fill.addEventListener('transitionend', function burst(e) {
      if (e.propertyName !== 'height') return;
      fill.removeEventListener('transitionend', burst);
      let drops = '';
      for (let i = 0; i < 12; i++) {
        const dx = ((i - 5.5) * 9 + ((i % 3) - 1) * 4).toFixed(0);
        const dy = -(26 + (i * 7) % 38);
        drops += `<span class="gauge-drop" style="left:${12 + i * 6.8}%; bottom:${level}%;`
               + ` --dx:${dx}px; --dy:${dy}px; animation-delay:${(i % 4) * 0.05}s"></span>`;
      }
      water.insertAdjacentHTML('beforeend', drops);
      pctEl.classList.add('celebrate');
      setTimeout(() => water.querySelectorAll('.gauge-drop').forEach(d => d.remove()), 1400);
    });
  }

  requestAnimationFrame(() => requestAnimationFrame(() => {
    fill.style.height = level + '%';
  }));
}

// Tiny freestyle swimmer glyph (side view, facing right): filled head, torso,
// and articulated limbs. The two arms share one shoulder joint and windmill
// a full 360° half a cycle apart (real freestyle timing); the legs flutter-
// kick around the hip. All driven by the sw-arm / sw-leg CSS animations.
// Inherits currentColor; flipping the host element mirrors the whole stroke.
const SWIMMER_SVG =
  '<svg viewBox="0 0 32 16" fill="none" stroke="currentColor" stroke-width="2"'
  + ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
  + '<circle cx="22.5" cy="6" r="2.2" fill="currentColor" stroke="none"></circle>'
  + '<path d="M20.5 7.5 C 16 8.8, 12.5 9.3, 8.5 9.5"></path>'
  + '<path class="sw-arm" d="M20.5 7 L23.9 6.5 L27 8"></path>'
  + '<path class="sw-arm sw-arm2" d="M20.5 7 L23.9 6.5 L27 8"></path>'
  + '<path class="sw-leg" d="M8.5 9.5 L4.3 8.4"></path>'
  + '<path class="sw-leg sw-leg2" d="M8.5 9.5 L4.3 10.8"></path>'
  + '</svg>';

// Site-wide ambience: neon bubble rings rising behind the content. The field
// is anchored to the PAGE (absolute, full document height), not the viewport,
// so scrolling down sweeps the bubbles up the screen and scrolling up sinks
// them — no scroll listener needed. Bubbles live ONLY in the side gutters
// flanking the centered content column, so they never pass behind text; on
// windows too narrow for gutters they hide. Spread is a deterministic walk.
function initBubbleField() {
  if (_reducedMotion() || document.querySelector('.bubble-field')) return;
  const field = document.createElement('div');
  field.className = 'bubble-field';
  field.setAttribute('aria-hidden', 'true');
  const n = Math.min(36, Math.max(12, Math.round(document.documentElement.scrollHeight / 300)));
  let html = '';
  for (let i = 0; i < n; i++) {
    const top  = ((i * 37.3) % 100).toFixed(1);
    const size = (6 + ((i * 3.3) % 10)).toFixed(1);
    const dur  = (16 + ((i * 5.3) % 18)).toFixed(1);
    const delay = -(((i * 3.1) % 16)).toFixed(1);
    const wob  = ((i % 2 ? 1 : -1) * (6 + (i * 5) % 10)).toFixed(0);
    html += `<span class="bubble" style="top:${top}%; width:${size}px; height:${size}px;`
          + ` animation-duration:${dur}s; animation-delay:${delay}s; --wob:${wob}px"></span>`;
  }
  field.innerHTML = html;
  document.body.appendChild(field);

  const fit = () => {
    field.style.height = document.documentElement.scrollHeight + 'px';
    // Confine bubbles to the gutters beside the content column.
    const vw = document.documentElement.clientWidth;
    const page = document.querySelector('main.page');
    const rect = page ? page.getBoundingClientRect() : null;
    const gutL = rect ? Math.max(0, rect.left) : 0;
    const gutR = rect ? Math.max(0, vw - rect.right) : 0;
    field.querySelectorAll('.bubble').forEach((el, i) => {
      const left = i % 2 === 0;
      const g = left ? gutL : gutR;
      if (g < 70) { el.style.display = 'none'; return; }  // no gutter — no bubble
      el.style.display = '';
      const span = Math.max(1, g - 64);   // margins: 14px outer, ~50px inner (incl. wobble)
      const x = 14 + ((i * 23.7) % span);
      el.style.left = (left ? x : vw - x - 16) + 'px';
    });
  };
  fit();
  window.addEventListener('resize', fit);
  window.addEventListener('load', fit);   // re-measure once images/fonts settle
}

// Scroll progress as a pool lane rope along the nav's bottom edge, with a
// swimmer dot leading the fill. Only on the Build page (the stepper), where
// knowing how far along you are actually helps.
function initScrollLane() {
  if (!document.querySelector('.stepper')) return;
  if (document.querySelector('.scroll-lane') || _reducedMotion()) return;
  const bar = document.createElement('div');
  bar.className = 'scroll-lane';
  bar.setAttribute('aria-hidden', 'true');
  bar.innerHTML = '<div class="scroll-lane-rope"></div>'
                + '<span class="scroll-lane-swimmer">' + SWIMMER_SVG + '</span>';
  // Ride the sticky nav's bottom edge so the dot never clips offscreen.
  (document.querySelector('nav.topnav') || document.body).appendChild(bar);
  let ticking = false;
  const update = () => {
    ticking = false;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    if (max < 60) { bar.style.display = 'none'; return; }
    bar.style.display = '';
    const p = Math.min(1, Math.max(0, window.scrollY / max));
    bar.style.setProperty('--p', (p * 100).toFixed(2) + '%');
  };
  const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  update();
}

// Count up the totals row and scenario win-percent chips on the results page.
function initLineupTickers() {
  if (_reducedMotion()) return;
  const tick = (el, target, decimals, suffix) => {
    const dur = 650;
    const ease = t => 1 - Math.pow(1 - t, 3);
    let start = null;
    function frame(ts) {
      if (start === null) start = ts;
      const p = Math.min(1, (ts - start) / dur);
      el.textContent = (target * ease(p)).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  };
  document.querySelectorAll('.total-cell strong').forEach(el => {
    const m = el.textContent.trim().match(/^(\d+(?:\.\d+)?)$/);
    if (!m) return;   // skips the "219 – 153" median cell
    tick(el, parseFloat(m[1]), (m[1].split('.')[1] || '').length, '');
  });
  document.querySelectorAll('.scenario-winpct').forEach(el => {
    const m = el.textContent.trim().match(/^(\d+(?:\.\d+)?)%$/);
    if (!m) return;
    tick(el, parseFloat(m[1]), (m[1].split('.')[1] || '').length, '%');
  });
}

/* ─── Lineup persistence (auto-save the latest optimize to localStorage) ─ */
const LineupStorage = {
  KEY: 'laneLab:lineup',
  save(data) {
    try { localStorage.setItem(this.KEY, JSON.stringify(data)); }
    catch (e) { console.warn('LineupStorage.save failed:', e); }
  },
  load() {
    try { return JSON.parse(localStorage.getItem(this.KEY) || 'null'); }
    catch { return null; }
  },
  clear() {
    try { localStorage.removeItem(this.KEY); } catch {}
  },
};

/* ─── Lineup view: opp-mode toggle (Predicted v5 / Last Week) ──────────── */
function _winClass(wp) { return wp >= 75 ? 'win100' : wp >= 55 ? 'win75' : wp >= 35 ? 'win50' : 'win25'; }
function _pctClass(wp) { return wp >= 75 ? 'pct-easy' : wp >= 55 ? 'pct-moderate' : wp >= 35 ? 'pct-hard' : 'pct-extreme'; }

// Switch every opp-dependent number on the lineup page to the chosen matchup
// ("predicted" or "lastweek"): headline win%, median, and each event's win%/pts.
// Lane swapping is handled separately. Elements without a value for the mode
// (e.g. an event the opp didn't swim last week) keep their current value.
function _applyOppMode(mode) {
  const suf = (mode === 'lastweek') ? 'Lastweek' : 'Predicted';
  const hp = document.getElementById('headlinePct');
  if (hp) {
    const v = hp.dataset['wp' + suf];
    if (v != null && v !== '') {
      const wp = parseFloat(v);
      hp.textContent = wp.toFixed(1) + '%';
      hp.className = 'headline-pct ' + _pctClass(wp);
    }
  }
  const mc = document.getElementById('medianCell');
  if (mc) {
    const opp = mc.dataset['opp' + suf];
    if (opp != null && opp !== '') mc.textContent = mc.dataset.our + ' – ' + opp;
  }
  document.querySelectorAll('.event-winpct').forEach(el => {
    const v = el.dataset['wp' + suf];
    if (v != null && v !== '') {
      const wp = parseFloat(v);
      el.textContent = wp.toFixed(0) + '% win';
      el.className = 'event-winpct ' + _winClass(wp);
    }
  });
  document.querySelectorAll('.event-pts').forEach(el => {
    const v = el.dataset['pts' + suf];
    if (v != null && v !== '') el.textContent = parseFloat(v).toFixed(1) + ' pts';
  });
}

// Results-page inline picker: the coach chooses who swims a "no real time" lane.
// Persists to the server so the lineup + Excel export reflect it. Not scored (the
// swimmer has no seed time) — it's a meet-day roster choice.
async function onLanePick(sel) {
  const event   = sel.dataset.event;
  const lane    = parseInt(sel.dataset.lane, 10);
  const swimmer = sel.value || null;
  sel.classList.toggle('has-pick', !!swimmer);
  const row = sel.closest('.lane');
  if (row) row.classList.toggle('lane-picked', !!swimmer);
  try {
    const r = await fetch('/api/set_lane_pick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, lane, swimmer }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      sel.value = '';                      // revert the rejected choice
      sel.classList.remove('has-pick');
      if (row) row.classList.remove('lane-picked');
      if (typeof _showPrefsStatus === 'function') _showPrefsStatus(d.error || 'Could not add that swimmer', 'err');
    }
  } catch (e) { /* best-effort; the visual choice still holds for this session */ }
}

function initLineupView() {
  // If the server didn't render and we have a saved lineup, hydrate.
  const root = document.getElementById('lineupRoot');
  if (root && root.dataset.serverRendered === 'false' && !window.LINEUP_DATA) {
    const stored = LineupStorage.load();
    if (stored) {
      window.LINEUP_DATA = stored;
      // Soft-reload so the server renders the empty page (no _cache) but the
      // template still has nothing to render — instead show a "restored" message.
      // For now: just navigate to /setup. (Full client-side render is a bigger
      // build; the empty CTA stays so the user re-runs.)
    }
  }

  // Server-rendered path: wire up the Predicted ↔ Last Week toggle.
  const toggles = document.querySelectorAll('.opp-mode');
  if (!toggles.length) return;
  toggles.forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.disabled) return;
      const mode = btn.dataset.mode;
      toggles.forEach(b => b.classList.toggle('active', b === btn));
      document.querySelectorAll('.lane-grid').forEach(grid => {
        grid.classList.toggle('lane-grid--hidden', grid.dataset.mode !== mode);
      });
      _applyOppMode(mode);   // swap the scores/win%/per-event too, not just names
    });
  });

  // Auto-save the current server-rendered payload so refresh later restores it.
  // (Re-saves every load, which keeps the cache fresh.)
  if (window.LINEUP_DATA && root && root.dataset.serverRendered === 'true') {
    LineupStorage.save(window.LINEUP_DATA);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Build comboboxes in chunks across frames so a page with 120+ selects
  // (the Check editor) doesn't block first paint.
  const _combos = Array.from(document.querySelectorAll('select[data-combo]'));
  (function _buildCombos() {
    _combos.splice(0, 24).forEach(initCombobox);
    if (_combos.length) requestAnimationFrame(_buildCombos);
  })();
  document.querySelectorAll('[data-liquid]').forEach(initLiquidTrack);
  document.querySelectorAll('.info-tabs').forEach(initInfoTabs);
  initRevealOnScroll();
  initLineupView();
  updateLadderRec();
  initSetupPrefs();
  initCountUps();
  initScenarioPills();
  initCheckPage();
  initWinGauge();
  initLineupTickers();
  initBubbleField();
  initScrollLane();
  // Disarm "Confirm clear" the moment the pointer leaves the button.
  const _clrBtn = document.getElementById('clearLineupBtn');
  if (_clrBtn) _clrBtn.addEventListener('mouseleave', () => { if (_clearArmed) _resetClearBtn(); });
});

/* ─── Results: export to Excel (backend endpoint stubbed) ─────────────── */
function exportLineupXlsx() {
  // Trigger the .xlsx download. Backend returns 409 JSON if no lineup is cached, but
  // this button only renders on the lineup page, so a lineup is present by construction.
  window.location = '/api/export_lineup.xlsx';
}

/* ─── Clear lineup: inline two-step confirm (no native dialog) ───────────
   First click "arms" the button (turns it into a danger "Confirm clear" that
   auto-reverts after 3s); a second click within that window performs the wipe.
   Errors show inline on the button, never an alert(). */
let _clearArmed = false, _clearTimer = null;
function clearLineupClick() {
  const btn = document.getElementById('clearLineupBtn');
  if (!btn) return;
  if (!_clearArmed) {
    _clearArmed = true;
    btn.classList.add('armed');
    btn.textContent = 'Confirm clear';
    _clearTimer = setTimeout(_resetClearBtn, 3000);
    return;
  }
  clearTimeout(_clearTimer);
  _doClearLineup(btn);
}
function _resetClearBtn() {
  const btn = document.getElementById('clearLineupBtn');
  if (!btn) return;
  clearTimeout(_clearTimer);
  _clearArmed = false;
  btn.disabled = false;
  btn.className = 'clear-lineup-btn';
  btn.textContent = 'Clear lineup';
}
async function _doClearLineup(btn) {
  _clearArmed = false;
  btn.disabled = true;
  btn.className = 'clear-lineup-btn';
  btn.textContent = 'Clearing…';
  try {
    const res = await fetch('/api/clear_cache', { method: 'POST' });
    const data = await res.json();
    if (data.ok) {
      btn.classList.add('done');
      btn.textContent = 'Cleared ✓';
      setTimeout(() => { window.location.href = '/setup'; }, 600);
    } else {
      throw new Error(data.error || 'unknown error');
    }
  } catch (e) {
    btn.disabled = false;
    btn.classList.add('failed');
    btn.textContent = 'Failed — retry';
    setTimeout(_resetClearBtn, 2000);
  }
}

/* ─── Check page: editable what-if lineup ────────────────────────────────
   Real client-side bits: edit tracking, reset, and conflict checks
   (duplicate-in-event, per-swimmer entry counts). Scoring the edited lineup
   and ranked swap suggestions need a backend pass (hinted in the UI). */
function initCheckPage() {
  const grid = document.getElementById('checkGrid');
  if (!grid) return;
  // Snapshot the optimal per-event win% chips so Reset can restore them.
  grid.querySelectorAll('.check-event .event-winpct').forEach(chip => {
    chip.dataset.origText  = chip.textContent;
    chip.dataset.origClass = chip.className;
  });
  grid.querySelectorAll('.swap-select').forEach(sel => {
    sel.addEventListener('change', () => {
      sel.classList.toggle('changed', sel.value !== sel.dataset.orig);
      markYoursDirty();
      runChecks();
    });
  });
  filterCheckGrid();
  runChecks();
}

// Show only the selected age group / team. Hidden events stay in the DOM, so
// scoring stays whole-meet. "all" shows everything.
function filterCheckGrid() {
  const age = (document.getElementById('ageFilter')    || {}).value || 'all';
  const gen = (document.getElementById('genderFilter') || {}).value || 'all';
  // Hide the whole non-matching team column (keeps the layout tidy).
  document.querySelectorAll('.events-col').forEach(col => {
    col.style.display = (gen === 'all' || col.dataset.gender === gen) ? '' : 'none';
  });
  // One team selected → let the remaining column use the full width.
  const grid = document.getElementById('checkGrid');
  if (grid) grid.classList.toggle('single-col', gen !== 'all');
  // Within the visible columns, hide events outside the chosen age group.
  document.querySelectorAll('.check-event').forEach(card => {
    card.style.display = (age === 'all' || card.dataset.age === age) ? '' : 'none';
  });
  updateCompareScope();
}

function scopeLabel() {
  const age = (document.getElementById('ageFilter')    || {}).value || 'all';
  const gen = (document.getElementById('genderFilter') || {}).value || 'all';
  const parts = [];
  if (gen !== 'all') parts.push(gen);
  if (age !== 'all') parts.push(age);
  return parts.length ? '· ' + parts.join(' ') : '· whole meet';
}

// Recompute the compare bar from the VISIBLE event cards only: optimal points
// (data-optpts, static) vs your scored points (data-yourpts, set after a Check).
function updateCompareScope() {
  const scopeEl = document.getElementById('cmpScope');
  if (scopeEl) scopeEl.textContent = scopeLabel();
  // offsetParent is null when the card OR its (gender) column is display:none,
  // so this counts only events actually visible under the age + team filters.
  const cards = Array.from(document.querySelectorAll('.check-event'))
                     .filter(c => c.offsetParent !== null);
  let optSum = 0, yourSum = 0, scored = cards.length > 0;
  cards.forEach(c => {
    optSum += parseFloat(c.dataset.optpts || '0');
    if (c.dataset.yourpts !== undefined) yourSum += parseFloat(c.dataset.yourpts);
    else scored = false;
  });
  const optEl = document.getElementById('optimalPts');
  if (optEl) optEl.textContent = optSum.toFixed(1) + ' pts';

  const yEl = document.getElementById('yoursPts');
  const dEl = document.getElementById('yoursDelta');
  const changed = document.querySelectorAll('.swap-select.changed').length;
  if (scored) {
    if (yEl) yEl.textContent = yourSum.toFixed(1) + ' pts';
    if (dEl) {
      const dp = yourSum - optSum;
      dEl.textContent = (dp >= 0 ? '+' : '') + dp.toFixed(1) + ' pts vs optimal';
      dEl.className = 'cmp-delta ' + (Math.abs(dp) < 0.05 ? '' : (dp > 0 ? 'better' : 'worse'));
    }
  } else {
    if (yEl) yEl.textContent = changed > 0 ? 'edited' : '— pts';
    if (dEl) {
      dEl.textContent = changed > 0 ? (changed + ' change' + (changed > 1 ? 's' : '') + ' — click “Check lineup”') : '';
      dEl.className = 'cmp-delta ' + (changed > 0 ? 'dirty' : '');
    }
  }
}

// An edit invalidates the last score: drop cached per-event "yours" points and
// the whole-meet win line, then refresh the compare bar.
function markYoursDirty() {
  document.querySelectorAll('.check-event').forEach(c => { delete c.dataset.yourpts; });
  const meet = document.getElementById('meetWin');
  if (meet) meet.textContent = '';
  // Last score is stale until they re-check, so hide the promote button.
  const pBtn = document.getElementById('promoteBtn');
  if (pBtn) pBtn.style.display = 'none';
  updateCompareScope();
}

// Live conflict checks (no backend): duplicate swimmer within one event, and any
// swimmer entered in more than 2 individual events (the NVSL per-meet cap).
function runChecks() {
  const grid = document.getElementById('checkGrid');
  if (!grid) return;
  const selects = Array.from(grid.querySelectorAll('.swap-select'));
  selects.forEach(s => s.classList.remove('invalid'));

  const issues = [];
  const byEvent = {};
  selects.forEach(s => { (byEvent[s.dataset.event] = byEvent[s.dataset.event] || []).push(s); });
  Object.entries(byEvent).forEach(([ev, sels]) => {
    const seen = {};
    sels.forEach(s => { if (s.value) (seen[s.value] = seen[s.value] || []).push(s); });
    Object.entries(seen).forEach(([name, arr]) => {
      if (arr.length > 1) {
        arr.forEach(s => s.classList.add('invalid'));
        issues.push({ type: 'error', msg: `${name} is entered twice in the same event (${ev}).` });
      }
    });
  });

  // 2-event cap: a swimmer may enter at most 2 individual events per meet (NVSL
  // MAX_EVENTS). Count DISTINCT events per swimmer — a within-event duplicate is
  // flagged above and must not inflate this — and flag anyone over the cap.
  const MAX_EVENTS = 2;
  const eventsBySwimmer = {};
  Object.entries(byEvent).forEach(([ev, sels]) => {
    new Set(sels.map(s => s.value).filter(Boolean)).forEach(name => {
      (eventsBySwimmer[name] = eventsBySwimmer[name] || new Set()).add(ev);
    });
  });
  Object.entries(eventsBySwimmer)
    .filter(([, evs]) => evs.size > MAX_EVENTS)
    .forEach(([name, evs]) => {
      selects.filter(s => s.value === name).forEach(s => s.classList.add('invalid'));
      issues.push({ type: 'error',
        msg: `${name} is entered in ${evs.size} events — a swimmer can swim at most ${MAX_EVENTS} individual events.` });
    });

  const box = document.getElementById('checkIssues');
  if (!box) return;
  if (!issues.length) {
    box.innerHTML = '<div class="check-ok">✓ No conflicts found (no double-bookings or duplicate entries).</div>';
  } else {
    box.innerHTML = issues.map(i =>
      `<div class="check-issue check-${i.type}">${i.type === 'error' ? '✕' : '⚠'} ${i.msg}</div>`).join('');
  }
}

// Score the edited lineup via the backend (reuses the optimizer's sim). Stores
// each event's "yours" points on its card so the compare bar can sum just the
// visible (filtered) scope, and shows the whole-meet win % separately.
async function runCheckScore() {
  runChecks();
  const grid = document.getElementById('checkGrid');
  const yEl  = document.getElementById('yoursPts');
  const btn  = document.getElementById('checkBtn');
  if (!grid) return;

  const lineup = {};
  grid.querySelectorAll('.swap-select').forEach(s => {
    (lineup[s.dataset.event] = lineup[s.dataset.event] || []).push(s.value);
  });

  if (btn) btn.disabled = true;
  if (yEl) yEl.textContent = 'scoring…';

  try {
    const r = await fetch('/api/score_lineup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lineup }),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);

    // Per-event: cache "yours" points on the card + refresh its win% chip.
    (d.events || []).forEach(ev => {
      const sel  = grid.querySelector('.swap-select[data-event="' + ev.event + '"]');
      const card = sel && sel.closest('.check-event');
      if (!card) return;
      // Use the CRN-precise delta vs optimal (noise-cancelled) rather than the raw
      // MC points, so the compare bar reads a trustworthy difference.
      if (ev.delta != null) {
        card.dataset.yourpts = (parseFloat(card.dataset.optpts || '0') + ev.delta).toFixed(2);
      } else {
        card.dataset.yourpts = (ev.mc_pts != null ? ev.mc_pts : 0);
      }
      const chip = card.querySelector('.event-winpct');
      if (chip && ev.win_pct != null) {
        const w = ev.win_pct;
        chip.textContent = w.toFixed(0) + '% win';
        chip.className = 'event-winpct ' + (w >= 75 ? 'win100' : w >= 55 ? 'win75' : w >= 35 ? 'win50' : 'win25');
      }
    });

    // Whole-meet win line (independent of the age/team scope).
    const meet = document.getElementById('meetWin');
    if (meet) {
      const base = window.CHECK_BASE || {};
      let t = 'Whole-meet win: ';
      if (base.win != null) t += base.win.toFixed(0) + '% → ';
      t += d.win_pct.toFixed(0) + '%';
      if (base.win != null) {
        const dw = d.win_pct - base.win;
        t += '  (' + (dw >= 0 ? '+' : '') + dw.toFixed(0) + '%)';
      }
      meet.textContent = t;
    }

    updateCompareScope();

    // Offer "Make this the optimal" when the lineup is valid, changed, and not
    // worse than optimal on the whole-meet win %. The server does the final,
    // authoritative robust re-check before actually promoting.
    const pBtn = document.getElementById('promoteBtn');
    if (pBtn) {
      const base = window.CHECK_BASE || {};
      const noConflicts = document.querySelectorAll('.swap-select.invalid').length === 0;
      const changed     = document.querySelectorAll('.swap-select.changed').length > 0;
      const notWorse    = (base.win == null) || (d.win_pct >= base.win - 0.5);
      pBtn.style.display = (noConflicts && changed && notWorse) ? '' : 'none';
    }

    // Eligibility warnings (swimmers with no time for an event's stroke).
    if (d.warnings && d.warnings.length) {
      const box = document.getElementById('checkIssues');
      if (box) d.warnings.forEach(w => {
        const div = document.createElement('div');
        div.className = 'check-issue check-warn';
        div.textContent = '⚠ ' + w.swimmers.join(', ') + ' — no time for ' + w.event + ', not counted.';
        box.appendChild(div);
      });
    }
  } catch (e) {
    if (yEl) yEl.textContent = '—';
    const dEl = document.getElementById('yoursDelta');
    if (dEl) { dEl.textContent = e.message; dEl.className = 'cmp-delta worse'; }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// Promote the edited lineup to be the new "optimal". The server validates it and
// re-checks it against the opponent-uncertainty set the optimizer hedged over; if
// it holds up it becomes the saved lineup and we reload so the whole page reflects
// it. If the optimizer was hedging on purpose, the server explains why it held off.
async function promoteLineup() {
  const grid = document.getElementById('checkGrid');
  const btn  = document.getElementById('promoteBtn');
  const box  = document.getElementById('checkIssues');
  if (!grid) return;
  const lineup = {};
  grid.querySelectorAll('.swap-select').forEach(s => {
    (lineup[s.dataset.event] = lineup[s.dataset.event] || []).push(s.value);
  });
  if (btn) { btn.disabled = true; btn.textContent = 'Checking…'; }
  try {
    const r = await fetch('/api/promote_lineup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lineup }),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    if (d.promoted) {
      location.reload();   // new optimal saved — re-render the whole page from it
      return;
    }
    if (box) box.innerHTML =
      `<div class="check-issue check-warn">⚠ ${d.reason || 'Not promoted.'}</div>` + box.innerHTML;
  } catch (e) {
    if (box) box.innerHTML =
      `<div class="check-issue check-error">✕ ${e.message}</div>` + box.innerHTML;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Make this the optimal'; }
  }
}

function resetCheck() {
  const pBtn = document.getElementById('promoteBtn');
  if (pBtn) pBtn.style.display = 'none';
  document.querySelectorAll('.swap-select').forEach(sel => {
    sel.value = sel.dataset.orig;
    sel.classList.remove('changed', 'invalid');
    sel.dispatchEvent(new Event('combo:sync'));
  });
  document.querySelectorAll('.check-event').forEach(c => { delete c.dataset.yourpts; });
  // Restore the optimal per-event win% chips.
  document.querySelectorAll('.check-event .event-winpct').forEach(chip => {
    if (chip.dataset.origClass !== undefined) {
      chip.textContent = chip.dataset.origText;
      chip.className   = chip.dataset.origClass;
    }
  });
  const meet = document.getElementById('meetWin');
  if (meet) meet.textContent = '';
  updateCompareScope();
  runChecks();
}

// Upload a coach's own lineup (Excel) to load into the editor. The backend
// (/api/parse_lineup_xlsx) parses the sheet and fuzzy-matches names to the
// roster; we then select each matched swimmer in the right event's dropdown.
async function uploadLineupXlsx() {
  const input = document.getElementById('lineupXlsxFile');
  const hint  = document.getElementById('lineupXlsxHint');
  const show  = (txt) => { if (hint) { hint.textContent = txt; hint.style.display = 'inline-flex'; } };
  if (!input || !input.files.length) { show('Pick an Excel file first.'); return; }
  const grid = document.getElementById('checkGrid');
  if (!grid) { show('No editable lineup on this page — run the optimizer first.'); return; }
  show('Parsing…');
  // Send the editor's own event labels so the server matches to the right dropdowns.
  const evLabels = [...new Set([...grid.querySelectorAll('.swap-select')].map(s => s.dataset.event))];
  const fd = new FormData();
  fd.append('file', input.files[0]);
  fd.append('events', JSON.stringify(evLabels));
  try {
    const r = await fetch('/api/parse_lineup_xlsx', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    // Backend returns canonical {event: [roster names]}, already fuzzy-matched.
    let set = 0; const missed = [];
    Object.entries(d.lineup || {}).forEach(([ev, names]) => {
      const selects = grid.querySelectorAll('.swap-select[data-event="' + ev + '"]');
      names.forEach((nm, i) => {
        const sel = selects[i];
        if (!sel) { missed.push(nm); return; }
        const opt = Array.from(sel.options).find(o => o.value === nm);
        if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('combo:sync')); set++; } else { missed.push(nm); }
      });
    });
    const warn = (d.unmatched_events || []).length + (d.unmatched_names || []).length + missed.length;
    show('Loaded ' + set + ' entries from "' + input.files[0].name + '"'
         + (warn ? ' · ' + warn + ' not matched (unknown event / name not on roster)' : ''));
    if (typeof runCheckScore === 'function') runCheckScore();
  } catch (e) {
    show('Error: ' + e.message);
  }
}

// Scenario pill switcher (results page): clicking a pill swaps which scenario
// card is shown. The liquid-highlight (static mode) follows the .active pill
// automatically via its class MutationObserver.
function initScenarioPills() {
  const pills = document.querySelectorAll('.scenario-pill');
  if (!pills.length) return;
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      const idx = pill.dataset.scenario;
      pills.forEach(p => p.classList.toggle('active', p === pill));
      document.querySelectorAll('.scenario-card').forEach(card => {
        card.classList.toggle('scenario-card--hidden', card.dataset.scenario !== idx);
      });
    });
  });
}

// Count any [data-countup] element up from 0 to its target on load (results
// page headline win-prob). data-suffix appends a unit; decimals inferred from
// the target string. Respects reduced-motion.
function initCountUps() {
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('[data-countup]').forEach(el => {
    const raw = el.getAttribute('data-countup');
    const target = parseFloat(raw);
    if (isNaN(target)) return;
    const suffix   = el.getAttribute('data-suffix') || '';
    const decimals = (raw.split('.')[1] || '').length;
    if (reduce) { el.textContent = target.toFixed(decimals) + suffix; return; }
    const dur = 900;
    const ease = t => 1 - Math.pow(1 - t, 3);   // easeOutCubic
    let start = null;
    function frame(ts) {
      if (start === null) start = ts;
      const p = Math.min(1, (ts - start) / dur);
      el.textContent = (target * ease(p)).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(frame);
      else el.textContent = target.toFixed(decimals) + suffix;
    }
    requestAnimationFrame(frame);
  });
}


function getConfig() {
  // Availability checkbox semantic: checked = "here this week". So the absent
  // list is everyone whose box is UNCHECKED.
  const absent = Array.from(document.querySelectorAll('#rosterArea input.absent:not(:checked)'))
                      .map(c => c.value);
  const oppAbsent = Array.from(document.querySelectorAll('#oppRosterArea input.absent-opp:not(:checked)'))
                         .map(c => c.value);
  // Checkbox semantic: checked = "on team / include in imputation".
  // Excluded = swimmers whose box is UNCHECKED (= no longer on team).
  const yourExcludes = Array.from(document.querySelectorAll('#impYourArea input.imp-inc:not(:checked)'))
                            .map(c => c.value);
  // Opponent imputation panel was removed; opp_excludes is no longer sent so the
  // server keeps (and re-applies) whatever was previously saved for that team.
  const useImp = document.getElementById('useImputation')
                ? document.getElementById('useImputation').checked : true;
  const useFp  = document.getElementById('useOppFingerprint')
                ? document.getElementById('useOppFingerprint').checked : true;
  const swimupRule = document.getElementById('swimupOnlyIfScoring')
                ? document.getElementById('swimupOnlyIfScoring').checked : true;
  return {
    your_team: document.getElementById('yourTeam').value,
    opp_team:  document.getElementById('oppTeam').value,
    year:      parseInt(document.getElementById('year').value),
    week:      parseInt(document.getElementById('week').value),
    use_opp_fingerprint: useFp,
    absent:    absent,
    opp_absent: oppAbsent,
    use_imputation: useImp,
    swimup_only_if_scoring: swimupRule,
    your_excludes:  yourExcludes,
    your_is_home:   (document.getElementById('homeAway') || {}).value !== 'away',
  };
}

// Reset the multi-step flow whenever inputs change.
function resetSetup() {
  ['step-upload', 'step-roster', 'step-impute', 'step-run'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.setAttribute('data-status', 'locked');
  });
  const setupStep = document.getElementById('step-setup');
  if (setupStep) setupStep.setAttribute('data-status', 'active');
  ['rosterArea', 'oppRosterArea', 'impYourArea', 'nameFlagArea'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '';
  });
  const nfBlock = document.getElementById('nameFlagBlock');
  if (nfBlock) nfBlock.style.display = 'none';
  ['teamsMsg', 'setupMsg', 'ladderMsg', 'runMsg'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.textContent = ''; el.className = 'status'; }
  });
  const setupBtn = document.getElementById('setupBtn');
  if (setupBtn) setupBtn.disabled = false;
  const runBtn = document.getElementById('runBtn');
  if (runBtn) runBtn.disabled = true;   // re-lock until the user advances to step 5
  updateLadderRec();
  refreshLadderInfo();   // team may have changed — refresh the saved-ladder notice
}

// The earlier the week, the less current-season data exists, so the value of a
// time-trial PDF rises. Phrase the recommendation accordingly (week 1 = caution).
function updateLadderRec() {
  const el = document.getElementById('ladderRec');
  if (!el) return;
  const week = parseInt((document.getElementById('week') || {}).value) || 0;
  if (week === 1) {
    el.className = 'ladder-rec rec-strong';
    el.textContent = '⚠ Highly recommended for Week 1 — there’s no current-season race data yet, so without a time-trial PDF the lineup leans entirely on last year’s results.';
  } else if (week === 2) {
    el.className = 'ladder-rec rec-mid';
    el.textContent = 'Recommended for Week 2 — only one week of current-season results exists so far.';
  } else if (week >= 3) {
    el.className = 'ladder-rec rec-soft';
    el.textContent = 'Encouraged — helps cover swimmers who haven’t raced every event yet.';
  } else {
    el.className = 'ladder-rec';
    el.textContent = '';
  }
}

// The uploaded ladder is saved per-team on the server and reused automatically
// every session — so when one is already on file, say so, and the user can skip
// the upload entirely. Populates #ladderSaved for the selected "your team".
async function refreshLadderInfo() {
  const el  = document.getElementById('ladderSaved');
  const btn = document.getElementById('ladderBtn');
  if (!el) return;
  const team = (document.getElementById('yourTeam') || {}).value || '';
  if (!team) { el.innerHTML = ''; el.className = ''; if (btn) btn.textContent = 'Upload →'; return; }
  try {
    const r = await fetch('/api/ladder_info?team=' + encodeURIComponent(team));
    const d = await r.json();
    if (d && d.exists && d.total) {
      let when = '';
      if (d.mtime) {
        try { when = ' · uploaded ' + new Date(d.mtime * 1000).toLocaleDateString(); } catch (e) {}
      }
      // Callout: a ladder IS on file (and its date), but nudge a fresh upload —
      // seed times change week to week, so last week's ladder goes stale.
      el.className = 'ladder-saved-callout';
      el.innerHTML = `<span class="ladder-saved-check">✓</span>`
                   + `<span><b>A saved ladder is on file${when}</b> — ${d.total} entries · ${d.swimmers} swimmers. `
                   + `It's applied automatically, but seed times change week to week — `
                   + `<b>uploading this week's ladder is recommended</b> for the most accurate lineup.</span>`;
      if (btn) btn.textContent = "Upload this week's ladder →";
    } else {
      el.className = 'note';
      el.innerHTML = 'No saved ladder for this team yet.';
      if (btn) btn.textContent = 'Upload →';
    }
  } catch (e) { el.innerHTML = ''; el.className = ''; }
}

// The imputation toggle is now saved per (team, week) on the server (restored in
// doSetup from use_imputation_pre, persisted on Run), so it sticks for that meet
// without bleeding across weeks. Nothing to restore here on first paint.
function initSetupPrefs() {
  refreshLadderInfo();
}

// Step 1 → 2: validate teams + week are chosen, then unlock the team-data step.
function proceedFromTeams() {
  const cfg = getConfig();
  const msg = document.getElementById('teamsMsg');
  if (!cfg.your_team || !cfg.opp_team) {
    if (msg) { msg.className = 'status error'; msg.textContent = 'Pick both teams.'; }
    return;
  }
  if (!cfg.week) {
    if (msg) { msg.className = 'status error'; msg.textContent = 'Pick a week.'; }
    return;
  }
  if (msg) { msg.textContent = ''; msg.className = 'status'; }
  refreshLadderInfo();   // show whether a saved ladder is already on file
  advanceStep('step-setup', 'step-upload');
}

// Smoothly scroll an element to the vertical center of the viewport over a set
// duration. Native scrollIntoView({behavior:'smooth'}) gives no speed control,
// so we animate scrollY ourselves. Respects reduced-motion.
function smoothScrollToEl(el, duration = 1100) {
  if (!el) return;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const rect   = el.getBoundingClientRect();
  const maxY   = document.documentElement.scrollHeight - window.innerHeight;
  const destY  = Math.max(0, Math.min(
                   window.scrollY + rect.top - (window.innerHeight - rect.height) / 2, maxY));
  const startY = window.scrollY;
  const dist   = destY - startY;
  if (reduce || Math.abs(dist) < 2) { window.scrollTo(0, destY); return; }
  const ease = t => 1 - Math.pow(1 - t, 3);   // easeOutCubic
  let start = null;
  function frame(ts) {
    if (start === null) start = ts;
    const p = Math.min(1, (ts - start) / duration);
    window.scrollTo(0, startY + dist * ease(p));
    if (p < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// Walk down the stepper: mark the current step done (its connector line fills
// to the next), unlock the next step, and slow-scroll it into view. Called by
// the "Next →" buttons on the review steps.
function advanceStep(currentId, nextId) {
  const cur = document.getElementById(currentId);
  const nxt = document.getElementById(nextId);
  if (cur) cur.setAttribute('data-status', 'done');
  if (nxt && nxt.getAttribute('data-status') === 'locked') {
    nxt.setAttribute('data-status', 'active');
  }
  // Entering availability: rebuild it from current racers + the returning swimmers
  // just kept on the previous step, so an estimated swimmer can be marked absent.
  if (nextId === 'step-roster') _rebuildAbsencePanel();
  if (nextId === 'step-run') {
    const runBtn = document.getElementById('runBtn');
    if (runBtn) runBtn.disabled = false;
  }
  smoothScrollToEl(nxt);
}

// Build the availability list = current-season racers (your_roster) + the
// returning swimmers still CHECKED on the imputation step (so estimated swimmers
// who don't yet "exist" this season can still be declared absent). Re-applies this
// meet's saved absences (saved per team + week).
function _rebuildAbsencePanel() {
  const base = window._YOUR_ROSTER || [];
  const keptReturners = Array.from(
    document.querySelectorAll('#impYourArea input.imp-inc:checked')).map(c => c.value);
  const names = [...new Set([...base, ...keptReturners])]
                  .sort((a, b) => a.localeCompare(b));
  _renderAbsencePanel('rosterArea', names, 'absent', 'absentHeader', window._YOUR_ABSENT_PRE || []);
}

async function doSetup() {
  const btn = document.getElementById('setupBtn');
  const msg = document.getElementById('setupMsg');
  const cfg = getConfig();
  if (!cfg.your_team || !cfg.opp_team) {
    msg.className = 'status error'; msg.textContent = 'Pick both teams.'; return;
  }
  if (!cfg.week) {
    msg.className = 'status error'; msg.textContent = 'Pick a week.'; return;
  }
  btn.disabled = true;
  msg.className = 'status';
  msg.textContent = 'Loading profile data...';
  try {
    const r = await fetch('/api/load_setup', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(cfg),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    let parts = [];
    parts.push(`${cfg.your_team}: ${d.your_n} swimmers / ${d.your_times} times`);
    parts.push(`${cfg.opp_team}: ${d.opp_n} swimmers / ${d.opp_times} times`);
    let html = '<span class="ok-text">Loaded.</span> ' + parts.join(' · ');
    if (d.warnings && d.warnings.length) {
      html += '<br><span style="color:var(--win-mid)">⚠ ' + d.warnings.join(' · ') + '</span>';
    }
    msg.className = 'status ok';
    msg.innerHTML = html;
    // Load done: mark steps 1-2 done, unlock availability (step 3). The user
    // walks the rest via "Next →" (advanceStep), filling the connector line.
    document.getElementById('step-setup').setAttribute('data-status', 'done');
    document.getElementById('step-upload').setAttribute('data-status', 'done');
    // Returning-swimmers (imputation) review comes first now, so an estimated
    // swimmer can be carried into the availability list and marked absent.
    document.getElementById('step-impute').setAttribute('data-status', 'active');
    document.getElementById('step-roster').setAttribute('data-status', 'locked');
    document.getElementById('step-run').setAttribute('data-status', 'locked');
    const runBtn = document.getElementById('runBtn');
    if (runBtn) runBtn.disabled = true;
    const adv = document.getElementById('step-advanced');
    if (adv) adv.setAttribute('data-status', 'active');
    document.getElementById('rosterYourTitle').textContent = cfg.your_team;
    document.getElementById('rosterOppTitle').textContent  = cfg.opp_team;
    // Stash for building the availability list (racers + kept returners) and for
    // restoring this meet's saved absences.
    window._YOUR_ROSTER     = d.your_roster || [];
    window._YOUR_ABSENT_PRE = d.your_absent_pre || [];
    // Imputation toggle is saved per (team, week); default ON when never set.
    const impBox = document.getElementById('useImputation');
    if (impBox) impBox.checked = (d.use_imputation_pre == null) ? true : !!d.use_imputation_pre;
    renderImputationReview(d.your_imp_review || [], d.opp_imp_review || [],
                           d.your_excludes_pre || [], d.opp_excludes_pre || [],
                           cfg.your_team, cfg.opp_team);
    renderNameFlags(d.your_name_flags || [], cfg.your_team, d.your_name_auto || 0);
    renderOppRoster(d.opp_roster || []);
    _initManualTimes(d.your_roster || [], d.events || [], d.your_manual_times || []);
    _rebuildAbsencePanel();   // racers + kept returners; saved absences applied
    // Step 2 → 3: glide down to the returning-swimmers step now that it's populated.
    smoothScrollToEl(document.getElementById('step-impute'));
  } catch(e) {
    msg.className = 'status error';
    msg.textContent = 'Error: ' + e.message;
    btn.disabled = false;
  }
}

// Render an availability panel (checkbox = "here this week"; unchecked = absent)
// into areaId. Used for both your team and the opponent; each gets its own input
// class + header so the two counts update independently. preAbsent = names that
// start UNCHECKED (this meet's saved absences, restored per team + week).
function _renderAbsencePanel(areaId, swimmers, inputClass, headerId, preAbsent) {
  const area = document.getElementById(areaId);
  if (!area) return;
  if (!swimmers || !swimmers.length) {
    area.innerHTML = '<span class="note">No swimmers found.</span>';
    return;
  }
  const absentSet = new Set((preAbsent || []).map(n => n.toLowerCase()));
  let nAbsent = 0;
  const html = swimmers.map(name => {
    const safe = name.replace(/"/g, '&quot;');
    const isAbsent = absentSet.has(name.toLowerCase());
    if (isAbsent) nAbsent++;
    return `<label data-name="${safe.toLowerCase()}">
              <input type="checkbox" class="${inputClass}" value="${safe}" ${isAbsent ? '' : 'checked'} onchange="updateAbsenceHeader('${areaId}','${headerId}','${inputClass}')">
              <span>${safe}</span>
            </label>`;
  }).join('');
  area.innerHTML = `<div id="${headerId}" class="note" style="margin:0 0 10px">${swimmers.length} swimmers · ${nAbsent} marked absent</div>
                    <div class="paste-absent">
                      <label class="paste-absent-label" for="${areaId}-pasteBox">Mark absent from a paste</label>
                      <textarea id="${areaId}-pasteBox" class="paste-absent-box" rows="3" placeholder="Paste a roster or entry list — one swimmer per line, &quot;Brightwell, Ada&quot; or &quot;Ada Brightwell&quot;. Ages and times are ignored."></textarea>
                      <div class="paste-absent-actions">
                        <button type="button" class="secondary" onclick="markAbsentFromPaste('${areaId}','${inputClass}','${headerId}')">Mark absent from paste</button>
                        <span id="${areaId}-pasteResult" class="paste-absent-result note"></span>
                      </div>
                    </div>
                    <input type="search" class="absence-search" placeholder="Search swimmers to mark absent…" aria-label="Search swimmers" oninput="filterAbsencePanel('${areaId}', this.value)">
                    <div class="roster-grid">${html}</div>`;
}

// Normalize a name to a match key: lowercase, drop periods, drop single-letter
// middle initials, collapse whitespace. Mirrors the server's normalize_name so a
// pasted "Deveraux, Samantha P" matches the roster's "Samantha Deveraux".
function _normNameKey(name) {
  let parts = (name || '').toLowerCase().replace(/[.]/g, ' ').replace(/[’]/g, "'")
                .trim().split(/\s+/).filter(Boolean);
  if (parts.length > 2) {
    parts = [parts[0], ...parts.slice(1, -1).filter(p => p.length > 1), parts[parts.length - 1]];
  }
  return parts.join(' ');
}

// Pull swimmer names out of a pasted block (SwimTopia entry sheet, roster export,
// a plain list…). Handles "Last, First   age", "First Last", and ignores the time
// / dash / age noise that comes along in a copy-paste.
function _parseAbsenceNames(text) {
  const out = [];
  (text || '').split(/\r?\n/).forEach(raw => {
    let line = (raw || '').replace(/\t/g, ' ').trim();
    if (!line) return;
    // Skip lines that are only times / dashes / numbers (e.g. "57.59", "1:00.53", "--").
    if (/^[\d:.\s\-–—]+$/.test(line)) return;
    // Strip a trailing standalone age ("Kestrel, Cora   10" -> "Kestrel, Cora").
    line = line.replace(/\s+\d{1,3}\s*$/, '').trim();
    if (!line) return;
    let name = null;
    if (line.includes(',')) {
      const comma = line.indexOf(',');
      const last  = line.slice(0, comma).trim();
      const first = line.slice(comma + 1).trim();
      if (first && last && /[A-Za-z]/.test(first) && /[A-Za-z]/.test(last)) {
        name = `${first} ${last}`;
      }
    } else if (/\s/.test(line) && /^[A-Za-z][A-Za-z'’.\-\s]+$/.test(line)) {
      name = line;   // "First Last" with no stray characters
    }
    if (name) out.push(name.replace(/\s+/g, ' ').trim());
  });
  return out;
}

// Uncheck (= mark absent) every roster checkbox whose swimmer appears in the
// pasted list. Reports how many were marked and any names not found on the roster.
function markAbsentFromPaste(areaId, inputClass, headerId) {
  const box = document.getElementById(`${areaId}-pasteBox`);
  const resultEl = document.getElementById(`${areaId}-pasteResult`);
  if (!box) return;
  const names = _parseAbsenceNames(box.value);
  if (!names.length) {
    if (resultEl) resultEl.textContent = 'No swimmer names found in the paste.';
    return;
  }
  const map = {};
  document.querySelectorAll(`#${areaId} input.${inputClass}`).forEach(cb => {
    map[_normNameKey(cb.value)] = cb;
  });
  let marked = 0, already = 0;
  const notFound = [], seen = new Set();
  names.forEach(nm => {
    const key = _normNameKey(nm);
    if (!key || seen.has(key)) return;
    seen.add(key);
    const cb = map[key];
    if (cb) {
      if (cb.checked) { cb.checked = false; marked++; } else { already++; }
    } else {
      notFound.push(nm);
    }
  });
  updateAbsenceHeader(areaId, headerId, inputClass);
  if (resultEl) {
    let msg = `Marked ${marked} absent`;
    if (already) msg += ` (${already} already were)`;
    if (notFound.length) {
      const show = notFound.slice(0, 6).join(', ');
      msg += ` · ${notFound.length} not on roster: ${show}${notFound.length > 6 ? '…' : ''}`;
    }
    resultEl.textContent = msg;
  }
}

// Filter the absence checklist as the user types — a fast way to find and mark a
// specific swimmer absent on a big roster. Only toggles row visibility, so
// checkbox state (and the "N marked absent" count) is preserved across searches.
function filterAbsencePanel(areaId, query) {
  const area = document.getElementById(areaId);
  if (!area) return;
  const q = (query || '').toLowerCase().trim();
  const grid = area.querySelector('.roster-grid');
  if (!grid) return;
  let shown = 0;
  grid.querySelectorAll('label').forEach(label => {
    const match = !q || (label.getAttribute('data-name') || '').includes(q);
    label.style.display = match ? '' : 'none';
    if (match) shown++;
  });
  let empty = area.querySelector('.absence-empty');
  if (shown === 0) {
    if (!empty) {
      empty = document.createElement('div');
      empty.className = 'note absence-empty';
      empty.style.margin = '8px 0 0';
      grid.after(empty);
    }
    empty.textContent = `No swimmers match “${query}”.`;
  } else if (empty) {
    empty.remove();
  }
}

function renderRoster(swimmers) {
  _renderAbsencePanel('rosterArea', swimmers, 'absent', 'absentHeader');
}
function renderOppRoster(swimmers) {
  _renderAbsencePanel('oppRosterArea', swimmers, 'absent-opp', 'oppAbsentHeader');
}

function updateAbsenceHeader(areaId, headerId, inputClass) {
  const total   = document.querySelectorAll(`#${areaId} input.${inputClass}`).length;
  const present = document.querySelectorAll(`#${areaId} input.${inputClass}:checked`).length;
  const absent  = total - present;   // unchecked = not here this week
  const hdr     = document.getElementById(headerId);
  if (hdr) hdr.textContent = `${total} swimmers · ${absent} marked absent`;
  if (areaId === 'rosterArea') _queuePrefsSave();   // your-team availability → save now
}

// ── Immediate save of availability + returning-swimmer choices ──────────────────
// Persist the moment the coach changes something, so choices stick without having
// to run the optimizer. Debounced, and only sends a field whose panel is actually
// rendered (so a not-yet-built panel can't overwrite a good saved value).
let _prefsSaveTimer = null;
function _queuePrefsSave() {
  clearTimeout(_prefsSaveTimer);
  _showPrefsStatus('Saving…');
  _prefsSaveTimer = setTimeout(_savePrefsNow, 450);
}
async function _savePrefsNow() {
  const cfg = getConfig();
  if (!cfg.your_team || !cfg.week) return;
  const body = { your_team: cfg.your_team, year: cfg.year, week: cfg.week };
  const rosterInputs = document.querySelectorAll('#rosterArea input.absent');
  if (rosterInputs.length) {
    body.absent = Array.from(rosterInputs).filter(c => !c.checked).map(c => c.value);
  }
  const impInputs = document.querySelectorAll('#impYourArea input.imp-inc');
  if (impInputs.length) {
    body.your_excludes = Array.from(impInputs).filter(c => !c.checked).map(c => c.value);
  }
  const impBox = document.getElementById('useImputation');
  if (impBox) body.use_imputation = impBox.checked;
  try {
    const r = await fetch('/api/save_prefs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    _showPrefsStatus(r.ok ? 'Saved ✓' : 'Save failed', r.ok ? 'ok' : 'err');
  } catch (e) {
    _showPrefsStatus('Save failed', 'err');
  }
}
function _showPrefsStatus(text, cls) {
  let el = document.getElementById('prefsSaved');
  if (!el) {
    el = document.createElement('div');
    el.id = 'prefsSaved';
    el.className = 'prefs-saved';
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.className = 'prefs-saved show' + (cls ? ' ' + cls : '');
  clearTimeout(el._hideTimer);
  if (cls) el._hideTimer = setTimeout(() => { el.className = 'prefs-saved'; }, 1600);
}

function _renderImpPanel(areaId, swimmers, preChecked, teamLabel) {
  const area = document.getElementById(areaId);
  if (!swimmers || !swimmers.length) {
    area.innerHTML = '<span class="note">Nothing to review — everyone on the team has already raced this season.</span>';
    return;
  }
  // preChecked is the saved EXCLUDE list. Checkbox = "on team / include in imputation".
  // So a swimmer in the saved-exclude list starts UNCHECKED; everyone else starts CHECKED.
  const excludeSet = new Set((preChecked || []).map(s => s.toLowerCase()));
  const lc = name => name.toLowerCase().replace(/\s+[a-z]\s+/g, ' ').replace(/\s+/g, ' ').trim();
  const rows = swimmers.map(sw => {
    const safe   = sw.name.replace(/"/g, '&quot;');
    const isExcluded = excludeSet.has(lc(sw.name)) || excludeSet.has(sw.name.toLowerCase());
    const isChecked  = !isExcluded;
    const colorAge   = sw.last_age_grp || '?';
    return `<label>
              <input type="checkbox" class="imp-inc" value="${safe}" ${isChecked ? 'checked' : ''} onchange="updateImpCount('${areaId}')">
              <span>${safe}</span>
              <span class="swimmer-meta">
                <span>last raced ${sw.last_raced}</span>
                <span>${colorAge}</span>
                <span>(${sw.n_prior_races} races)</span>
              </span>
            </label>`;
  }).join('');
  const hdrId = areaId + 'Header';
  const excludedNow = swimmers.length - swimmers.filter(sw =>
      !excludeSet.has(lc(sw.name)) && !excludeSet.has(sw.name.toLowerCase())).length;
  area.innerHTML = `<div id="${hdrId}" class="note" style="margin:0 0 8px">${swimmers.length} swimmers · ${excludedNow} excluded</div>
                    <div class="checkbox-list">${rows}</div>`;
}

// ── Manual time entry (Build page) ──────────────────────────────────────────────
// Enter a real time the app doesn't have (usually a DQ'd swim). Saved per team and
// merged into the profiles as a real time, so the swimmer is seeded on it.
function _mtEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function _rebuildCombo(sel) {
  // The combobox snapshots its options at init, so a dynamically refilled
  // <select> needs a teardown + re-init to show the new list.
  const wrap = sel.closest('.combo');
  if (wrap) {
    wrap.parentNode.insertBefore(sel, wrap);
    wrap.remove();
  }
  delete sel.dataset.comboReady;
  sel.classList.remove('combo-source');
  initCombobox(sel);
}

function _initManualTimes(roster, events, existing) {
  const dl = document.getElementById('rosterDatalist');
  if (dl) dl.innerHTML = (roster || []).map(n => `<option value="${_mtEsc(n)}"></option>`).join('');
  const sel = document.getElementById('mtEvent');
  if (sel) {
    sel.innerHTML = '<option value="">Event…</option>' +
      (events || []).map(e => `<option value="${_mtEsc(e)}">${_mtEsc(e)}</option>`).join('');
    _rebuildCombo(sel);
  }
  renderManualTimes(existing || []);
}

function renderManualTimes(times) {
  window._MANUAL_TIMES = times || [];
  const box = document.getElementById('mtList');
  if (!box) return;
  box.innerHTML = (times || []).map(t => `
    <div class="manual-time-row">
      <span class="manual-time-txt"><b>${_mtEsc(t.name)}</b> · ${_mtEsc(t.event)} · ${_mtEsc(t.time)}</span>
      <button type="button" class="mt-remove" title="Remove"
              onclick="removeManualTime(this.dataset.n, this.dataset.e)"
              data-n="${_mtEsc(t.name)}" data-e="${_mtEsc(t.event)}">&times;</button>
    </div>`).join('');
}

async function addManualTime() {
  const cfg    = getConfig();
  const name   = (document.getElementById('mtName').value  || '').trim();
  const event  = (document.getElementById('mtEvent').value || '').trim();
  const time   = (document.getElementById('mtTime').value  || '').trim();
  const status = document.getElementById('mtStatus');
  const set = (msg, ok) => { if (status) { status.textContent = msg; status.className = 'manual-time-status note' + (ok === true ? ' ok' : ok === false ? ' err' : ''); } };
  if (!cfg.your_team) { set('Load a team first.', false); return; }
  if (!name || !event || !time) { set('Enter a swimmer, an event, and a time.', false); return; }
  set('Saving…');
  try {
    const r = await fetch('/api/save_manual_time', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team: cfg.your_team, name, event, time }),
    });
    const d = await r.json();
    if (d.error) { set(d.error, false); return; }
    renderManualTimes(d.times);
    document.getElementById('mtName').value = '';
    document.getElementById('mtTime').value = '';
    set('Saved ✓ — re-run the optimizer to use it.', true);
  } catch (e) { set('Save failed.', false); }
}

async function removeManualTime(name, event) {
  const cfg = getConfig();
  try {
    const r = await fetch('/api/delete_manual_time', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team: cfg.your_team, name, event }),
    });
    const d = await r.json();
    renderManualTimes(d.times || []);
  } catch (e) { /* best-effort */ }
}

function updateImpCount(areaId) {
  const total    = document.querySelectorAll('#' + areaId + ' input.imp-inc').length;
  const included = document.querySelectorAll('#' + areaId + ' input.imp-inc:checked').length;
  const excluded = total - included;
  const hdr = document.getElementById(areaId + 'Header');
  if (hdr) hdr.textContent = `${total} swimmers · ${excluded} excluded`;
  if (areaId === 'impYourArea') _queuePrefsSave();   // returning-swimmer choice → save now
}

function renderImputationReview(yourSw, oppSw, yourExc, oppExc, yourName, oppName) {
  // Only your team's imputation is reviewed — the opponent's roster is rarely
  // known, so its panel was removed. (oppSw/oppExc kept in the signature so the
  // existing call site doesn't need to change; any saved opp excludes still
  // apply server-side.)
  const yt = document.getElementById('impYourTitle');
  if (yt) yt.textContent = yourName + ' · ' + yourSw.length + ' returning swimmer' + (yourSw.length === 1 ? '' : 's');
  _renderImpPanel('impYourArea', yourSw, yourExc, yourName);
}

// ── Ambiguous-name confirmation ────────────────────────────────────────────
// Each flag is a {ladder_name, ladder_age, hist_name, hist_age, ...} pair where
// the ladder name didn't auto-merge but shares a last name + gender with someone
// in last year's results. We ask "same person?" and remember the answer forever.
let _nameFlags = [];
let _nameFlagTeam = '';

function renderNameFlags(flags, team, autoResolved) {
  _nameFlags = flags || [];
  _nameFlagTeam = team || '';
  const block = document.getElementById('nameFlagBlock');
  const area  = document.getElementById('nameFlagArea');
  const msg   = document.getElementById('nameFlagMsg');
  if (msg) { msg.textContent = ''; msg.className = 'status'; }
  if (!block || !area) return;
  const hdr      = document.getElementById('nameFlagHdr');
  const intro    = document.getElementById('nameFlagIntro');
  const controls = document.getElementById('nameFlagControls');
  // The age rule may have quietly resolved obvious sibling/aged-out pairs even
  // when none remain to ask about — surface that as a one-line reassurance.
  const autoNote = autoResolved
    ? `<p class="note" style="margin:0 0 10px">✓ ${autoResolved} obvious ${autoResolved === 1 ? 'pair was' : 'pairs were'} auto-resolved by age (different ages → different swimmers).</p>`
    : '';
  if (!_nameFlags.length) {
    if (!autoResolved) { block.style.display = 'none'; area.innerHTML = ''; return; }
    // Nothing to ask, but we did resolve some — show a brief all-clear note only.
    if (hdr)   hdr.textContent = 'Swimmer identities — all clear';
    if (intro) intro.style.display = 'none';
    if (controls) controls.style.display = 'none';
    area.innerHTML = autoNote + '<p class="note" style="margin:0">Nothing to confirm — every look-alike was sorted out by age.</p>';
    block.style.display = '';
    return;
  }
  if (intro) intro.style.display = '';
  if (controls) controls.style.display = '';
  if (hdr) hdr.textContent = 'Is this the same swimmer?';
  // Default each pair to "different" — the safe choice. The user flips the true
  // matches to "same". Doing nothing therefore never merges two people by accident.
  const esc = s => String(s == null ? '' : s).replace(/"/g, '&quot;').replace(/</g, '&lt;');
  const rows = _nameFlags.map((f, i) => `
    <div class="name-flag-row">
      <div class="name-flag-people">
        <span class="name-flag-person"><b>${esc(f.ladder_name)}</b><span class="swimmer-meta"><span>your ladder · ${esc(f.ladder_age)}</span></span></span>
        <span class="name-flag-vs">vs</span>
        <span class="name-flag-person"><b>${esc(f.hist_name)}</b><span class="swimmer-meta"><span>last year · ${esc(f.hist_age)}</span></span></span>
        ${f.hint ? `<span class="name-flag-hint">${esc(f.hint)}</span>` : ''}
      </div>
      <div class="name-flag-choice">
        <label><input type="radio" name="nameflag-${i}" value="same"> Same person</label>
        <label><input type="radio" name="nameflag-${i}" value="diff" checked> Different people</label>
      </div>
    </div>`).join('');
  area.innerHTML = autoNote + rows;
  block.style.display = '';
}

async function saveNameFlags() {
  const btn = document.getElementById('nameFlagSaveBtn');
  const msg = document.getElementById('nameFlagMsg');
  const decisions = _nameFlags.map((f, i) => {
    const sel = document.querySelector(`input[name="nameflag-${i}"]:checked`);
    return {
      ladder_norm: f.ladder_norm,
      hist_norm:   f.hist_norm,
      hist_name:   f.hist_name,
      same:        sel ? sel.value === 'same' : false,
    };
  });
  if (btn) btn.disabled = true;
  if (msg) { msg.className = 'status'; msg.textContent = 'Saving…'; }
  try {
    const r = await fetch('/api/save_name_matches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ team: _nameFlagTeam, decisions }),
    });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || ('HTTP ' + r.status));
    const n = d.merged || 0;
    if (msg) {
      msg.className = 'status ok';
      msg.innerHTML = `<span class="ok-text">Saved.</span> ${n} merged · reloading with the changes…`;
    }
    // Rebuild profiles with the merged identities. doSetup() re-renders every
    // panel (availability + returning + name flags), so resolved pairs vanish.
    await doSetup();
  } catch (e) {
    if (msg) { msg.className = 'status error'; msg.textContent = 'Error: ' + e.message; }
    if (btn) btn.disabled = false;
  }
}

async function doUploadLadder() {
  const btn = document.getElementById('ladderBtn');
  const msg = document.getElementById('ladderMsg');
  const file = document.getElementById('ladderFile').files[0];
  const team = document.getElementById('yourTeam').value;
  if (!file) { msg.className = 'status error'; msg.textContent = 'Pick a PDF first.'; return; }
  btn.disabled = true;
  msg.className = 'status';
  msg.textContent = 'Parsing PDF...';
  const fd = new FormData();
  fd.append('file', file);
  fd.append('team', team);
  try {
    const r = await fetch('/api/upload_ladder', { method: 'POST', body: fd });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    const src = d.sources || {};
    const srcStr = Object.entries(src).map(([k,v]) => `${k}: ${v}`).join(' · ');
    msg.className = 'status ok';
    msg.innerHTML = `<span class="ok-text">Parsed</span> ${d.entries} entries · ${d.swimmers} swimmers · ${d.events} events`
                  + `<br><span class="note">${srcStr}`
                  + (d.aliases_used > 0 ? ` · ${d.aliases_used} alias rules applied` : '')
                  + ` · saved</span>`;
    refreshLadderInfo();   // update the "saved ladder on file" notice
    // Re-run setup so ladder data merges into profiles
    doSetup();
  } catch(e) {
    msg.className = 'status error';
    msg.textContent = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}

/* ─── Quirky messages cycled in the loading overlay during optimize ──── */
const LOADING_MESSAGES = [
  "Finding the missing swim cap…",
  "Negotiating snack-bar pricing…",
  "Simulating one parent volunteering, twelve declining…",
  "Asking the coach what they'd actually do…",
  "Explaining the meet won't actually end at noon…",
  "Looking for the timer who wandered off…",
  "Running the meet 10,000 times so you don't have to…",
  "Running every lineup we could think of…",
  "Calculating the odds someone forgets their goggles…",
  "Testing the theory that lane 4 wins…",
  "Simulating the odds of thunder delay…",
  "Simulating 500 false starts…",
  "Modeling the parking lot at 7am…",
  "Predicting who forgets which event they're in…",
  "Reapplying sunscreen, again…",
  "Restocking the snack bar's last hot dog…",
  "Bargaining with the sun for more shade…",
  "Counting how many events are left…",
  "Pretending we're still on schedule…",
  "Drying off just in time for the next race…",
  "Reading times off a soggy timer card…",
];

// How long each loading message stays up. 5s is a comfortable read; with ~21
// messages the set spans ~105s, so a typical 60–90s run shows each ~once.
const MESSAGE_DURATION_MS = 5000;

// Fisher–Yates shuffle, returns a new array (doesn't mutate the source).
function _shuffled(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function _showLoadingOverlay() {
  const ov  = document.getElementById('loadingOverlay');
  const msg = document.getElementById('loadingMessage');
  if (!ov || !msg) return null;
  // Restart logo animations from scratch so it always starts as a static logo
  ov.querySelectorAll('.notch-track, .notch-dot').forEach(el => {
    el.style.animation = 'none';
    void el.getBoundingClientRect();
    el.style.animation = '';
  });
  ov.classList.add('visible');
  ov.setAttribute('aria-hidden', 'false');
  // Always lead with "Running the optimizer…", then a fresh random order of
  // the quirky messages, paced so the set spans the expected optimize time.
  const messages = ['Running the optimizer…'].concat(_shuffled(LOADING_MESSAGES));
  msg.textContent = messages[0];
  let i = 0;
  const id = setInterval(() => {
    // Fade out, swap text, fade in — keeps the transitions visible.
    msg.classList.add('fading');
    setTimeout(() => {
      i = (i + 1) % messages.length;
      msg.textContent = messages[i];
      msg.classList.remove('fading');
    }, 320);
  }, MESSAGE_DURATION_MS);
  return id;
}

function _hideLoadingOverlay(intervalId) {
  if (intervalId) clearInterval(intervalId);
  const ov = document.getElementById('loadingOverlay');
  if (!ov) return;
  ov.classList.remove('visible');
  ov.setAttribute('aria-hidden', 'true');
}

async function doRun() {
  const btn = document.getElementById('runBtn');
  const msg = document.getElementById('runMsg');
  btn.disabled = true;
  msg.className = 'status';
  msg.textContent = 'Running optimizer…';
  const overlayInterval = _showLoadingOverlay();
  try {
    const r = await fetch('/api/run', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(getConfig())
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    msg.className = 'status ok';
    msg.textContent = 'Done · loading lineup…';
    // Server-side data is now in the Flask cache; the lineup page will pick it up
    // and write it to localStorage on load (via LineupStorage.persistIfFresh).
    window.location.href = '/lineup';
  } catch(e) {
    _hideLoadingOverlay(overlayInterval);
    msg.className = 'status error';
    msg.textContent = 'Error: ' + e.message;
    btn.disabled = false;
  }
}
