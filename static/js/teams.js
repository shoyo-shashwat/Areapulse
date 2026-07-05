/* Teams — shared logic for gov + ngo portals */
'use strict';

let _teams = [];
let _activeTeam = null;
let _chatPoll   = null;
let _me         = null;

// ── boot ──────────────────────────────────────────────────────
async function loadTeams() {
  try {
    const d = await apiFetch('/api/teams/mine');
    _teams = d.teams || [];
    _me    = d.me;
    renderTeamList();
    if (!_activeTeam && _teams.length) openTeam(_teams[0].id);
  } catch(e) {
    el('teams-list').innerHTML = errState('Failed to load teams: ' + e.message);
  }
}

// ── helpers ───────────────────────────────────────────────────
async function apiFetch(url, body) {
  const r = await fetch(url, body
    ? { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }
    : { method:'GET' });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.status);
  }
  return r.json();
}

function el(id) { return document.getElementById(id); }
function esc(s) { return String(s||'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso), now = new Date();
  if (d.toDateString() === now.toDateString())
    return d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  return d.toLocaleDateString([], {month:'short',day:'numeric'}) + ' ' +
         d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}
function errState(msg) {
  return `<div style="padding:24px;text-align:center;color:var(--ink-3)">⚠ ${esc(msg)}</div>`;
}
function emptyState(icon, title, sub) {
  return `<div style="padding:40px 16px;text-align:center">
    <div style="font-size:32px">${icon}</div>
    <div style="font-weight:700;margin:10px 0 4px">${esc(title)}</div>
    <div style="font-size:13px;color:var(--ink-3)">${esc(sub)}</div>
  </div>`;
}
function toast(msg, kind='success') {
  if (window.Toast && window.Toast[kind]) window.Toast[kind](msg);
}

// ── list panel ────────────────────────────────────────────────
function renderTeamList() {
  const list = el('teams-list');
  if (!_teams.length) {
    list.innerHTML = emptyState('📭','No teams yet','Create one or enter an invite code to join.');
    return;
  }
  list.innerHTML = _teams.map(t => `
    <div onclick="openTeam('${t.id}')"
         style="padding:12px;border-radius:8px;cursor:pointer;margin-bottom:4px;
                background:${_activeTeam===t.id ? 'var(--accent-soft)' : 'transparent'};
                border:1px solid ${_activeTeam===t.id ? 'var(--accent)' : 'transparent'};
                transition:background .1s">
      <div style="font-weight:600;font-size:14px;color:var(--ink)">${esc(t.name)}</div>
      <div style="font-size:12px;color:var(--ink-3);margin-top:2px">
        ${t.members.length} member${t.members.length!==1?'s':''} &middot;
        <span style="font-family:monospace;letter-spacing:1px">${t.code}</span>
      </div>
    </div>
  `).join('');
}

// ── team detail panel ─────────────────────────────────────────
async function openTeam(teamId) {
  _activeTeam = teamId;
  renderTeamList();
  if (_chatPoll) { clearInterval(_chatPoll); _chatPoll = null; }

  const panel = el('team-panel');
  panel.innerHTML = emptyState('⏳','Loading…','');

  try {
    const d = await apiFetch('/api/teams/' + teamId);
    if (d.error) { panel.innerHTML = errState(d.error); return; }
    _me = d.me;
    renderTeamPanel(d.team, d.messages);
    _chatPoll = setInterval(() => pollMessages(teamId), 4000);
  } catch(e) {
    panel.innerHTML = errState(e.message);
  }
}

function renderTeamPanel(team, messages) {
  const panel = el('team-panel');
  const members = Object.entries(team.member_details || {}).map(([u,d])=>({username:u,...d}));

  panel.innerHTML = `
    <!-- header -->
    <div style="padding:14px 18px;border-bottom:1px solid var(--border);
                display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
      <div style="min-width:0">
        <div style="font-weight:700;font-size:15px;color:var(--ink)">${esc(team.name)}</div>
        <div style="font-size:12px;color:var(--ink-3);margin-top:1px">${esc(team.purpose||'No purpose set')}</div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
        <span title="Click to copy invite code"
              onclick="copyCode('${team.code}')"
              style="background:var(--bg-subtle);padding:5px 11px;border-radius:6px;
                     font-family:monospace;font-weight:700;letter-spacing:1px;font-size:13px;
                     cursor:pointer;border:1px solid var(--border)">${team.code} 📋</span>
        <button onclick="leaveTeam('${team.id}')"
                style="padding:6px 12px;border-radius:6px;border:1px solid var(--border);
                       background:transparent;color:var(--ink-3);font-size:12px;cursor:pointer">
          Leave
        </button>
      </div>
    </div>

    <!-- body: chat + members -->
    <div style="display:grid;grid-template-columns:1fr 190px;min-height:0;height:calc(100% - 56px)">

      <!-- chat -->
      <div style="display:flex;flex-direction:column;border-right:1px solid var(--border)">
        <div id="chat-messages"
             style="flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;
                    gap:8px;min-height:380px;max-height:480px"></div>
        <div style="padding:10px 12px;border-top:1px solid var(--border);display:flex;gap:8px">
          <input id="chat-input" placeholder="Type a message… (Enter to send)"
                 onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg('${team.id}')}"
                 style="flex:1;padding:9px 12px;border:1px solid var(--border);border-radius:8px;
                        background:var(--bg-surface);color:var(--ink);font-size:13px;outline:none">
          <button onclick="sendMsg('${team.id}')"
                  class="btn btn-primary btn-sm">Send</button>
        </div>
      </div>

      <!-- members -->
      <div style="padding:12px;overflow-y:auto">
        <div style="font-size:11px;color:var(--ink-3);font-weight:600;letter-spacing:.5px;margin-bottom:10px">
          MEMBERS (${members.length})
        </div>
        ${members.map(m=>`
          <div style="display:flex;align-items:center;gap:8px;padding:5px 0">
            <div style="width:28px;height:28px;border-radius:50%;background:var(--accent);
                        color:white;display:flex;align-items:center;justify-content:center;
                        font-size:12px;font-weight:600;flex-shrink:0">
              ${(m.name||m.username)[0].toUpperCase()}
            </div>
            <div style="min-width:0;flex:1">
              <div style="font-size:13px;font-weight:600;color:var(--ink);
                          overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                ${esc(m.name||m.username)}${m.username===_me?' <span style="color:var(--ink-3);font-weight:400">(you)</span>':''}
              </div>
              <div style="font-size:11px;color:var(--ink-3)">${m.role}${m.dept?' · '+esc(m.dept):''}</div>
            </div>
          </div>
        `).join('')}
      </div>

    </div>
  `;
  renderMessages(messages);
}

// ── messages ──────────────────────────────────────────────────
function renderMessages(messages) {
  const box = el('chat-messages');
  if (!box) return;
  if (!messages || !messages.length) {
    box.innerHTML = '<div style="text-align:center;color:var(--ink-3);font-size:13px;padding:32px 0">No messages yet — say hi 👋</div>';
    return;
  }
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
  box.innerHTML = messages.map(m => {
    if (m.system) return `<div style="text-align:center;font-size:12px;color:var(--ink-3);padding:3px 0">${esc(m.text)}</div>`;
    const isMe = m.author === _me;
    return `
      <div style="display:flex;flex-direction:column;align-items:${isMe?'flex-end':'flex-start'}">
        <div style="font-size:11px;color:var(--ink-3);margin-bottom:2px">${esc(m.author_name||m.author)} · ${fmtTime(m.ts)}</div>
        <div style="max-width:72%;padding:8px 12px;border-radius:12px;word-wrap:break-word;white-space:pre-wrap;
                    background:${isMe?'var(--accent)':'var(--bg-subtle)'};
                    color:${isMe?'white':'var(--ink)'}">
          ${esc(m.text)}
        </div>
      </div>`;
  }).join('');
  if (atBottom) box.scrollTop = box.scrollHeight;
}

async function pollMessages(teamId) {
  if (_activeTeam !== teamId) return;
  try {
    const d = await apiFetch('/api/teams/' + teamId);
    if (d.messages) renderMessages(d.messages);
  } catch(e) {}
}

async function sendMsg(teamId) {
  const inp = el('chat-input');
  const text = (inp.value||'').trim();
  if (!text) return;
  inp.value = '';
  try {
    await apiFetch('/api/teams/' + teamId + '/message', { text });
    pollMessages(teamId);
  } catch(e) { toast('Failed to send: '+e.message, 'error'); }
}

// ── create / join ─────────────────────────────────────────────
function openCreate() {
  const m = el('create-modal');
  if (m) { m.style.display = 'flex'; setTimeout(()=>el('c-name')&&el('c-name').focus(),50); }
}
function openJoin() {
  const m = el('join-modal');
  if (m) { m.style.display = 'flex'; setTimeout(()=>el('j-code')&&el('j-code').focus(),50); }
}
function closeModals() {
  ['create-modal','join-modal'].forEach(id => {
    const m = el(id); if (m) m.style.display = 'none';
  });
}

async function submitCreate() {
  const name    = (el('c-name')?.value||'').trim();
  const purpose = (el('c-purpose')?.value||'').trim();
  if (!name) { toast('Team name required','warning'); return; }
  try {
    const d = await apiFetch('/api/teams/create', { name, purpose });
    if (d.ok) {
      closeModals();
      if (el('c-name'))    el('c-name').value    = '';
      if (el('c-purpose')) el('c-purpose').value = '';
      toast('Team created! Code: ' + d.team.code);
      _activeTeam = d.team.id;
      loadTeams();
    } else { toast(d.error||'Failed','error'); }
  } catch(e) { toast(e.message,'error'); }
}

async function submitJoin() {
  const code = (el('j-code')?.value||'').trim().toUpperCase();
  if (!code) { toast('Enter a code','warning'); return; }
  try {
    const d = await apiFetch('/api/teams/join', { code });
    if (d.ok) {
      closeModals();
      if (el('j-code')) el('j-code').value = '';
      toast(d.already_member ? 'Already a member' : 'Joined team!');
      _activeTeam = d.team.id;
      loadTeams();
    } else { toast(d.error||'Invalid code','error'); }
  } catch(e) { toast(e.message,'error'); }
}

async function leaveTeam(teamId) {
  if (!confirm('Leave this team?')) return;
  try {
    await apiFetch('/api/teams/'+teamId+'/leave', {});
    _activeTeam = null;
    if (_chatPoll) { clearInterval(_chatPoll); _chatPoll = null; }
    el('team-panel').innerHTML = emptyState('👋','Left team','Select another team or create one.');
    loadTeams();
  } catch(e) { toast(e.message,'error'); }
}

function copyCode(code) {
  navigator.clipboard.writeText(code)
    .then(()=>toast('Code copied — share it: '+code))
    .catch(()=>toast('Code: '+code));
}

// ── init ──────────────────────────────────────────────────────
if (document.readyState==='loading') document.addEventListener('DOMContentLoaded', loadTeams);
else loadTeams();