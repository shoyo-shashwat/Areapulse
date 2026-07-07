/* ═══════════════════════════════════════════════════════════════
   AREAPULSE VOICE v3  — voice_v2.js
   Click 🎤 (bottom-right) or Ctrl+Shift+V to activate.
   Speaks to Flask /api/voice/parse — Groq key never in browser.
   Works in English, Hindi, Hinglish.

   PATCHES vs original:
   1. issue_escalate  → routes to /ngo/api/escalate for NGO role
   2. ngo_mark_done   → redirects to verification queue, never resolves
   3. ngo_commit      → tries /ngo/api/adopt first, falls back to /ngo/commit
   ═══════════════════════════════════════════════════════════════ */
'use strict';

(function () {

  const ROLE = () => window.APR || 'gov';

  // ── helpers ─────────────────────────────────────────────────
  function nav(url, label) {
    vtoast('→ ' + label, 'success');
    vtts('Opening ' + label);
    setTimeout(() => { window.location.href = url; }, 450);
  }

  async function apiPost(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || r.status);
    return d;
  }

  function vtoast(msg, kind) {
    kind = kind || 'success';
    if (window.Toast && window.Toast[kind]) window.Toast[kind](msg);
  }

  function vtts(text) {
    if (!window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = 'en-IN'; u.rate = 1.05; u.volume = 0.8;
      window.speechSynthesis.speak(u);
    } catch(e) {}
  }

  // ── command executor ─────────────────────────────────────────
  async function execute(cmd, arg) {
    const role = ROLE();
    console.log('[voice] execute:', cmd, arg);
    switch (cmd) {
      // navigation gov
      case 'nav_dashboard':     nav(`/${role}/dashboard`,        'Dashboard'); break;
      case 'nav_queue':         nav(`/${role}/queue`,            'Issue Queue'); break;
      case 'nav_progress':      nav(`/${role}/progress`,         'Progress'); break;
      case 'nav_sla':           nav(`/${role}/sla`,              'SLA Board'); break;
      case 'nav_map':           nav(`/${role}/map`,              'Map'); break;
      case 'nav_analytics':     nav(`/${role}/analytics`,        'Analytics'); break;
      case 'nav_reports':       nav(`/${role}/reports`,          'Reports'); break;
      case 'nav_departments':   nav(`/${role}/departments`,      'Departments'); break;
      case 'nav_ngo_coord':     nav(`/${role}/ngo-coordination`, 'NGO Partners'); break;
      case 'nav_notifications': nav(`/${role}/notifications`,    'Notifications'); break;
      case 'nav_settings':      nav(`/${role}/settings`,         'Settings'); break;
      case 'nav_verify':        nav(`/${role}/verify`,           'Verify Closures'); break;
      case 'nav_accountability':nav(`/${role}/accountability`,   'Accountability'); break;
      case 'nav_ai':            nav(`/${role}/ai-assistant`,     'AI Copilot'); break;
      case 'nav_teams':         nav(`/${role}/teams`,            'Teams'); break;
      // navigation ngo
      case 'nav_gap_map':       nav(`/${role}/opportunities`,    'Gap Map'); break;
      case 'nav_projects':      nav(`/${role}/projects`,         'Projects'); break;
      case 'nav_impact':        nav(`/${role}/impact`,           'Impact'); break;
      case 'nav_volunteers':    nav(`/${role}/volunteers`,       'Volunteers'); break;
      case 'nav_gov_coord':     nav(`/${role}/gov-coordination`, 'Gov Coordination'); break;
      // filters
      case 'filter_area':
        if (!arg) { vtoast('Which area?', 'warning'); break; }
        nav(`/${role}/queue?area=${encodeURIComponent(arg)}`, arg + ' issues');
        break;
      case 'search_issues':
        if (!arg) { vtoast('What are you looking for?', 'warning'); break; }
        nav(`/${role}/queue?q=${encodeURIComponent(arg)}`, 'Search: ' + arg);
        break;
      case 'filter_status':   nav(`/${role}/queue?status=${arg}`,   arg + ' issues'); break;
      case 'filter_tag':      nav(`/${role}/queue?tag=${arg}`,      arg + ' issues'); break;
      case 'filter_severity': nav(`/${role}/queue?severity=${arg}`, arg + ' severity'); break;
      case 'filter_clear':    nav(`/${role}/queue`,                 'All Issues'); break;
      // open issue
      case 'open_issue':
        if (!arg) { vtoast('Which issue number?', 'warning'); break; }
        nav(`/${role}/issue/${arg}`, 'Issue AP-' + arg); break;
      // status changes — resolve always opens proof modal
      case 'issue_start':
      case 'issue_acknowledge':
      case 'issue_resolve':
        if (!arg) { vtoast('Which issue number?', 'warning'); vtts('Which issue?'); break; }
        if (window.showResolveModal) {
          window.showResolveModal(arg);
          vtts('Opening resolve form for issue ' + arg);
        } else {
          vtoast('Open a gov portal page to resolve issues', 'warning');
        }
        break;
      case 'issue_reopen': {
        if (!arg) { vtoast('Which issue number?', 'warning'); vtts('Which issue?'); break; }
        const sm = { issue_start:'in_progress', issue_acknowledge:'acknowledged', issue_reopen:'open' };
        const nm = { issue_start:'Started via voice', issue_acknowledge:'Acknowledged via voice', issue_reopen:'Reopened via voice' };
        try {
          await apiPost('/gov/update-status', { id: arg, status: sm[cmd], note: nm[cmd] });
          vtoast('✓ AP-' + arg + ' ' + sm[cmd].replace('_',' '), 'success');
          vtts('AP ' + arg + ' ' + sm[cmd].replace('_',' '));
          if (/\/(queue|progress|sla)/.test(location.pathname)) setTimeout(() => location.reload(), 600);
        } catch(e) { vtoast('Failed: ' + e.message, 'error'); }
        break;
      }

      // ── PATCH 1: issue_escalate — correct endpoint per role ──
      case 'issue_escalate': {
        if (!arg) { vtoast('Which issue number?', 'warning'); break; }
        if (ROLE() === 'ngo') {
          try {
            await apiPost('/ngo/api/escalate', { issue_id: arg, evidence: 'Escalated via voice', attempts: 1 });
            vtoast('↑ AP-' + arg + ' escalated to government', 'success');
            vtts('Escalated issue ' + arg);
            if (/\/(projects|gov-coordination)/.test(location.pathname)) setTimeout(() => location.reload(), 600);
          } catch(e) { vtoast('Escalation failed: ' + e.message, 'error'); }
        } else {
          try {
            await apiPost('/gov/api/escalate', { id: arg });
            vtoast('↑ AP-' + arg + ' escalated', 'success');
            vtts('Escalated ' + arg);
            if (/\/(queue|progress|sla)/.test(location.pathname)) setTimeout(() => location.reload(), 600);
          } catch(e) { vtoast('Failed: ' + e.message, 'error'); }
        }
        break;
      }

      case 'issue_deescalate': {
        if (!arg) { vtoast('Which issue number?', 'warning'); break; }
        const deUrl = ROLE() === 'ngo' ? '/ngo/api/deescalate' : '/gov/api/deescalate';
        try {
          await apiPost(deUrl, { id: arg, note: 'De-escalated via voice' });
          vtoast('↓ AP-' + arg + ' de-escalated', 'success');
          vtts('De-escalated ' + arg);
          if (/\/(queue|progress|sla)/.test(location.pathname)) setTimeout(() => location.reload(), 600);
        } catch(e) { vtoast('Failed: ' + e.message, 'error'); }
        break;
      }

      // ── PATCH 3: ngo_commit — tries adopt first ──────────────
      case 'ngo_commit': {
        if (!arg) { vtoast('Which issue number?', 'warning'); break; }
        try {
          await apiPost('/ngo/api/adopt', { issue_id: arg, volunteers: 2, eta: '48h', plan: 'Adopted via voice' });
          vtoast('✓ Adopted AP-' + arg + ' as partner', 'success');
          vtts('Adopted issue ' + arg);
          if (/\/(opportunities|projects)/.test(location.pathname)) setTimeout(() => location.reload(), 600);
        } catch(adoptErr) {
          try {
            await apiPost('/ngo/commit', { issue_id: arg, volunteers: 2, eta: '48h', note: 'Adopted via voice' });
            vtoast('✓ Committed to AP-' + arg, 'success');
            vtts('Committed to issue ' + arg);
            if (/\/(opportunities|projects)/.test(location.pathname)) setTimeout(() => location.reload(), 600);
          } catch(e) { vtoast('Failed: ' + e.message, 'error'); }
        }
        break;
      }

      // ── PATCH 2: ngo_mark_done — go to verification queue ────
      case 'ngo_mark_done': {
        if (!arg) { vtoast('Which issue number?', 'warning'); vtts('Which issue?'); break; }
        vtoast('NGOs cannot resolve issues — opening verification queue', 'info');
        vtts('Opening verification queue');
        setTimeout(() => { window.location.href = '/ngo/verify'; }, 500);
        break;
      }

      // bulk
      case 'bulk_start':
        if (window.bulkAction) { window.bulkAction('in_progress'); vtoast('Starting all selected'); }
        else vtoast('Open queue page first', 'warning'); break;
      case 'bulk_resolve':
        if (window.bulkAction) { window.bulkAction('resolved'); vtoast('Resolving all selected'); }
        else vtoast('Open queue page first', 'warning'); break;
      case 'bulk_escalate':
        if (window.bulkAction) { window.bulkAction('escalated'); vtoast('Escalating all selected'); }
        else vtoast('Open queue page first', 'warning'); break;
      case 'bulk_select_all':
        if (window.toggleSelectAll) { window.toggleSelectAll(); vtoast('Selected all'); }
        else vtoast('Open queue page first', 'warning'); break;
      // exports
      case 'export_pdf': window.open(`/${ROLE()}/api/export-pdf`, '_blank'); vtoast('Opening PDF'); break;
      case 'export_csv': window.open(`/${ROLE()}/api/export-csv`, '_blank'); vtoast('Downloading CSV'); break;
      // map
      case 'map_heatmap':
        if (window.toggleHeatmap) { window.toggleHeatmap(); vtoast('Heatmap toggled'); }
        else nav(`/${ROLE()}/map`, 'Map'); break;
      case 'map_reset':
        if (window.mapInstance) { window.mapInstance.setView([28.6139,77.2090],11); vtoast('Map reset'); }
        else nav(`/${ROLE()}/map`, 'Map'); break;
      // notifications
      case 'notif_mark_read':
        if (window.markAllRead) { window.markAllRead(); vtoast('Notifications cleared'); }
        else nav(`/${ROLE()}/notifications`, 'Notifications'); break;
      // teams
      case 'teams_create':
        if (window.openCreate) { window.openCreate(); vtoast('Creating new team'); }
        else nav(`/${ROLE()}/teams`, 'Teams'); break;
      case 'teams_join':
        if (window.openJoin) { window.openJoin(); vtoast('Join a team'); }
        else nav(`/${ROLE()}/teams`, 'Teams'); break;
      // reports
      case 'gen_report':
        if (window.generateReport) { window.generateReport('summary'); }
        else nav(`/${ROLE()}/reports`, 'Reports'); break;
      case 'gen_donor_report':
        if (window.generateDonorReport) { window.generateDonorReport(); }
        else nav(`/${ROLE()}/impact`, 'Impact'); break;
      // util
      case 'page_refresh':
        vtoast('Refreshing…', 'info'); setTimeout(() => location.reload(), 400); break;
      case 'logout': nav('/logout', 'logout'); break;
      case 'help':   showHelp(); break;
      case 'stop':   VoiceEngine.stop(); break;
      case 'unknown':
      default:
        vtoast('Not understood — try "open queue", "start AP 141", "bijli issues dikhao"', 'warning');
        vtts('Not understood');
    }
  }

  function showHelp() {
    const h = [
      'Navigation: "open dashboard" · "queue dikhao" · "progress dikhao" · "map dikhao"',
      'Issue: "start AP 141" · "resolve 42" · "escalate 73" · "de-escalate 15" · "ap131 dikhao"',
      'Filters: "bijli issues" · "Rohini dikhao" · "urgent issues" · "clear filter"',
      'NGO: "adopt 73" · "escalate 42" · "impact dikhao" · "verify queue"',
    ];
    vtoast(h[Math.floor(Math.random() * h.length)], 'info');
  }

  // ── VoiceEngine ───────────────────────────────────────────────
  // Matches original structure: object with init/_buildUI/toggle/start/stop
  const VoiceEngine = {
    recognition: null,
    active: false,
    ui: null,

    init() {
      this._buildUI();
    },

    _buildUI() {
      // Remove any stale elements from previous versions
      document.querySelectorAll('#ap-voice-fab, #voice-fab, #ap-v-btn').forEach(e => e.remove());

      const wrap = document.createElement('div');
      wrap.id = 'ap-voice-fab';
      wrap.style.cssText = [
        'position:fixed', 'bottom:24px', 'right:24px', 'z-index:9998',
        'display:flex', 'flex-direction:column', 'align-items:flex-end', 'gap:8px',
        'pointer-events:none',
      ].join(';');

      wrap.innerHTML = `
        <div id="ap-v-tx"
             style="display:none;background:rgba(15,23,42,0.95);color:#f1f5f9;
                    padding:10px 14px;border-radius:10px;font-size:13px;max-width:300px;
                    box-shadow:0 8px 24px rgba(0,0,0,0.35);border:1px solid rgba(255,255,255,0.08);
                    pointer-events:none;word-break:break-word"></div>
        <div id="ap-v-hint"
             style="display:none;background:rgba(15,23,42,0.9);color:#f1f5f9;
                    padding:7px 14px;border-radius:20px;font-size:12px;pointer-events:none">
          🎙 Listening…
        </div>
        <button id="ap-v-btn"
                title="Voice control — click or Ctrl+Shift+V"
                style="pointer-events:auto;width:54px;height:54px;border-radius:50%;
                       border:none;cursor:pointer;font-size:22px;
                       background:linear-gradient(135deg,#3b82f6,#6366f1);color:white;
                       box-shadow:0 6px 20px rgba(59,130,246,0.45);
                       transition:transform .15s,box-shadow .15s;display:flex;
                       align-items:center;justify-content:center">🎤</button>
      `;

      document.body.appendChild(wrap);

      this.ui = {
        btn:  document.getElementById('ap-v-btn'),
        hint: document.getElementById('ap-v-hint'),
        tx:   document.getElementById('ap-v-tx'),
      };

      this.ui.btn.addEventListener('click', () => this.toggle());
    },

    _setActive(on) {
      if (!this.ui) return;
      this.active = on;
      this.ui.btn.style.background = on
        ? 'linear-gradient(135deg,#ef4444,#dc2626)'
        : 'linear-gradient(135deg,#3b82f6,#6366f1)';
      this.ui.btn.style.boxShadow = on
        ? '0 6px 20px rgba(239,68,68,0.55)'
        : '0 6px 20px rgba(59,130,246,0.45)';
      this.ui.hint.style.display = on ? 'block' : 'none';
    },

    _showTx(text) {
      if (!this.ui) return;
      this.ui.tx.textContent = text;
      this.ui.tx.style.display = 'block';
      clearTimeout(this._txTimer);
      this._txTimer = setTimeout(() => {
        if (this.ui) this.ui.tx.style.display = 'none';
      }, 3500);
    },

    start() {
      if (this.active) return;
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        vtoast('Speech recognition not supported in this browser', 'warning');
        return;
      }

      this.recognition = new SpeechRec();
      this.recognition.lang           = 'en-IN';
      this.recognition.interimResults = false;
      this.recognition.maxAlternatives= 3;
      this.recognition.continuous     = false;

      this.recognition.onstart = () => {
        this._setActive(true);
        vtoast('🎤 Listening…', 'info');
      };

      this.recognition.onresult = async (event) => {
        const transcript = event.results[0][0].transcript;
        this._showTx('"' + transcript + '"');
        vtts('Got it');
        this._setActive(false);

        try {
          const res = await fetch('/api/voice/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript, portal: ROLE(), lang: 'en' })
          });
          const d = await res.json().catch(() => ({}));
          const cmd = d.cmd || (d.command && d.command.id) || null;
          const arg = d.arg !== undefined ? d.arg : (d.command && d.command.arg) || null;
          if (cmd) {
            await execute(cmd, arg);
          } else {
            vtoast('Not understood', 'warning');
          }
        } catch(e) {
          vtoast('Voice error: ' + e.message, 'error');
        }
      };

      this.recognition.onerror = (e) => {
        this._setActive(false);
        if (e.error !== 'no-speech') vtoast('Voice error: ' + e.error, 'warning');
      };

      this.recognition.onend = () => { this._setActive(false); };
      this.recognition.start();
    },

    stop() {
      if (this.recognition) this.recognition.stop();
      this._setActive(false);
    },

    toggle() {
      this.active ? this.stop() : this.start();
    },
  };

  // ── CSS injection ─────────────────────────────────────────────
  if (!document.getElementById('ap-v-style')) {
    const s = document.createElement('style');
    s.id = 'ap-v-style';
    s.textContent = `
      @keyframes apvp {
        0%,100% { box-shadow: 0 6px 20px rgba(239,68,68,.5); }
        50%      { box-shadow: 0 6px 28px rgba(239,68,68,1), 0 0 0 10px rgba(239,68,68,.12); }
      }
      #ap-v-btn:hover  { transform: scale(1.06) !important; }
      #ap-v-btn:active { transform: scale(0.97) !important; }
    `;
    document.head.appendChild(s);
  }

  // ── boot ──────────────────────────────────────────────────────
  window.VoiceEngine = VoiceEngine;

  // toggleVoice() global shim — keeps any existing HTML buttons working
  window.toggleVoice = function() { VoiceEngine.toggle(); };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => VoiceEngine.init());
  } else {
    VoiceEngine.init();
  }

  // Keyboard shortcut Ctrl+Shift+V
  document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'V') {
      e.preventDefault();
      VoiceEngine.toggle();
    }
  });

})();