/* ═══════════════════════════════════════════════════════════════
   AREAPULSE VOICE v3
   Click 🎤 (bottom-right) or Ctrl+Shift+V to activate.
   Speaks to Groq via Flask /api/voice/parse — key never in browser.
   Works in English, Hindi, Hinglish.
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
        // Both /gov/issue/<id> and /ngo/issue/<id> exist
        nav(`/${role}/issue/${arg}`, 'Issue AP-' + arg); break;
      // status changes
      case 'issue_start':
      case 'issue_acknowledge':
      case 'issue_resolve':
        // Resolve triggers the proof popup — never direct API
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
      case 'issue_escalate': {
        if (!arg) { vtoast('Which issue number?', 'warning'); break; }
        try {
          await apiPost('/gov/api/escalate', { id: arg });
          vtoast('↑ AP-' + arg + ' escalated', 'success');
          vtts('Escalated ' + arg);
          if (/\/(queue|progress|sla)/.test(location.pathname)) setTimeout(() => location.reload(), 600);
        } catch(e) { vtoast('Failed: ' + e.message, 'error'); }
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
      case 'ngo_commit': {
        if (!arg) { vtoast('Which issue number?', 'warning'); break; }
        try {
          await apiPost('/ngo/commit', { issue_id: arg, volunteers: 2, eta: '48h', note: 'Committed via voice' });
          vtoast('✓ Committed to AP-' + arg, 'success');
          vtts('Committed to issue ' + arg);
          if (/\/(opportunities|projects)/.test(location.pathname))
            setTimeout(() => location.reload(), 600);
        } catch(e) { vtoast('Failed: ' + e.message, 'error'); }
        break;
      }

      // ── NGO mark done (alias for resolve with modal) ──────────
      case 'ngo_mark_done': {
        if (!arg) { vtoast('Which issue number?', 'warning'); vtts('Which issue?'); break; }
        if (window.showResolveModal) {
          window.showResolveModal(arg);
          vtts('Opening done form for issue ' + arg);
        } else {
          vtoast('Open the projects page first', 'warning');
        }
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
      'Filters: "bijli issues dikhao" · "pani issues" · "naali issues" · "show escalated"',
      'Bulk: "start all" · "resolve all" · "select all"',
      'NGO: "gap map" · "commit to 42" · "impact dikhao" · "volunteers"',
      'Other: "download PDF" · "export CSV" · "mark all read" · "refresh" · "logout"',
    ];
    vtoast(h.join('\n'), 'info');
    console.log('[voice help]\n' + h.join('\n'));
  }

  // ── AI intent via Flask+Groq ─────────────────────────────────
  async function parseIntent(transcript) {
    try {
      const r = await fetch('/api/voice/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript, portal: ROLE() })
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return await r.json();
    } catch(e) {
      console.warn('[voice] parse failed:', e.message);
      return localFallback(transcript);
    }
  }

  // Delhi area names for local fallback
  const DELHI_AREAS = [
    'chandni chowk','rohini','dwarka','saket','lajpat nagar','karol bagh',
    'connaught place','cp','janakpuri','pitampura','shahdara','preet vihar',
    'mayur vihar','vasant kunj','malviya nagar','hauz khas','green park',
    'south extension','greater kailash','gk','nehru place','okhla',
    'faridabad','gurgaon','noida','rajouri garden','patel nagar','kirti nagar',
    'moti nagar','punjabi bagh','ashok vihar','model town','civil lines',
    'north campus','south campus','paharganj','new delhi','old delhi',
  ];

  function localFallback(t) {
    t = t.toLowerCase();
    const m = t.match(/(\d{2,5})/);
    const id = m ? parseInt(m[1]) : null;

    // Check for Delhi area names first
    for (const area of DELHI_AREAS) {
      if (t.includes(area)) {
        // Proper-case the area name
        const proper = area.split(' ').map(w=>w[0].toUpperCase()+w.slice(1)).join(' ');
        return { cmd:'filter_area', arg: proper };
      }
    }
    if (/dashboard|ghar/.test(t))            return { cmd:'nav_dashboard',   arg:null };
    if (/queue|issues list/.test(t))         return { cmd:'nav_queue',       arg:null };
    if (/progress/.test(t))                  return { cmd:'nav_progress',    arg:null };
    if (/naksha|\bmap\b/.test(t))            return { cmd:'nav_map',         arg:null };
    if (/sla|deadline/.test(t))              return { cmd:'nav_sla',         arg:null };
    if (/analytic|graph/.test(t))            return { cmd:'nav_analytics',   arg:null };
    if (/team/.test(t))                      return { cmd:'nav_teams',       arg:null };
    if (/notif|suchna/.test(t))              return { cmd:'nav_notifications',arg:null };
    if (/bijli|electricity/.test(t))         return { cmd:'filter_tag',      arg:'electricity' };
    if (/pani|water|jal/.test(t))            return { cmd:'filter_tag',      arg:'water' };
    if (/naali|sewage|drain/.test(t))        return { cmd:'filter_tag',      arg:'sewage' };
    if (/sadak|pothole|road/.test(t))        return { cmd:'filter_tag',      arg:'pothole' };
    if (/kachra|garbage|waste/.test(t))      return { cmd:'filter_tag',      arg:'garbage' };
    if (/escalated|urgent/.test(t) && !id)   return { cmd:'filter_status',   arg:'escalated' };
    if (/resolved|done/.test(t) && !id)      return { cmd:'filter_status',   arg:'resolved' };
    if (/start|shuru/.test(t) && id)         return { cmd:'issue_start',     arg:id };
    if (/resolve|khatam/.test(t) && id)      return { cmd:'issue_resolve',   arg:id };
    if (/escalate/.test(t) && id)            return { cmd:'issue_escalate',  arg:id };
    if (/de.esc|deesc/.test(t) && id)        return { cmd:'issue_deescalate',arg:id };
    if (/dikhao|kholo|open|show/.test(t) && id) return { cmd:'open_issue',  arg:id };
    if (/refresh|reload/.test(t))            return { cmd:'page_refresh',    arg:null };
    if (/logout|nikal/.test(t))              return { cmd:'logout',          arg:null };
    if (/help/.test(t))                      return { cmd:'help',            arg:null };
    return { cmd:'unknown', arg:null };
  }

  // ── speech engine ─────────────────────────────────────────────
  const VoiceEngine = {
    rec: null,
    on: false,
    supported: false,
    ui: null,
    _timer: null,

    init() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { console.warn('[voice] not supported — use Chrome or Edge'); return; }
      this.supported = true;

      this.rec = new SR();
      this.rec.continuous     = false;
      this.rec.interimResults = false;
      this.rec.lang           = 'en-IN';
      this.rec.maxAlternatives = 5;

      this.rec.onresult = (ev) => {
        const parts = [];
        for (let i = ev.resultIndex; i < ev.results.length; i++)
          for (let j = 0; j < ev.results[i].length; j++)
            parts.push(ev.results[i][j].transcript);
        if (!parts.length) return;
        const text = parts[0].trim();
        this._show('"' + text + '" — thinking…');
        parseIntent(text).then(intent => {
          console.log('[voice] intent:', intent);
          this._show('"' + text + '"');
          execute(intent.cmd, intent.arg);
        });
      };

      this.rec.onerror = (ev) => {
        if (ev.error === 'network')
          vtoast('Voice needs internet + localhost or https://', 'error');
        else if (ev.error === 'not-allowed')
          vtoast('Mic blocked — allow mic in browser settings', 'error');
        else if (ev.error !== 'no-speech' && ev.error !== 'aborted')
          vtoast('Mic error: ' + ev.error, 'warning');
        this._setState(false);
      };
      this.rec.onend = () => this._setState(false);

      this._buildUI();
      document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && (e.key === 'V' || e.key === 'v')) {
          e.preventDefault(); this.toggle();
        }
      });
    },

    toggle() {
      if (!this.supported) { vtoast('Use Chrome or Edge for voice', 'warning'); return; }
      this.on ? this.stop() : this.start();
    },

    start() {
      if (!this.rec || this.on) return;
      try {
        this.rec.start();
        this._setState(true);
        this._timer = setTimeout(() => this.stop(), 7000);
      } catch(e) {
        if (e.name === 'InvalidStateError') {
          try { this.rec.abort(); } catch(_) {}
          setTimeout(() => this.start(), 200);
        } else {
          vtoast('Mic error: ' + e.message, 'error');
        }
      }
    },

    stop() {
      clearTimeout(this._timer);
      try { this.rec.stop(); } catch(_) {}
      this._setState(false);
    },

    _setState(on) {
      this.on = on;
      if (!this.ui) return;
      if (on) {
        this.ui.btn.style.background = 'linear-gradient(135deg,#ef4444,#dc2626)';
        this.ui.btn.style.animation  = 'apvp 1.4s infinite';
        this.ui.btn.textContent      = '🔴';
        this.ui.hint.style.display   = 'block';
      } else {
        this.ui.btn.style.background = 'linear-gradient(135deg,#3b82f6,#6366f1)';
        this.ui.btn.style.animation  = '';
        this.ui.btn.textContent      = '🎤';
        this.ui.hint.style.display   = 'none';
        setTimeout(() => { if (this.ui) this.ui.tx.style.display = 'none'; }, 3000);
      }
    },

    _show(text) {
      if (!this.ui) return;
      this.ui.tx.textContent  = text;
      this.ui.tx.style.display = 'block';
    },

    _buildUI() {
      // Remove any old voice elements left over from previous versions
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
  };

  // ── styles ───────────────────────────────────────────────────
  if (!document.getElementById('ap-v-style')) {
    const s = document.createElement('style');
    s.id = 'ap-v-style';
    s.textContent = `
      @keyframes apvp {
        0%,100% { box-shadow: 0 6px 20px rgba(239,68,68,.5); }
        50%      { box-shadow: 0 6px 28px rgba(239,68,68,1), 0 0 0 10px rgba(239,68,68,.12); }
      }
      #ap-v-btn:hover  { transform: scale(1.06); }
      #ap-v-btn:active { transform: scale(0.97); }
    `;
    document.head.appendChild(s);
  }

  // ── boot ─────────────────────────────────────────────────────
  window.VoiceEngine = VoiceEngine;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => VoiceEngine.init());
  else VoiceEngine.init();

})();