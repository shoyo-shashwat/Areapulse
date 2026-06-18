'use strict';

/* ═══════════════════════════════════════════════════════════════
   AREAPULSE CORE — core.js
   Sidebar · Clock · Command Palette · SLA Countdowns · Toasts
   ═══════════════════════════════════════════════════════════════ */

// ── SIDEBAR COLLAPSE ─────────────────────────────────────────
function initSidebar() {
  const sidebar     = document.getElementById('sidebar');
  const collapseBtn = document.getElementById('sidebar-collapse-btn');
  const hamburger   = document.getElementById('topbar-hamburger');
  if (!sidebar) return;

  const KEY = 'sidebar_collapsed';
  const setCollapsed = (v) => {
    sidebar.classList.toggle('collapsed', v);
    localStorage.setItem(KEY, v ? '1' : '');
    const icon = collapseBtn?.querySelector('.collapse-icon');
    if (icon) icon.style.transform = v ? 'rotate(180deg)' : '';
  };
  if (localStorage.getItem(KEY)) setCollapsed(true);
  if (collapseBtn) collapseBtn.addEventListener('click', () => setCollapsed(!sidebar.classList.contains('collapsed')));
  if (hamburger) hamburger.addEventListener('click', () => sidebar.classList.toggle('mobile-open'));
  sidebar.addEventListener('mouseenter', () => {
    if (window.innerWidth >= 768 && window.innerWidth < 1024 && sidebar.classList.contains('collapsed'))
      sidebar.classList.add('hover-expanded');
  });
  sidebar.addEventListener('mouseleave', () => sidebar.classList.remove('hover-expanded'));
}

// ── TOPBAR CLOCK ─────────────────────────────────────────────
function initClock() {
  const el = document.getElementById('topbar-clock');
  if (!el) return;
  const update = () => {
    el.textContent = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
  };
  update();
  setInterval(update, 1000);
}

// ── COMMAND PALETTE ──────────────────────────────────────────
const CommandPalette = (() => {
  let backdrop, input, results, items = [], focusIdx = -1;

  // ★ UPDATED: all endpoint names use blueprint dot notation
  const NAV_ITEMS = {
    gov: [
      { icon: '📊', label: 'Dashboard',       sub: 'Overview & KPIs',       url: '/gov/dashboard',         endpoint: 'gov.dashboard' },
      { icon: '📋', label: 'Issue Queue',      sub: 'All active issues',     url: '/gov/queue',             endpoint: 'gov.queue' },
      { icon: '⏱',  label: 'SLA Board',        sub: 'Kanban SLA tracker',    url: '/gov/sla',               endpoint: 'gov.sla' },
      { icon: '🗺',  label: 'Live Map',         sub: 'Geo issue view',        url: '/gov/map',               endpoint: 'gov.map_view' },
      { icon: '📊', label: 'Analytics',        sub: 'Ward performance',      url: '/gov/analytics',         endpoint: 'gov.analytics' },
      { icon: '🏢', label: 'Departments',      sub: 'Dept management',       url: '/gov/departments',       endpoint: 'gov.departments' },
      { icon: '🤝', label: 'NGO Partners',     sub: 'Coordination view',     url: '/gov/ngo-coordination',  endpoint: 'gov.ngo_coordination' },
      { icon: '📄', label: 'Reports',          sub: 'Export & generate',     url: '/gov/reports',           endpoint: 'gov.reports' },
      { icon: '🤖', label: 'AI Copilot',       sub: 'AI assistant',          url: '/gov/ai-assistant',      endpoint: 'gov.ai_assistant' },
      { icon: '🔔', label: 'Notifications',    sub: 'All alerts',            url: '/gov/notifications',     endpoint: 'gov.notifications' },
      { icon: '⚙',  label: 'Settings',         sub: 'Account & prefs',       url: '/gov/settings',          endpoint: 'gov.settings' },
    ],
    ngo: [
      { icon: '📊', label: 'Dashboard',        sub: 'Impact overview',       url: '/ngo/dashboard',         endpoint: 'ngo.dashboard' },
      { icon: '🗺',  label: 'Opportunities',    sub: 'Matching issues',       url: '/ngo/opportunities',     endpoint: 'ngo.opportunities' },
      { icon: '📁', label: 'Active Projects',  sub: 'Current commitments',   url: '/ngo/projects',          endpoint: 'ngo.projects' },
      { icon: '💚', label: 'Impact Tracker',   sub: 'Metrics & proof',       url: '/ngo/impact',            endpoint: 'ngo.impact' },
      { icon: '🗺',  label: 'Live Map',         sub: 'Geo issue view',        url: '/ngo/map',               endpoint: 'ngo.map_view' },
      { icon: '📊', label: 'Analytics',        sub: 'Area analysis',         url: '/ngo/analytics',         endpoint: 'ngo.analytics' },
      { icon: '🤝', label: 'Gov Coordination', sub: 'Partnership view',      url: '/ngo/gov-coordination',  endpoint: 'ngo.gov_coordination' },
      { icon: '📄', label: 'Reports',          sub: 'Impact reports',        url: '/ngo/reports',           endpoint: 'ngo.reports' },
      { icon: '🤖', label: 'AI Assistant',     sub: 'Smart recommendations', url: '/ngo/ai-assistant',      endpoint: 'ngo.ai_assistant' },
      { icon: '🔔', label: 'Notifications',    sub: 'All alerts',            url: '/ngo/notifications',     endpoint: 'ngo.notifications' },
      { icon: '⚙',  label: 'Settings',         sub: 'Account & prefs',       url: '/ngo/settings',          endpoint: 'ngo.settings' },
    ],
  };

  const init = () => {
    backdrop = document.getElementById('cmdpal-backdrop');
    input    = document.getElementById('cmdpal-input');
    results  = document.getElementById('cmdpal-results');
    if (!backdrop) return;

    const role = document.body.classList.contains('gov-mode') ? 'gov' : 'ngo';
    items = NAV_ITEMS[role] || NAV_ITEMS.gov;

    document.getElementById('topbar-search')?.addEventListener('click', open);
    document.getElementById('sidebar-search')?.addEventListener('click', open);
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); open(); }
      if (e.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) { e.preventDefault(); open(); }
    });
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
    input?.addEventListener('input', search);
    input?.addEventListener('keydown', handleKeydown);
  };

  const open  = () => { backdrop?.classList.add('open'); input?.focus(); render(items); };
  const close = () => { backdrop?.classList.remove('open'); if (input) input.value = ''; focusIdx = -1; };

  const search = () => {
    const q = input.value.toLowerCase().trim();
    if (!q) { render(items); return; }
    render(items.filter(i => i.label.toLowerCase().includes(q) || i.sub.toLowerCase().includes(q)));
  };

  const render = (list) => {
    if (!results) return;
    focusIdx = -1;
    if (!list.length) { results.innerHTML = '<div style="padding:20px;text-align:center;font-size:13px;color:var(--t4)">No results</div>'; return; }
    results.innerHTML = list.map((item, idx) => `
      <div class="cmdpal-item" data-idx="${idx}" data-url="${item.url}" onclick="window.location='${item.url}'">
        <span class="cmdpal-icon">${item.icon}</span>
        <div><div class="cmdpal-label">${item.label}</div><div class="cmdpal-sub">${item.sub}</div></div>
      </div>`).join('');
  };

  const handleKeydown = (e) => {
    const els = results?.querySelectorAll('.cmdpal-item') || [];
    if (e.key === 'ArrowDown')  { e.preventDefault(); focusIdx = Math.min(focusIdx + 1, els.length - 1); els[focusIdx]?.classList.add('focused'); els[focusIdx - 1]?.classList.remove('focused'); }
    if (e.key === 'ArrowUp')    { e.preventDefault(); focusIdx = Math.max(focusIdx - 1, 0); els[focusIdx]?.classList.add('focused'); els[focusIdx + 1]?.classList.remove('focused'); }
    if (e.key === 'Enter')      { if (focusIdx >= 0) window.location = els[focusIdx]?.dataset.url; }
    if (e.key === 'Escape')     { close(); }
  };

  return { init, open, close };
})();

// ── SLA COUNTDOWNS ────────────────────────────────────────────
const SLA_HOURS = { sewage:24, electricity:24, traffic:24, noise:24, water:48, streetlight:48, garbage:72, other:120, pothole:168, tree:168 };

function updateSLACountdowns() {
  document.querySelectorAll('[data-sla-timestamp]').forEach(el => {
    const ts  = parseFloat(el.dataset.slaTimestamp) * 1000;
    const tag = el.dataset.slaTag || 'other';
    const sla = (SLA_HOURS[tag] || 120) * 3600 * 1000;
    const due = ts + sla;
    const now = Date.now();
    const rem = due - now;
    const el2 = el.querySelector('.sla-countdown') || el;
    if (rem <= 0) {
      const h = Math.abs(Math.floor(rem / 3600000));
      el2.textContent = `OVERDUE +${h}h`;
      el.classList.add('sla-breached');
    } else {
      const h = Math.floor(rem / 3600000);
      const m = Math.floor((rem % 3600000) / 60000);
      el2.textContent = h > 24 ? `${Math.floor(h/24)}d ${h%24}h` : `${h}h ${m}m`;
    }
  });
}

// ── COUNTER ANIMATION ─────────────────────────────────────────
function animateCounter(el, target, duration = 600) {
  if (!el) return;
  const start = parseInt(el.textContent.replace(/\D/g, '')) || 0;
  if (start === target) return;
  const step  = (target - start) / (duration / 16);
  let   cur   = start;
  const timer = setInterval(() => {
    cur += step;
    if ((step > 0 && cur >= target) || (step < 0 && cur <= target)) {
      el.textContent = target.toLocaleString();
      clearInterval(timer);
    } else {
      el.textContent = Math.round(cur).toLocaleString();
    }
  }, 16);
}

// ── TOAST SYSTEM ─────────────────────────────────────────────
const Toast = (() => {
  let container;
  const get = () => {
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.style.cssText = 'position:fixed;top:72px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none';
      document.body.appendChild(container);
    }
    return container;
  };
  const show = (msg, type = 'info') => {
    const colors = { success:'var(--green)', error:'var(--red)', warning:'var(--amber)', info:'var(--blue)' };
    const icons  = { success:'✓', error:'✕', warning:'⚠', info:'ℹ' };
    const t = document.createElement('div');
    t.style.cssText = `background:var(--bg-surface);border:1px solid var(--border);border-left:3px solid ${colors[type]||colors.info};border-radius:var(--r-md);padding:10px 14px;font-size:13px;font-weight:500;color:var(--t1);box-shadow:var(--sh-md);pointer-events:auto;max-width:320px;animation:fadeIn .2s ease`;
    t.innerHTML = `<span style="color:${colors[type]||colors.info};margin-right:6px">${icons[type]||icons.info}</span>${msg}`;
    get().appendChild(t);
    setTimeout(() => t.remove(), 3500);
  };
  return { success: m => show(m,'success'), error: m => show(m,'error'), warning: m => show(m,'warning'), info: m => show(m,'info') };
})();

// ── INIT ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initClock();
  CommandPalette.init();
  updateSLACountdowns();
  setInterval(updateSLACountdowns, 60000);

  document.querySelectorAll('[data-counter]').forEach(el => {
    animateCounter(el, parseInt(el.dataset.counter) || 0);
  });
});

window.Toast = Toast;
window.animateCounter = animateCounter;
window.updateSLACountdowns = updateSLACountdowns;
window.CommandPalette = CommandPalette;
