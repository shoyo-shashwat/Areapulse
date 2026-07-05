// ══════════════════════════════════════════════════════════
//  ngo_features.js — Volunteer Management + Donor PDF download
//  Isolated add-on. Wraps existing showView(), calls new endpoints.
// ══════════════════════════════════════════════════════════

(function () {
  let _logVolId = null;
  const escq = (s) => s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : '';

  // wrap existing showView
  const _orig = window.showView;
  window.showView = function (id, btn) {
    if (typeof _orig === 'function') _orig(id, btn);
    if (id === 'volunteers') loadVolunteers();
  };

  // ══════════════════════════════════════════════════════
  //  VOLUNTEERS
  // ══════════════════════════════════════════════════════
  async function loadVolunteers() {
    const listEl = document.getElementById('volunteers-list');
    const lbEl   = document.getElementById('volunteer-leaderboard');
    try {
      const [vR, lR] = await Promise.all([
        fetch('/api/ngo/volunteers'),
        fetch('/api/ngo/volunteers/leaderboard')
      ]);
      const vols = (await vR.json()).volunteers || [];
      const board = (await lR.json()).leaderboard || [];

      if (!vols.length) {
        listEl.innerHTML = '<div class="loading-state">No volunteers yet — click "Add Volunteer" to start.</div>';
      } else {
        listEl.innerHTML = vols.map(v => `
          <div class="vol-card">
            <div class="vol-avatar">${escq((v.name||'?').split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase())}</div>
            <div class="vol-body">
              <div class="vol-name">${escq(v.name)}</div>
              <div class="vol-meta">${escq(v.skills||'—')} · ${v.total_hours||0}h · ${v.drives_count||0} drives</div>
            </div>
            <button class="ac-btn ac-btn-update" onclick="openLogHours('${escq(v.id)}','${escq(v.name)}')">Log Hours</button>
          </div>
        `).join('');
      }

      if (!board.length) {
        lbEl.innerHTML = '<div class="loading-state">No hours logged yet.</div>';
      } else {
        const medals = ['🥇','🥈','🥉'];
        lbEl.innerHTML = board.map(b => `
          <div class="lb-row">
            <div class="lb-rank">${medals[b.rank-1] || b.rank}</div>
            <div class="lb-name">${escq(b.name)}</div>
            <div class="lb-hours">${b.total_hours}h</div>
          </div>
        `).join('');
      }
    } catch(e) {
      if (listEl) listEl.innerHTML = '<div class="loading-state">Error loading.</div>';
    }
  }

  window.openAddVolunteer = function () {
    ['vol-name','vol-phone','vol-skills'].forEach(id=>{const e=document.getElementById(id); if(e) e.value='';});
    if (typeof openModal === 'function') openModal('addvol');
  };

  window.submitAddVolunteer = async function () {
    const name = document.getElementById('vol-name').value.trim();
    if (!name) { if(typeof showToast==='function') showToast('Please enter a name','danger'); return; }
    await fetch('/api/ngo/volunteers/add', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        name, phone:document.getElementById('vol-phone').value,
        skills:document.getElementById('vol-skills').value
      })
    });
    if (typeof closeModal==='function') closeModal('addvol');
    if (typeof showToast==='function') showToast('Volunteer added ✓');
    loadVolunteers();
  };

  window.openLogHours = function (vid, name) {
    _logVolId = vid;
    const info = document.getElementById('loghours-vol-info');
    if (info) info.innerHTML = `Logging hours for <strong>${escq(name)}</strong>`;
    document.getElementById('loghours-task').value = '';
    document.getElementById('loghours-hours').value = '2';
    if (typeof openModal === 'function') openModal('loghours');
  };

  window.submitLogHours = async function () {
    const task  = document.getElementById('loghours-task').value.trim();
    const hours = parseFloat(document.getElementById('loghours-hours').value) || 0;
    await fetch('/api/ngo/volunteers/checkout', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({volunteer_id:_logVolId, drive_id:'manual', task, hours})
    });
    if (typeof closeModal==='function') closeModal('loghours');
    if (typeof showToast==='function') showToast(`${hours}h logged ✓`);
    loadVolunteers();
  };

  // ══════════════════════════════════════════════════════
  //  DONOR PDF DOWNLOAD
  // ══════════════════════════════════════════════════════
  window.downloadDonorPDF = async function () {
    if (typeof showToast==='function') showToast('Generating donor PDF…');
    const stats = window._impactStats || {};
    const story = (document.getElementById('impact-story-text')||{}).textContent || '';
    // pull adoptions if available
    let adoptions = [];
    try {
      const r = await fetch('/api/ngo/my-adoptions'); const d = await r.json();
      adoptions = d.adoptions || [];
    } catch(e){}

    try {
      const r = await fetch('/api/ngo/donor-report', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
          story: story.startsWith('Click') ? '' : story,
          stats, adoptions,
          budget: { program: 0, overhead: 0 }   // NGO can edit later; 0 hides the section
        })
      });
      const d = await r.json();
      if (d.url) {
        window.open(d.url, '_blank');
        if (typeof showToast==='function') showToast('Donor PDF ready ✓','success');
      } else {
        if (typeof showToast==='function') showToast(d.error||'Failed to generate','danger');
      }
    } catch(e) {
      if (typeof showToast==='function') showToast('Failed to generate PDF','danger');
    }
  };
})();