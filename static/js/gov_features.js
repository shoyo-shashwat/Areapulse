// ══════════════════════════════════════════════════════════
//  gov_features.js — frontend for Verify Closures + Accountability
//  Isolated add-on. Hooks into existing showView() via a wrapper,
//  calls the new /api/gov/* endpoints. Does not modify gov_app.js logic.
// ══════════════════════════════════════════════════════════

(function () {
  let _verifyIssueId = null;
  let _gps = null;

  const TAG_ICONS = {
    pothole:'🕳',garbage:'🗑',water:'💧',sewage:'🚧',electricity:'⚡',
    streetlight:'💡',traffic:'🚦',tree:'🌳',noise:'📢',other:'⚠'
  };
  const escq = (s) => s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : '';

  // ---- wrap existing showView so our views load their data ----
  const _origShowView = window.showView;
  window.showView = function (id, btn) {
    if (typeof _origShowView === 'function') _origShowView(id, btn);
    // titles for new views (origShowView may not know them)
    const T = {
      verify:        ['Verify Closures', 'Proof + confirmation before an issue closes'],
      accountability:['Accountability', 'Auto-escalation & tamper-proof audit trail'],
    };
    if (T[id]) {
      const t=document.getElementById('topbar-title'); if(t) t.textContent=T[id][0];
      const s=document.getElementById('topbar-sub');   if(s) s.textContent=T[id][1];
    }
    if (id === 'verify')         loadPendingVerifications();
    if (id === 'accountability') { loadAutoEscalations(); loadAuditTrail(); }
  };

  // ══════════════════════════════════════════════════════
  //  VERIFY CLOSURES
  // ══════════════════════════════════════════════════════
  async function loadPendingVerifications() {
    const el = document.getElementById('verify-pending-list');
    if (!el) return;
    try {
      const r = await fetch('/api/gov/resolution/pending');
      const d = await r.json();
      const items = d.pending || [];
      // badge
      const badge = document.getElementById('sb-badge-verify');
      if (badge) { badge.textContent = items.length || ''; badge.style.display = items.length ? 'inline-flex' : 'none'; }

      if (!items.length) {
        el.innerHTML = '<div class="empty-state">No resolutions awaiting verification.<br>Submit proof from any issue via the "Verify" button on the Issues Board.</div>';
        return;
      }
      el.innerHTML = items.map(rec => `
        <div class="verify-row">
          <div class="verify-row-body">
            <div class="verify-row-title">Issue #${escq(rec.issue_id)}</div>
            <div class="verify-row-meta">📍 ${rec.lat}, ${rec.lng} · by ${escq(rec.submitted_by)} · ${escq(rec.note||'')}</div>
          </div>
          <div class="verify-row-actions">
            <button class="act-btn act-btn-status" onclick="verifyResolution('${escq(rec.issue_id)}','supervisor',true)">✓ Confirm Fixed</button>
            <button class="act-btn act-btn-escalate" onclick="verifyResolution('${escq(rec.issue_id)}','supervisor',false)">✕ Reject</button>
          </div>
        </div>
      `).join('');
    } catch (e) { el.innerHTML = '<div class="loading-row">Error loading.</div>'; }
  }

  window.verifyResolution = async function (issueId, verifierType, approved) {
    await fetch('/api/gov/resolution/verify', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({issue_id:issueId, verifier_type:verifierType, verifier_id:'officer', approved})
    });
    if (typeof showToast === 'function')
      showToast(approved ? `Issue #${issueId} verified & closed ✓` : `Issue #${issueId} rejected — reopened`, approved?'success':'danger');
    loadPendingVerifications();
    if (typeof loadIssues === 'function') loadIssues();
  };

  // ---- open the proof-submission modal (called from Issues Board) ----
  window.openVerifyModal = function (issueId) {
    _verifyIssueId = issueId; _gps = null;
    const iss = (window._issues||[]).find(i => String(i.id) === String(issueId));
    const info = document.getElementById('verify-issue-info');
    if (info && iss) info.innerHTML = `<strong>#${escq(String(issueId))}</strong> · ${TAG_ICONS[iss.tag]||'⚠'} ${escq(iss.tag)} · ${escq(iss.area)}<br>${escq((iss.description||'').slice(0,80))}`;
    const ph=document.getElementById('verify-photo'); if(ph) ph.value='';
    const gs=document.getElementById('verify-gps-status'); if(gs){gs.textContent='Not captured';gs.className='verify-gps-status';}
    const nt=document.getElementById('verify-note'); if(nt) nt.value='';
    if (typeof openModal === 'function') openModal('verify');
  };

  window.captureGPS = function () {
    const status = document.getElementById('verify-gps-status');
    if (!navigator.geolocation) { if(status){status.textContent='GPS not supported';} return; }
    if (status) status.textContent='Capturing…';
    navigator.geolocation.getCurrentPosition(
      (pos) => { _gps = {lat:+pos.coords.latitude.toFixed(6), lng:+pos.coords.longitude.toFixed(6)};
        if(status){status.textContent=`✓ ${_gps.lat}, ${_gps.lng}`; status.className='verify-gps-status ok';} },
      ()   => { if(status){status.textContent='Permission denied — using issue location'; }
        const iss=(window._issues||[]).find(i=>String(i.id)===String(_verifyIssueId));
        if(iss){ _gps={lat:iss.lat,lng:iss.lng}; if(status){status.textContent=`✓ ${iss.lat}, ${iss.lng} (issue loc)`; status.className='verify-gps-status ok';} } },
      {timeout:8000}
    );
  };

  window.submitResolutionProof = async function () {
    const fileInput = document.getElementById('verify-photo');
    const note = document.getElementById('verify-note').value;
    const hasPhoto = fileInput && fileInput.files && fileInput.files.length;
    if (!hasPhoto) { if(typeof showToast==='function') showToast('Please add an after photo', 'danger'); return; }
    if (!_gps)     { if(typeof showToast==='function') showToast('Please capture GPS', 'danger'); return; }

    // photo reference (filename marker — real upload would go to storage)
    const photoRef = 'photo:' + fileInput.files[0].name;
    const r = await fetch('/api/gov/resolution/submit', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({issue_id:_verifyIssueId, after_photo:photoRef, lat:_gps.lat, lng:_gps.lng, note})
    });
    const d = await r.json();
    if (d.error) { if(typeof showToast==='function') showToast(d.error+' ('+(d.missing||[]).join(', ')+')','danger'); return; }
    if (typeof closeModal==='function') closeModal('verify');
    if (typeof showToast==='function') showToast(`Proof submitted for #${_verifyIssueId} — awaiting verification`,'success');
  };

  // ══════════════════════════════════════════════════════
  //  ACCOUNTABILITY — Auto-escalation + Audit
  // ══════════════════════════════════════════════════════
  async function loadAutoEscalations() {
    const el = document.getElementById('auto-esc-summary');
    if (!el) return;
    try {
      const r = await fetch('/api/gov/auto-escalations');
      const d = await r.json();
      const s = d.summary || {};
      el.innerHTML = `
        <div class="auto-esc-tier">
          <div class="aet-dot t1"></div>
          <div class="aet-body"><div class="aet-name">Supervisor (24h+)</div><div class="aet-sub">Overdue past first tier</div></div>
          <div class="aet-count">${s.supervisor||0}</div>
        </div>
        <div class="auto-esc-tier">
          <div class="aet-dot t2"></div>
          <div class="aet-body"><div class="aet-name">Assistant Commissioner (48h+)</div><div class="aet-sub">Escalated up second tier</div></div>
          <div class="aet-count">${s.assistant_commissioner||0}</div>
        </div>
        <div class="auto-esc-tier">
          <div class="aet-dot t3"></div>
          <div class="aet-body"><div class="aet-name">Commissioner (72h+)</div><div class="aet-sub">Flagged to public dashboard</div></div>
          <div class="aet-count">${s.commissioner||0}</div>
        </div>
        <div class="auto-esc-note">${(s.public_flagged||[]).length} issue(s) now publicly flagged for transparency.</div>
      `;
    } catch(e){ el.innerHTML='<div class="loading-row">Error loading.</div>'; }
  }

  async function loadAuditTrail() {
    const el = document.getElementById('audit-list');
    if (!el) return;
    try {
      const [logR, verR] = await Promise.all([ fetch('/api/gov/audit'), fetch('/api/gov/audit/verify') ]);
      const log = await logR.json();
      const ver = await verR.json();
      const badge = document.getElementById('audit-integrity');
      if (badge) {
        badge.textContent = ver.intact ? '🔒 intact' : '⚠ tampered';
        badge.className = 'audit-badge ' + (ver.intact ? 'ok' : 'bad');
      }
      const entries = log.entries || [];
      if (!entries.length) { el.innerHTML='<div class="empty-state">No actions logged yet.</div>'; return; }
      el.innerHTML = entries.slice(0,30).map(e => `
        <div class="audit-row">
          <div class="audit-seq">#${e.seq}</div>
          <div class="audit-body">
            <div class="audit-action">${escq(e.action.replace(/_/g,' '))}${e.issue_id?` · issue #${escq(e.issue_id)}`:''}</div>
            <div class="audit-detail">${escq(e.detail||'')}</div>
            <div class="audit-meta">${escq(e.actor)} · ${new Date(e.ts*1000).toLocaleString('en-IN')}</div>
          </div>
        </div>
      `).join('');
    } catch(e){ el.innerHTML='<div class="loading-row">Error loading.</div>'; }
  }

  // refresh pending-verify badge on load
  window.addEventListener('DOMContentLoaded', () => { setTimeout(loadPendingVerifications, 1500); });
})();