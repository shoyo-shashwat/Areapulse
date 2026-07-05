// ══════════════════════════════════════════════════════════
//  voice_agent.js — AreaPulse bilingual voice agent (shared)
//  Works in BOTH portals. Detects which portal via window.VOICE_PORTAL
//  ('gov' or 'ngo'), set in each HTML before this script loads.
//
//  Pipeline:
//   speech -> Web Speech API -> POST /api/voice/interpret
//   -> decision: act | clarify | repeat
//   -> act: call EXISTING functions (showView, submitEscalate, ...)
//   -> mutating actions show an Undo toast + logged in voice history
//
//  Never duplicates portal logic — only triggers existing functions.
// ══════════════════════════════════════════════════════════

(function () {
  const PORTAL = window.VOICE_PORTAL || 'gov';
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  let recognizer = null;
  let listening  = false;
  let currentLang = 'en-IN';       // toggles to hi-IN
  let lastAction  = null;          // for undo
  let undoTimer   = null;

  // ---- speech synthesis (talk back) ----
  function speak(text, lang) {
    try {
      if (!window.speechSynthesis) return;
      const u = new SpeechSynthesisUtterance(text);
      u.lang = lang || currentLang;
      u.rate = 1.05;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    } catch (e) {}
  }

  // ---- overlay UI helpers ----
  function overlay()      { return document.getElementById('voice-overlay'); }
  function setStatus(txt) { const e=document.getElementById('voice-status');     if(e) e.textContent = txt; }
  function setTranscript(txt){ const e=document.getElementById('voice-transcript'); if(e) e.textContent = txt; }
  function showOverlay()  { const o=overlay(); if(o) o.classList.remove('hidden'); }
  function hideOverlay()  { const o=overlay(); if(o) setTimeout(()=>o.classList.add('hidden'), 900); }

  function setMicActive(on) {
    const b = document.getElementById('voice-btn');
    if (b) b.classList.toggle('listening', on);
  }

  // ══════════════════════════════════════════════════════
  //  START / STOP
  // ══════════════════════════════════════════════════════
  window.toggleVoice = function () {
    if (!SR) {
      alert('Voice commands need Chrome or Edge. Please use the buttons on this device.');
      return;
    }
    if (listening) { stopListening(); return; }
    startListening();
  };

  // Optional language toggle (call from a small button if desired)
  window.toggleVoiceLang = function () {
    currentLang = currentLang === 'en-IN' ? 'hi-IN' : 'en-IN';
    speak(currentLang === 'hi-IN' ? 'Hindi mode' : 'English mode', currentLang);
    return currentLang;
  };

  function startListening() {
    recognizer = new SR();
    recognizer.lang            = currentLang;
    recognizer.interimResults  = true;
    recognizer.continuous      = false;
    recognizer.maxAlternatives = 3;

    listening = true;
    setMicActive(true);
    showOverlay();
    setStatus(currentLang === 'hi-IN' ? 'सुन रहा हूँ…' : 'Listening…');
    setTranscript('');

    recognizer.onresult = (event) => {
      let interim = '', finalText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interim += r[0].transcript;
      }
      setTranscript(finalText || interim);
      if (finalText) handleTranscript(finalText.trim());
    };

    recognizer.onerror = (e) => {
      setStatus('Error: ' + (e.error || 'unknown'));
      stopListening();
    };
    recognizer.onend = () => { setMicActive(false); listening = false; };

    try { recognizer.start(); } catch (e) {}
  }

  function stopListening() {
    listening = false;
    setMicActive(false);
    if (recognizer) { try { recognizer.stop(); } catch (e) {} }
    hideOverlay();
  }

  // ══════════════════════════════════════════════════════
  //  INTERPRET (calls backend) then EXECUTE
  // ══════════════════════════════════════════════════════
  async function handleTranscript(text) {
    const lang = currentLang.startsWith('hi') ? 'hi' : 'en';
    setStatus(lang === 'hi' ? 'समझ रहा हूँ…' : 'Understanding…');

    // complex=true only if the phrase looks like it has entities (has "to"/"ko"/a number)
    const complex = /\d|to |ko |team|department|dept|djb|mcd|pwd|bses/i.test(text);

    let data;
    try {
      const r = await fetch('/api/voice/interpret', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portal: PORTAL, transcript: text, lang, complex, context: buildContext() })
      });
      data = await r.json();
    } catch (e) {
      setStatus('Network error'); return;
    }

    if (data.decision === 'repeat') {
      setStatus(lang === 'hi' ? 'समझ नहीं आया — फिर कहें' : "Didn't catch that — please repeat");
      speak(lang === 'hi' ? 'फिर से कहिये' : 'Please repeat', currentLang);
      return;
    }

    if (data.decision === 'clarify') {
      const alts = (data.alternatives || []).filter(Boolean);
      const names = alts.map(a => humanName(a.id)).join(lang === 'hi' ? ' या ' : ' or ');
      setStatus((lang === 'hi' ? 'क्या आपका मतलब: ' : 'Did you mean: ') + names + '?');
      speak((lang === 'hi' ? 'क्या आपका मतलब ' : 'Did you mean ') + names, currentLang);
      hideOverlay();
      return;
    }

    // decision === 'act'
    execute(data.command, data.groq_intent, text, lang);
    hideOverlay();
  }

  // Build a light context payload so Groq can resolve entities
  function buildContext() {
    try {
      if (PORTAL === 'gov' && window._issues) {
        return { issues: window._issues.slice(0, 30).map(i => ({ id: i.id, area: i.area, tag: i.tag })) };
      }
      if (PORTAL === 'ngo' && window._gapIssues) {
        return { issues: window._gapIssues.slice(0, 30).map(i => ({ id: i.id, area: i.area, tag: i.tag })) };
      }
    } catch (e) {}
    return {};
  }

  // ══════════════════════════════════════════════════════
  //  EXECUTE — calls EXISTING portal functions only
  // ══════════════════════════════════════════════════════
  function execute(cmd, groqIntent, transcript, lang) {
    if (!cmd) return;

    // ---- NAVIGATION ----
    if (cmd.type === 'navigate') {
      const btn = document.querySelector(`[data-view="${cmd.view}"]`);
      if (typeof showView === 'function') showView(cmd.view, btn);
      say(lang, `Opening ${humanName(cmd.id)}`, `${humanName(cmd.id)} खोल रहा हूँ`);
      return;
    }

    // ---- QUERY (read a stat aloud) ----
    if (cmd.type === 'query') {
      const val = readMetric(cmd.metric);
      const label = metricLabel(cmd.metric, lang);
      const msg = lang === 'hi' ? `${val} ${label}` : `${val} ${label}`;
      setStatus(msg); speak(msg, currentLang);
      return;
    }

    // ---- FILTER ----
    if (cmd.type === 'filter') {
      applyFilter(cmd.field, cmd.value);
      say(lang, 'Filter applied', 'फ़िल्टर लगा दिया');
      return;
    }

    // ---- SESSION ----
    if (cmd.type === 'session') {
      if (cmd.action === 'logout' && typeof doLogout === 'function') { doLogout(); return; }
      if (cmd.action === 'start_shift' || cmd.action === 'start_program') {
        const btn = document.querySelector('[data-view="dashboard"], [data-view="gap"]');
        const v = PORTAL === 'gov' ? 'dashboard' : 'gap';
        if (typeof showView === 'function') showView(v, btn);
        say(lang, 'Shift started. Showing your priorities.', 'शिफ्ट शुरू। आपकी प्राथमिकताएँ दिखा रहा हूँ।');
        return;
      }
    }

    // ---- ACTION (mutating -> undo) ----
    if (cmd.type === 'action') {
      runAction(cmd, groqIntent, transcript, lang);
      return;
    }
  }

  // ---- action runner with undo pattern ----
  function runAction(cmd, groqIntent, transcript, lang) {
    const activeId = window._voiceActiveIssueId || null;   // set when user is viewing an issue

    // Resolve target issue id from groq hint if present
    let issueId = activeId;
    if (groqIntent && groqIntent.issue_hint) {
      issueId = resolveIssueByHint(groqIntent.issue_hint) || issueId;
    }

    // sensitive (resolve) -> tiny buffer before firing
    if (cmd.sensitive) {
      setStatus(lang === 'hi' ? 'Resolve कर रहा हूँ… रोकने के लिए cancel कहें' : 'Marking resolved… say cancel to stop');
      speak(lang === 'hi' ? 'Resolve कर रहा हूँ' : 'Marking resolved', currentLang);
    }

    switch (cmd.action) {
      case 'escalate':
        if (PORTAL === 'gov' && typeof openEscalateModal === 'function' && issueId) {
          openEscalateModal(issueId);
          if (groqIntent && groqIntent.dept) {
            const sel = document.getElementById('escalate-dept-sel');
            if (sel) sel.value = groqIntent.dept;
          }
          afterAction(lang, 'Escalation ready — review & confirm', 'Escalation तैयार — देखकर confirm करें');
        } else if (PORTAL === 'ngo' && typeof openEscalateModal === 'function' && issueId) {
          openEscalateModal(issueId);
          afterAction(lang, 'Escalation ready', 'Escalation तैयार');
        } else {
          promptSelectIssue(lang);
        }
        break;

      case 'assign':
        if (typeof openAssignModal === 'function' && issueId) {
          openAssignModal(issueId);
          afterAction(lang, 'Assignment ready — pick team & confirm', 'Assignment तैयार — team चुनें');
        } else { promptSelectIssue(lang); }
        break;

      case 'resolve':
        if (typeof openStatusModal === 'function' && issueId) {
          openStatusModal(issueId);
          afterAction(lang, 'Status panel open — confirm resolved', 'Status panel खुला — resolved confirm करें');
        } else { promptSelectIssue(lang); }
        break;

      case 'adopt':
        if (PORTAL === 'ngo' && typeof openAdoptModal === 'function' && issueId) {
          openAdoptModal(issueId);
          afterAction(lang, 'Adoption ready — add plan & confirm', 'Adoption तैयार — plan डालें');
        } else { promptSelectIssue(lang); }
        break;

      case 'update':
        if (typeof openUpdateModal === 'function' && issueId) {
          openUpdateModal(issueId);
          afterAction(lang, 'Update panel open', 'Update panel खुला');
        } else { promptSelectIssue(lang); }
        break;

      case 'impact_story':
        if (typeof generateImpactStory === 'function') {
          const btn = document.querySelector('[data-view="impact"]');
          if (typeof showView === 'function') showView('impact', btn);
          generateImpactStory();
          afterAction(lang, 'Generating impact story', 'Impact story बना रहा हूँ');
        }
        break;
    }
  }

  function afterAction(lang, en, hi) {
    const msg = lang === 'hi' ? hi : en;
    setStatus(msg); speak(msg, currentLang);
  }
  function say(lang, en, hi) { const m = lang==='hi'?hi:en; setStatus(m); speak(m, currentLang); }

  function promptSelectIssue(lang) {
    say(lang, 'Please open an issue first, then say the command.',
             'पहले कोई issue खोलें, फिर command कहें।');
  }

  // ══════════════════════════════════════════════════════
  //  DATA HELPERS (read from existing globals)
  // ══════════════════════════════════════════════════════
  function readMetric(metric) {
    try {
      if (PORTAL === 'gov') {
        const map = {
          sla_breached:   () => document.getElementById('stat-sla-val')?.textContent,
          total_open:     () => document.getElementById('stat-open-val')?.textContent,
          sla_critical:   () => (window._issues||[]).filter(i=>i.sla?.status==='critical').length,
          resolved_today: () => document.getElementById('stat-resolved-val')?.textContent,
        };
        return (map[metric] ? map[metric]() : '—') || '0';
      } else {
        const s = window._impactStats || {};
        return (s[metric] != null ? s[metric] : '0');
      }
    } catch (e) { return '0'; }
  }

  function metricLabel(metric, lang) {
    const en = {
      sla_breached: 'issues have breached SLA', total_open: 'issues are open',
      sla_critical: 'issues are critical', resolved_today: 'resolved today',
      total_adopted: 'issues adopted', resolved: 'issues resolved',
      total_volunteers: 'volunteers mobilised',
    };
    const hi = {
      sla_breached: 'issue SLA breach हुए', total_open: 'issue open हैं',
      sla_critical: 'issue critical हैं', resolved_today: 'आज resolve हुए',
      total_adopted: 'issue adopt हुए', resolved: 'issue resolve हुए',
      total_volunteers: 'volunteers जुड़े',
    };
    return (lang === 'hi' ? hi : en)[metric] || '';
  }

  function applyFilter(field, value) {
    if (PORTAL === 'gov') {
      if (field === 'clear') {
        ['iss-search','iss-filter-sev','iss-filter-status','iss-filter-sla'].forEach(id=>{
          const el=document.getElementById(id); if(el) el.value='';
        });
      } else if (field === 'severity') {
        const el=document.getElementById('iss-filter-sev'); if(el) el.value=value;
      } else if (field === 'sla') {
        const el=document.getElementById('iss-filter-sla'); if(el) el.value=value;
      }
      const btn = document.querySelector('[data-view="issues"]');
      if (typeof showView === 'function') showView('issues', btn);
      if (typeof filterIssues === 'function') filterIssues();
    }
  }

  function resolveIssueByHint(hint) {
    const pool = PORTAL === 'gov' ? (window._issues||[]) : (window._gapIssues||[]);
    hint = (hint||'').toLowerCase();
    // direct id
    const byId = pool.find(i => String(i.id) === hint.replace(/\D/g,''));
    if (byId) return byId.id;
    // area/tag keyword
    const byText = pool.find(i =>
      hint.includes((i.area||'').toLowerCase()) || hint.includes((i.tag||'').toLowerCase()));
    return byText ? byText.id : null;
  }

  // ---- human-readable command names ----
  const NAMES = {
    nav_dashboard:'Dashboard', nav_issues:'Issues Board', nav_dispatch:'Field Dispatch',
    nav_alerts:'Predictive Alerts', nav_analytics:'Analytics',
    nav_gap:'Gap Map', nav_adoptions:'My Adoptions', nav_drives:'Drive Builder', nav_impact:'Impact',
  };
  function humanName(id){ return NAMES[id] || (id||'').replace(/_/g,' '); }

})();