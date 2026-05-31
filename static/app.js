// ══════════════════════════════════════════════════════════
//  AreaPulse AR Camera — app.js
// ══════════════════════════════════════════════════════════

const ISSUE = {
  pothole:     { emoji:'🕳', color:'#B85042', label:'Pothole',     label_hi:'गड्ढा'              },
  garbage:     { emoji:'🗑', color:'#8BC34A', label:'Garbage',     label_hi:'कचरा'               },
  water:       { emoji:'💧', color:'#1B4F72', label:'Water Leak',  label_hi:'पानी की समस्या'      },
  streetlight: { emoji:'💡', color:'#B7770D', label:'Streetlight', label_hi:'स्ट्रीटलाइट'          },
  sewage:      { emoji:'🚧', color:'#6B7280', label:'Sewage',      label_hi:'नाली की समस्या'      },
  electricity: { emoji:'⚡', color:'#B7770D', label:'Electricity', label_hi:'बिजली की समस्या'    },
  traffic:     { emoji:'🚦', color:'#EF5350', label:'Traffic',     label_hi:'ट्रैफिक'             },
  tree:        { emoji:'🌳', color:'#2D6A4F', label:'Tree',        label_hi:'पेड़'               },
  noise:       { emoji:'📢', color:'#7C3AED', label:'Noise',       label_hi:'शोर'                },
  other:       { emoji:'⚠',  color:'#6B7280', label:'Other',       label_hi:'अन्य'               },
};

// ── i18n strings ──
const I18N = {
  en: {
    point_camera:'Point camera at a civic issue',
    analyzing:'Analyzing…',
    sev_high:'HIGH SEVERITY', sev_medium:'MEDIUM SEVERITY', sev_low:'LOW SEVERITY',
    high:'HIGH', medium:'MEDIUM', low:'LOW',
    ai_confidence:'AI Confidence', hazard_level:'Hazard Level',
    authority:'Authority', est_repair:'Est. Repair',
    ai_analysis:'🤖 Groq AI Analysis',
    nearby_ngos:'📍 Nearby NGOs', contact_authority:'📞 Contact Authority',
    helpline:'Helpline',
    submit_btn:'Submit to AreaPulse →', submitting:'⏳ Submitting…',
    scan_another:'Scan Another Issue',
    back:'← Back', issue_report:'Issue Report',
    severity_lbl:'SEVERITY', dispatch_to:'DISPATCH TO',
    eta:'ETA', wrong_scan_again:'↺ Wrong? Scan Again',
    view_report:'View Report →',
    reported_by:'Reported by',
    submitted:'Submitted!',
    saved_to_db:'Issue saved to AreaPulse database',
    my_reports_on_ap:'My Reports on AreaPulse →',
    no_detection:'No civic issue detected. Try pointing closer to the problem with good lighting.',
    captured_photo:'📸 Captured Photo',
  },
  hi: {
    point_camera:'कैमरा किसी नागरिक समस्या की तरफ करें',
    analyzing:'जांच हो रही है…',
    sev_high:'अत्यधिक गंभीर', sev_medium:'मध्यम गंभीर', sev_low:'कम गंभीर',
    high:'गंभीर', medium:'मध्यम', low:'हल्की',
    ai_confidence:'AI विश्वास', hazard_level:'खतरे का स्तर',
    authority:'प्राधिकरण', est_repair:'मरम्मत समय',
    ai_analysis:'🤖 Groq AI विश्लेषण',
    nearby_ngos:'📍 आसपास के NGO', contact_authority:'📞 प्राधिकरण से संपर्क',
    helpline:'हेल्पलाइन',
    submit_btn:'AreaPulse पर भेजें →', submitting:'⏳ भेज रहे हैं…',
    scan_another:'दूसरी समस्या स्कैन करें',
    back:'← वापस', issue_report:'समस्या रिपोर्ट',
    severity_lbl:'गंभीरता', dispatch_to:'भेजें',
    eta:'अनुमान', wrong_scan_again:'↺ गलत? दोबारा स्कैन करें',
    view_report:'रिपोर्ट देखें →',
    reported_by:'रिपोर्ट करने वाले',
    submitted:'सफलतापूर्वक भेज दी!',
    saved_to_db:'समस्या AreaPulse में दर्ज हो गई',
    my_reports_on_ap:'AreaPulse पर मेरी रिपोर्ट्स →',
    no_detection:'कोई नागरिक समस्या नहीं मिली। बेहतर रोशनी में पास से दोबारा कोशिश करें।',
    captured_photo:'📸 ली गई तस्वीर',
  },
};
function t(key) { return (I18N[voiceLang] && I18N[voiceLang][key]) || I18N.en[key] || key; }
function labelFor(tag) {
  const m = ISSUE[tag] || ISSUE.other;
  return voiceLang === 'hi' ? m.label_hi : m.label;
}

const AUTHORITY_CONTACTS = {
  'MCD North':           { phone: '1800110081', email: 'pgms@mcdonline.nic.in' },
  'MCD South':           { phone: '1800110081', email: 'pgms@mcdonline.nic.in' },
  'DJB':                 { phone: '1916',       email: 'cmo@delhijalboard.in' },
  'PWD':                 { phone: '011-23730011', email: 'secretary-pwd@nic.in' },
  'BSES Yamuna':         { phone: '19123',      email: 'customercare@bses.in' },
  'BSES Rajdhani':       { phone: '19125',      email: 'customercare@bses.in' },
  'Delhi Traffic Police':{ phone: '1095',       email: 'hqrs@delhitrafficpolice.nic.in' },
  'NDMC':                { phone: '1800110078', email: 'ndmc@ndmc.gov.in' },
};

let videoStream    = null;
let cameraReady    = false;
let userLat        = null;
let userLng        = null;
let userAcc        = null;
let deviceHeading  = 0;
let hasOrientation = false;
let capturedImage  = null;  // full data URL  (data:image/jpeg;base64,...)
let detectedIssues = [];
let primaryIssue   = null;
let isDetected     = false;
let selectedNGO    = null;
let nearbyIssues   = [];
let nearbyNGOs     = [];
let arRaf          = null;
let lastFetch      = 0;
let voiceLang      = localStorage.getItem('ap_lang') || 'en';
let detectTimer    = null;
const FOV_DEG      = 70;

// ── Voice loading (browsers populate getVoices() async) ──
let _availableVoices = [];
function loadVoices() {
  return new Promise(resolve => {
    let v = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
    if (v && v.length) { _availableVoices = v; resolve(v); return; }
    if (!window.speechSynthesis) { resolve([]); return; }
    const handler = () => {
      _availableVoices = window.speechSynthesis.getVoices();
      window.speechSynthesis.removeEventListener('voiceschanged', handler);
      resolve(_availableVoices);
    };
    window.speechSynthesis.addEventListener('voiceschanged', handler);
    setTimeout(() => resolve(window.speechSynthesis.getVoices()), 1500);
  });
}

// ══════════════════════════════════════════════════════════
//  AUTH
// ══════════════════════════════════════════════════════════
function getCurrentUser() { return localStorage.getItem('ap_user') || 'anonymous'; }

function doLogin() {
  const input = document.getElementById('login-user');
  const username = (input.value || '').trim();
  if (!username) { input.focus(); input.style.borderColor = '#B85042'; return; }
  localStorage.setItem('ap_user', username);
  showScreen('s-camera');
  initApp();
}

function logout() {
  const btn = document.getElementById('logout-btn');
  if (!btn) return;
  if (btn.dataset.confirming === '1') {
    localStorage.removeItem('ap_user');
    // Keep ap_reports — user might re-log in with same name
    document.getElementById('my-reports-panel').classList.add('hidden');
    document.getElementById('login-user').value = '';
    if (videoStream) {
      videoStream.getTracks().forEach(t => t.stop());
      videoStream = null;
      cameraReady = false;
    }
    showScreen('s-login');
    return;
  }
  btn.dataset.confirming = '1';
  const orig = btn.textContent;
  btn.textContent = 'Tap again to sign out';
  btn.classList.add('confirming');
  setTimeout(() => {
    if (btn.dataset.confirming === '1') {
      btn.textContent = orig;
      btn.classList.remove('confirming');
      delete btn.dataset.confirming;
    }
  }, 3000);
}

// ══════════════════════════════════════════════════════════
//  BOOT
// ══════════════════════════════════════════════════════════
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('lang-toggle').textContent = voiceLang === 'hi' ? 'HI' : 'EN';
  loadVoices();   // start loading voices early
  const user = localStorage.getItem('ap_user');
  if (!user) { showScreen('s-login'); return; }
  showScreen('s-camera');
  initApp();
});

async function initApp() {
  initCanvas();
  initLocation();
  initOrientation();
  await initCamera();
  setStatus('🎯', t('point_camera'));
}

// ══════════════════════════════════════════════════════════
//  VOICE LANGUAGE
// ══════════════════════════════════════════════════════════
async function toggleVoiceLang() {
  voiceLang = voiceLang === 'en' ? 'hi' : 'en';
  localStorage.setItem('ap_lang', voiceLang);
  document.getElementById('lang-toggle').textContent = voiceLang === 'hi' ? 'HI' : 'EN';

  if (voiceLang === 'hi') {
    await loadVoices();
    if (!findHindiVoice() && !window._hiVoiceWarned) {
      window._hiVoiceWarned = true;
      setStatus('⚠️', 'No Hindi voice on this device. Install one in OS settings — text will still display in Hindi.');
      setTimeout(() => setStatus('🎯', t('point_camera')), 7000);
    } else {
      setStatus('🎯', t('point_camera'));
    }
  } else {
    setStatus('🎯', t('point_camera'));
  }

  if (primaryIssue && !document.getElementById('s-report').classList.contains('hidden')) {
    renderReport(detectedIssues, primaryIssue);
  }
}

function findHindiVoice() {
  return _availableVoices.find(v => {
    const l = (v.lang || '').toLowerCase();
    const n = (v.name || '').toLowerCase();
    return l.startsWith('hi') || l === 'hi-in' || n.includes('hindi');
  });
}

async function speak(textEn, textHi) {
  if (!('speechSynthesis' in window)) return;
  await loadVoices();
  window.speechSynthesis.cancel();
  // Chrome: brief tick after cancel() before speak() is reliable
  await new Promise(r => setTimeout(r, 60));

  let text = (voiceLang === 'hi' && textHi) ? textHi : textEn;
  if (!text) return;

  const u = new SpeechSynthesisUtterance(text);
  u.lang = voiceLang === 'hi' ? 'hi-IN' : 'en-US';

  if (voiceLang === 'hi') {
    const hiVoice = findHindiVoice();
    if (hiVoice) {
      u.voice = hiVoice;
      console.log('[speak] Using Hindi voice:', hiVoice.name, hiVoice.lang);
    } else {
      // No Hindi voice installed — speak English version instead of silent garbage
      console.warn('[speak] No Hindi voice on this device. Speaking English audio.');
      u.text = textEn || text;
      u.lang = 'en-US';
    }
  }
  u.rate = 0.95; u.pitch = 1.0; u.volume = 1.0;
  window.speechSynthesis.speak(u);
}

// ══════════════════════════════════════════════════════════
//  MY REPORTS PANEL
// ══════════════════════════════════════════════════════════
function toggleMyReports() {
  const panel = document.getElementById('my-reports-panel');
  if (panel.classList.contains('hidden')) {
    const userEl = document.getElementById('mrp-username');
    if (userEl) userEl.textContent = getCurrentUser();
    renderMyReports();
    panel.classList.remove('hidden');
  } else {
    panel.classList.add('hidden');
  }
}

function renderMyReports() {
  const reports = JSON.parse(localStorage.getItem('ap_reports') || '[]');
  document.getElementById('mrp-view-all').href = `${window.AREAPULSE_URL}/my-reports`;
  const list = document.getElementById('mrp-list');
  if (!reports.length) {
    list.innerHTML = '<div class="mrp-empty">No reports yet.<br>Scan a civic issue to get started!</div>';
    return;
  }
  list.innerHTML = reports.map(r => {
    const meta = ISSUE[r.type] || ISSUE.other;
    const date = new Date(r.ts).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' });
    const sevClass = r.severity === 'high' ? 'sev-high' : r.severity === 'low' ? 'sev-low' : 'sev-medium';
    return `
      <div class="mrp-item">
        <div class="mrp-item-main">
          <span class="mrp-emoji">${meta.emoji}</span>
          <div class="mrp-item-body">
            <div class="mrp-item-title">${esc(r.title || (voiceLang==='hi'?meta.label_hi:meta.label))}</div>
            <div class="mrp-item-meta">${esc(r.area)} · ${date}</div>
          </div>
          <span class="mrp-sev-dot ${sevClass}"></span>
        </div>
        <div class="mrp-item-footer">
          <span class="mrp-id"># ${r.id}</span>
          <a class="mrp-view-btn" href="${window.AREAPULSE_URL}/my-reports" target="_blank">View Report →</a>
        </div>
      </div>`;
  }).join('');
}

function saveToMyReports(id) {
  if (!primaryIssue) return;
  const reports = JSON.parse(localStorage.getItem('ap_reports') || '[]');
  reports.unshift({
    id,
    title: primaryIssue.title,
    type: primaryIssue.issue_type,
    area: userArea || primaryIssue.area_estimate || 'Delhi',
    severity: primaryIssue.severity || 'medium',
    ts: Date.now(),
  });
  localStorage.setItem('ap_reports', JSON.stringify(reports.slice(0, 30)));
}

// ══════════════════════════════════════════════════════════
//  CAMERA
// ══════════════════════════════════════════════════════════
async function initCamera() {
  const vid = document.getElementById('vid');
  document.getElementById('cam-error').classList.add('hidden');

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const isInsecure = window.location.protocol === 'http:' &&
                       !['localhost','127.0.0.1'].includes(window.location.hostname);
    showCameraError(isInsecure
      ? `Camera blocked: HTTPS required. Try http://localhost:5001 or use ngrok.`
      : 'Your browser does not support camera access. Try Chrome or Safari.');
    return;
  }

  const tries = [
    { video:{ facingMode:{ ideal:'environment' }, width:{ ideal:1920 }, height:{ ideal:1080 } }, audio:false },
    { video:{ facingMode:'environment' }, audio:false },
    { video:true, audio:false },
  ];

  let lastErr = null;
  for (const c of tries) {
    try {
      videoStream = await navigator.mediaDevices.getUserMedia(c);
      vid.srcObject = videoStream;
      await vid.play();
      cameraReady = true;
      document.getElementById('btn-scan').disabled = false;
      return;
    } catch (e) { lastErr = e; }
  }

  cameraReady = false;
  let msg = 'Unable to access camera.';
  if (lastErr?.name === 'NotAllowedError' || lastErr?.name === 'PermissionDeniedError')
    msg = 'Camera permission denied. Please allow camera access in settings and retry.';
  else if (lastErr?.name === 'NotFoundError' || lastErr?.name === 'DevicesNotFoundError')
    msg = 'No camera found. Open on a phone with a rear camera.';
  else if (lastErr?.name === 'NotReadableError')
    msg = 'Camera is being used by another app. Close it and retry.';
  showCameraError(msg);
}

function showCameraError(msg) {
  document.getElementById('cam-error-msg').textContent = msg;
  document.getElementById('cam-error').classList.remove('hidden');
  document.getElementById('btn-scan').disabled = true;
  setStatus('⚠️', 'Camera required to scan');
}

async function retryCamera() {
  setStatus('🔄', 'Reconnecting to camera...');
  await initCamera();
}

// ══════════════════════════════════════════════════════════
//  GPS
// ══════════════════════════════════════════════════════════
function initLocation() {
  if (!navigator.geolocation) {
    document.getElementById('gps-txt').textContent = 'GPS unavailable';
    return;
  }
  document.getElementById('gps-txt').textContent = 'Searching…';
  navigator.geolocation.getCurrentPosition(
    pos => {
      setPosition(pos);
      navigator.geolocation.watchPosition(setPosition,
        e => console.warn('GPS watch:', e.message),
        { enableHighAccuracy: true, maximumAge: 5000 });
    },
    err => {
      if (err.code === 1) document.getElementById('gps-txt').textContent = 'GPS denied';
      else {
        document.getElementById('gps-txt').textContent = 'No GPS signal';
        navigator.geolocation.watchPosition(setPosition,
          e => console.warn('GPS retry:', e.message),
          { enableHighAccuracy: true, timeout: 20000 });
      }
    },
    { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
  );
}

let userArea = null;

function setPosition(pos) {
  userLat = pos.coords.latitude;
  userLng = pos.coords.longitude;
  userAcc = Math.round(pos.coords.accuracy);
  updateCoords();
  fetch(`/api/geocode?lat=${userLat}&lng=${userLng}`)
    .then(r => r.json())
    .then(d => {
      userArea = d.area && d.area !== 'Unknown' ? d.area : null;
      if (userArea) document.getElementById('gps-txt').textContent = userArea;
    }).catch(() => {});
  if (Date.now() - lastFetch > 30000) loadNearby();
}

function updateCoords() {
  if (!userLat) return;
  document.getElementById('gps-txt').textContent = userArea || 'GPS Fixed';
  document.getElementById('coords-lat').textContent = `LAT ${userLat.toFixed(5)}`;
  document.getElementById('coords-lng').textContent = `LNG ${userLng.toFixed(5)}`;
  document.getElementById('coords-acc').textContent = `±${userAcc||'?'}m`;
  const stripEl = document.getElementById('coords-strip');
  if (stripEl) {
    if (userAcc > 5000) { stripEl.classList.add('gps-bad'); stripEl.title = 'IP-based location — open on phone for real GPS'; }
    else if (userAcc > 500) stripEl.classList.add('gps-meh');
    else stripEl.classList.remove('gps-bad','gps-meh');
  }
}

// ══════════════════════════════════════════════════════════
//  ORIENTATION
// ══════════════════════════════════════════════════════════
function initOrientation() {
  const handler = (e) => {
    if (e.webkitCompassHeading !== undefined) deviceHeading = e.webkitCompassHeading;
    else if (e.alpha !== null) deviceHeading = (360 - e.alpha) % 360;
    hasOrientation = true;
  };
  if (typeof DeviceOrientationEvent !== 'undefined' &&
      typeof DeviceOrientationEvent.requestPermission === 'function') {
    const btn = document.createElement('button');
    btn.className = 'orient-btn';
    btn.textContent = '🧭 Enable AR Compass';
    btn.onclick = async () => {
      try {
        const p = await DeviceOrientationEvent.requestPermission();
        if (p === 'granted') { window.addEventListener('deviceorientation', handler); btn.remove(); }
      } catch (e) { console.warn('Orientation perm denied'); }
    };
    document.body.appendChild(btn);
  } else {
    window.addEventListener('deviceorientationabsolute', handler);
    window.addEventListener('deviceorientation', handler);
  }
}

function bearingTo(lat2, lng2) {
  if (userLat == null) return 0;
  const φ1 = userLat * Math.PI/180, φ2 = lat2 * Math.PI/180;
  const Δλ = (lng2 - userLng) * Math.PI/180;
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return (Math.atan2(y, x) * 180/Math.PI + 360) % 360;
}

function angleDiff(bearing) {
  let d = bearing - deviceHeading;
  while (d > 180) d -= 360;
  while (d < -180) d += 360;
  return d;
}

// ══════════════════════════════════════════════════════════
//  NEARBY
// ══════════════════════════════════════════════════════════
async function loadNearby() {
  if (!userLat) return;
  lastFetch = Date.now();
  try {
    const r = await fetch(`/api/nearby?lat=${userLat}&lng=${userLng}`);
    const d = await r.json();
    nearbyIssues = d.issues || [];
    nearbyNGOs   = d.ngos   || [];
    renderSidePanels();
  } catch (e) { console.warn('Nearby fetch:', e); }
}

function renderSidePanels() {
  const ngoP = document.getElementById('ar-ngo-panel');
  const ipP  = document.getElementById('ar-issue-panel');
  if (!isDetected || !primaryIssue) { ngoP.innerHTML = ''; ipP.innerHTML = ''; return; }

  const meta = ISSUE[primaryIssue.issue_type] || ISSUE.other;
  const sevColor = primaryIssue.severity === 'high' ? '#B85042'
                 : primaryIssue.severity === 'medium' ? '#B7770D' : '#2D6A4F';
  const sevTxt = t(primaryIssue.severity || 'medium');

  ngoP.innerHTML = `
    <div class="ar-detect-card" style="border-left-color:${sevColor}">
      <div class="card-label">${t('severity_lbl')}</div>
      <div class="card-value" style="color:${sevColor}">${sevTxt}</div>
      <div class="card-sub">${meta.emoji} ${labelFor(primaryIssue.issue_type)}</div>
    </div>
    <div class="ar-detect-card" style="border-left-color:#1B4F72">
      <div class="card-label">${t('dispatch_to')}</div>
      <div class="card-value-sm">${esc(primaryIssue.recommended_authority || 'MCD')}</div>
      <div class="card-sub">${t('eta')} ${esc(primaryIssue.estimated_repair_time || '3-7 days')}</div>
    </div>`;

  const matchedNgos = nearbyNGOs.filter(n => !n.tag || n.tag === primaryIssue.issue_type || n.tag === 'other').slice(0,3);
  const ngosToShow  = matchedNgos.length ? matchedNgos : nearbyNGOs.slice(0,2);
  ipP.innerHTML = `
    <div class="ar-popup-title">${t('nearby_ngos')}</div>
    ${ngosToShow.map(n => `
      <div class="ar-ngo-popup" onclick="selectNGO(${nearbyNGOs.indexOf(n)})">
        <div class="ngo-popup-name">${esc(n.name)}</div>
        <div class="ngo-popup-focus">${esc(n.focus || '')}</div>
        <div class="ngo-popup-dist"><span class="ngo-popup-dot"></span>${n.distance_km} km · ★${Number(n.rating).toFixed(1)}</div>
      </div>`).join('')}`;
}

function selectNGO(idx) {
  selectedNGO = nearbyNGOs[idx];
  renderSidePanels();
  speak(`Navigating to ${selectedNGO.name}, ${selectedNGO.distance_km} kilometers away.`,
        `${selectedNGO.name} की तरफ जा रहे हैं, ${selectedNGO.distance_km} किलोमीटर दूर।`);
  setStatus('🧭', `${selectedNGO.name}`);
}

// ══════════════════════════════════════════════════════════
//  AR CANVAS
// ══════════════════════════════════════════════════════════
function initCanvas() {
  const c = document.getElementById('ar');
  const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
  resize();
  window.addEventListener('resize', resize);
  const loop = () => {
    const ctx = c.getContext('2d');
    const W = c.width, H = c.height;
    ctx.clearRect(0, 0, W, H);
    if (isDetected && detectedIssues.length) drawDetectedMulti(ctx, W, H);
    else {
      drawScanning(ctx, W, H);
      drawNGOMarkers(ctx, W, H);
      if (selectedNGO) drawNavigationArrow(ctx, W, H);
    }
    arRaf = requestAnimationFrame(loop);
  };
  arRaf = requestAnimationFrame(loop);
}

function drawScanning(ctx, W, H) {
  const C = '#B85042', B = 36, T = 2.5;
  ctx.strokeStyle = C; ctx.lineWidth = T; ctx.lineCap = 'round';
  ctx.globalAlpha = 0.75;
  [[24,24,1,1],[W-24,24,-1,1],[24,H-24,1,-1],[W-24,H-24,-1,-1]].forEach(([x,y,dx,dy]) => {
    ctx.beginPath();
    ctx.moveTo(x, y+dy*B); ctx.lineTo(x, y); ctx.lineTo(x+dx*B, y);
    ctx.stroke();
  });
  ctx.globalAlpha = 1;
  const cx = W/2, cy = H*0.43;
  ctx.strokeStyle = 'rgba(255,255,255,0.45)'; ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.moveTo(cx-14,cy); ctx.lineTo(cx+14,cy); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx,cy-14); ctx.lineTo(cx,cy+14); ctx.stroke();
  ctx.fillStyle = C; ctx.beginPath(); ctx.arc(cx,cy,3,0,Math.PI*2); ctx.fill();
}

function drawNGOMarkers(ctx, W, H) {
  if (!hasOrientation || !userLat || !nearbyNGOs.length) return;
  const halfFov = FOV_DEG / 2;
  nearbyNGOs.slice(0, 4).forEach(ngo => {
    if (!ngo.lat || !ngo.lng) return;
    const b = bearingTo(ngo.lat, ngo.lng);
    const diff = angleDiff(b);
    if (Math.abs(diff) <= halfFov) {
      const x = W/2 + (diff / halfFov) * (W/2 - 60);
      const y = H * 0.32 + (ngo.distance_km * 15);
      drawNGOPin(ctx, x, y, ngo);
    } else drawEdgeArrow(ctx, diff < 0 ? 30 : W-30, H/2, diff < 0, ngo);
  });
}

function drawNGOPin(ctx, x, y, ngo) {
  const isSel = selectedNGO && selectedNGO.id === ngo.id;
  const C = isSel ? '#B85042' : '#2D6A4F';
  ctx.fillStyle = 'rgba(0,0,0,0.4)';
  rrect(ctx, x-65, y+2, 130, 38, 19); ctx.fill();
  ctx.fillStyle = C;
  rrect(ctx, x-65, y, 130, 36, 18); ctx.fill();
  if (isSel) {
    ctx.strokeStyle = `rgba(184,80,66,${0.4 + 0.3*Math.sin(Date.now()/300)})`;
    ctx.lineWidth = 3;
    rrect(ctx, x-69, y-4, 138, 44, 22); ctx.stroke();
  }
  ctx.fillStyle = 'rgba(255,255,255,0.2)';
  ctx.beginPath(); ctx.arc(x-50, y+18, 11, 0, Math.PI*2); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.font = '14px sans-serif';
  ctx.fillText('🏛', x-58, y+23);
  ctx.font = 'bold 11px DM Sans, sans-serif';
  const name = ngo.name.length > 14 ? ngo.name.substring(0,13)+'…' : ngo.name;
  ctx.fillText(name, x-32, y+15);
  ctx.font = '9.5px DM Sans, sans-serif';
  ctx.fillStyle = 'rgba(255,255,255,0.85)';
  ctx.fillText(`${ngo.distance_km} km`, x-32, y+28);
}

function drawEdgeArrow(ctx, x, y, isLeft, ngo) {
  const C = selectedNGO && selectedNGO.id === ngo.id ? '#B85042' : '#2D6A4F';
  ctx.fillStyle = C;
  ctx.beginPath();
  if (isLeft) { ctx.moveTo(x-12,y); ctx.lineTo(x+8,y-14); ctx.lineTo(x+8,y+14); }
  else        { ctx.moveTo(x+12,y); ctx.lineTo(x-8,y-14); ctx.lineTo(x-8,y+14); }
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.font = 'bold 9px DM Sans, sans-serif';
  const txt = `${ngo.distance_km}km`;
  const tx = isLeft ? x+14 : x-14-ctx.measureText(txt).width;
  ctx.fillText(txt, tx, y+3);
}

function drawNavigationArrow(ctx, W, H) {
  if (!selectedNGO || !hasOrientation || !selectedNGO.lat) return;
  const b = bearingTo(selectedNGO.lat, selectedNGO.lng);
  const diff = angleDiff(b);
  const cx = W/2, cy = H * 0.58, size = 80;
  ctx.save();
  ctx.translate(cx, cy); ctx.rotate(diff * Math.PI/180);
  ctx.strokeStyle = 'rgba(184,80,66,0.4)'; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.arc(0, 0, size*0.7, 0, Math.PI*2); ctx.stroke();
  ctx.fillStyle = '#B85042';
  ctx.beginPath();
  ctx.moveTo(0,-size*0.55); ctx.lineTo(size*0.32,size*0.2);
  ctx.lineTo(0,size*0.05);  ctx.lineTo(-size*0.32,size*0.2);
  ctx.closePath(); ctx.fill();
  ctx.restore();
  ctx.fillStyle = 'rgba(0,0,0,0.7)';
  rrect(ctx, cx-70, cy+50, 140, 32, 16); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.font = 'bold 13px DM Sans, sans-serif'; ctx.textAlign = 'center';
  ctx.fillText(`${selectedNGO.distance_km} km · ${selectedNGO.name.substring(0,16)}`, cx, cy+70);
  ctx.textAlign = 'left';
}

function drawDetectedMulti(ctx, W, H) {
  if (!detectedIssues.length) return;

  // Slight darken so overlay reads on bright outdoor shots
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(0, 0, W, H);

  // Bounding box per detected issue
  detectedIssues.forEach((iss, idx) => drawBBox(ctx, W, H, iss, idx));

  // Top-left counter panel — CCTV style
  drawCounterPanel(ctx, W, H);

  // Bottom strip: camera ID, timestamp, FPS (above the action bar)
  drawCameraInfoStrip(ctx, W, H);
}

function drawBBox(ctx, W, H, iss, idx) {
  const meta = ISSUE[iss.issue_type] || ISSUE.other;
  let x1, y1, x2, y2;

  if (Array.isArray(iss.bbox) && iss.bbox.length === 4) {
    x1 = iss.bbox[0] * W / 100;
    y1 = iss.bbox[1] * H / 100;
    x2 = iss.bbox[2] * W / 100;
    y2 = iss.bbox[3] * H / 100;
  } else {
    // Fallback box around the center hint
    const cx = (iss.x_hint != null ? iss.x_hint : 30 + idx*20) * W / 100;
    const cy = (iss.y_hint != null ? iss.y_hint : 35 + idx*15) * H / 100;
    const bw = Math.min(W * 0.30, 240), bh = Math.min(H * 0.25, 200);
    x1 = cx - bw/2; y1 = cy - bh/2;
    x2 = cx + bw/2; y2 = cy + bh/2;
  }
  // Clamp
  x1 = Math.max(4, x1); y1 = Math.max(70, y1);
  x2 = Math.min(W-4, x2); y2 = Math.min(H-120, y2);
  const w = x2 - x1, h = y2 - y1;
  if (w < 20 || h < 20) return;

  const sevColor = iss.severity === 'high' ? '#FF5252'
                : iss.severity === 'medium' ? '#FFC107' : '#69F0AE';

  // Bright yellow box (CCTV-style)
  ctx.strokeStyle = '#FFEB3B';
  ctx.lineWidth = 2.5;
  ctx.strokeRect(x1, y1, w, h);

  // Header label strip on top of the box
  const labelText = `${(iss.ar_label || meta.label).toUpperCase()}  ${iss.confidence || 88}%`;
  ctx.font = 'bold 11px "Courier New", ui-monospace, monospace';
  const labelW = ctx.measureText(labelText).width;
  const headerW = Math.max(w, labelW + 16);
  const headerH = 18;
  ctx.fillStyle = sevColor;
  ctx.fillRect(x1, y1 - headerH, headerW, headerH);
  ctx.fillStyle = '#000';
  ctx.fillText(labelText, x1 + 8, y1 - 5);

  // ID badge below the box
  const idText = `ID: ${(idx+1).toString().padStart(3,'0')}`;
  ctx.font = 'bold 10.5px "Courier New", ui-monospace, monospace';
  const idW = ctx.measureText(idText).width + 12;
  ctx.fillStyle = 'rgba(0,0,0,0.85)';
  ctx.fillRect(x2 - idW, y2, idW, 16);
  ctx.fillStyle = '#FFEB3B';
  ctx.fillText(idText, x2 - idW + 6, y2 + 12);
}

function drawCounterPanel(ctx, W, H) {
  // Tally by type
  const counts = {};
  detectedIssues.forEach(iss => {
    const k = iss.issue_type || 'other';
    counts[k] = (counts[k] || 0) + 1;
  });

  // High/low severity breakdown
  const high = detectedIssues.filter(i => i.severity === 'high').length;
  const med  = detectedIssues.filter(i => i.severity === 'medium').length;
  const low  = detectedIssues.filter(i => i.severity === 'low').length;

  const x = 12;
  const y = 64;   // below the top bar
  const padX = 10;
  const lineH = 16;
  const items = Object.entries(counts);
  const headerH = 24;
  const subH = 16;
  const w = 200;
  const h = headerH + subH + items.length * lineH + 8;

  // Background (CCTV-style dark with soft border)
  ctx.fillStyle = 'rgba(0,0,0,0.72)';
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = '#FFEB3B';
  ctx.lineWidth = 1;
  ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);

  // Title
  ctx.fillStyle = '#FFEB3B';
  ctx.font = 'bold 12.5px "Courier New", ui-monospace, monospace';
  ctx.fillText(`Total: ${detectedIssues.length} detected`, x + padX, y + 16);

  // High/med/low sub-row
  ctx.font = 'bold 10px "Courier New", ui-monospace, monospace';
  ctx.fillStyle = '#FF5252'; ctx.fillText(`${high} up`,  x + padX,       y + headerH + 10);
  ctx.fillStyle = '#FFC107'; ctx.fillText(`${med} med`,  x + padX + 50,  y + headerH + 10);
  ctx.fillStyle = '#69F0AE'; ctx.fillText(`${low} down`, x + padX + 105, y + headerH + 10);

  // Per-type rows
  ctx.fillStyle = '#FFEB3B';
  ctx.font = 'bold 11px "Courier New", ui-monospace, monospace';
  items.forEach(([tag, n], i) => {
    const meta = ISSUE[tag] || ISSUE.other;
    ctx.fillText(`${meta.label.padEnd(13)} ${n}`, x + padX, y + headerH + subH + 12 + i * lineH);
  });
}

function drawCameraInfoStrip(ctx, W, H) {
  // Yellow horizontal line across the lower-third (CCTV detection line)
  const ly = H * 0.62;
  ctx.strokeStyle = 'rgba(255,235,59,0.6)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(0, ly); ctx.lineTo(W, ly);
  ctx.stroke();

  // Bottom-left: date/time/area (drawn above the bottom action bar, ~y = H - 130)
  const baseY = H - 132;
  const now = new Date();
  const date = now.toISOString().slice(0, 10) + ' ' + now.toTimeString().slice(0, 8);
  ctx.fillStyle = '#FFEB3B';
  ctx.font = 'bold 11px "Courier New", ui-monospace, monospace';
  ctx.textAlign = 'left';
  ctx.fillText(date, 14, baseY);
  if (userArea) {
    ctx.font = 'bold 10px "Courier New", ui-monospace, monospace';
    ctx.fillStyle = 'rgba(255,235,59,0.85)';
    ctx.fillText(`AREA: ${userArea.toUpperCase()}`, 14, baseY + 14);
  }

  // Bottom-right: camera label + FPS
  ctx.textAlign = 'right';
  ctx.fillStyle = '#FFEB3B';
  ctx.font = 'bold 12px "Courier New", ui-monospace, monospace';
  ctx.fillText('AreaPulse · Camera 1', W - 14, baseY - 4);
  // Animated FPS for realism
  const fps = (9.7 + Math.sin(Date.now() / 600) * 0.18).toFixed(2);
  ctx.font = 'bold 11px "Courier New", ui-monospace, monospace';
  ctx.fillText(`FPS: ${fps}`, W - 14, baseY + 12);

  ctx.textAlign = 'left';
}

function rrect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x+r,y); ctx.lineTo(x+w-r,y); ctx.arcTo(x+w,y,x+w,y+r,r);
  ctx.lineTo(x+w,y+h-r); ctx.arcTo(x+w,y+h,x+w-r,y+h,r);
  ctx.lineTo(x+r,y+h); ctx.arcTo(x,y+h,x,y+h-r,r);
  ctx.lineTo(x,y+r); ctx.arcTo(x,y,x+r,y,r); ctx.closePath();
}

// ══════════════════════════════════════════════════════════
//  SCAN FLOW
// ══════════════════════════════════════════════════════════
async function startScan() {
  if (!cameraReady || !videoStream || !isCameraLive()) {
    showCameraError('Camera is not active. Please grant camera access and retry.');
    return;
  }
  const btn = document.getElementById('btn-scan');
  btn.disabled = true;

  // Flash
  const fl = document.createElement('div');
  fl.style.cssText = 'position:fixed;inset:0;background:#fff;z-index:500;opacity:.75;pointer-events:none;transition:opacity .2s';
  document.body.appendChild(fl);
  setTimeout(() => { fl.style.opacity = '0'; setTimeout(() => fl.remove(), 220); }, 50);

  const captured = captureFrame();
  if (captured === 'TOO_DARK') {
    btn.disabled = false;
    showNoDetection('Camera frame is too dark. Uncover the lens or improve lighting and scan again.');
    return;
  }
  if (!captured) {
    btn.disabled = false;
    showNoDetection('Failed to capture image. Please try again.');
    return;
  }

  capturedImage = captured;  // full data URL
  const b64 = captured.split(',')[1];

  showScreen('s-analyze');
  const result = await callAnalyze(b64);

  if (!result || result._err || !result.issues || !result.issues.length) {
    btn.disabled = false;
    showScreen('s-camera');
    showNoDetection(result?._err || t('no_detection'));
    return;
  }

  detectedIssues = result.issues;
  primaryIssue = detectedIssues[result.primary_index || 0] || detectedIssues[0];
  isDetected = true;

  showScreen('s-camera');
  renderSidePanels();
  narrateDetection(detectedIssues);

  document.getElementById('detect-action-bar').classList.remove('hidden');
  document.getElementById('det-btn-scan-again').textContent = t('wrong_scan_again');
  document.getElementById('det-btn-view-report').textContent = t('view_report');

  detectTimer = setTimeout(() => goToReport(), 6000);
  btn.disabled = false;
}

function scanAgain() {
  clearTimeout(detectTimer);
  document.getElementById('detect-action-bar').classList.add('hidden');
  isDetected = false;
  detectedIssues = [];
  primaryIssue = null;
  capturedImage = null;
  renderSidePanels();
  setStatus('🎯', t('point_camera'));
}

function goToReport() {
  clearTimeout(detectTimer);
  document.getElementById('detect-action-bar').classList.add('hidden');
  renderReport(detectedIssues, primaryIssue);
  showScreen('s-report');
}

function isCameraLive() {
  if (!videoStream) return false;
  const tracks = videoStream.getVideoTracks();
  return tracks.length > 0 && tracks[0].readyState === 'live' && !tracks[0].muted;
}

function captureFrame() {
  const vid = document.getElementById('vid');
  if (!vid.videoWidth || !vid.videoHeight) return null;
  if (vid.paused || vid.ended) return null;
  if (!isCameraLive()) return null;

  // Downscale to max 1280px wide — keeps Firestore doc under 1MB while still good for AI
  const maxW = 1280;
  let w = vid.videoWidth, h = vid.videoHeight;
  if (w > maxW) { h = h * maxW / w; w = maxW; }
  const tmp = document.createElement('canvas');
  tmp.width = w; tmp.height = h;
  const ctx = tmp.getContext('2d');
  ctx.drawImage(vid, 0, 0, w, h);

  const sample = ctx.getImageData(0, 0, Math.min(80,tmp.width), Math.min(80,tmp.height)).data;
  let total = 0, maxB = 0, minB = 255;
  for (let i = 0; i < sample.length; i += 4) {
    const b = (sample[i] + sample[i+1] + sample[i+2]) / 3;
    total += b; if (b > maxB) maxB = b; if (b < minB) minB = b;
  }
  const avg = total / (sample.length / 4);
  const variance = maxB - minB;
  if (avg < 22 || variance < 18) return 'TOO_DARK';

  return tmp.toDataURL('image/jpeg', 0.78);  // returns full data URL
}

// ══════════════════════════════════════════════════════════
//  API
// ══════════════════════════════════════════════════════════
async function callAnalyze(b64) {
  if (!b64) return { _err: 'No image captured.' };
  try {
    const r = await fetch('/api/analyze', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ image: b64 }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.error) {
      const err = data.error || `HTTP ${r.status}`;
      const raw = data.raw ? ` · AI said: "${data.raw.substring(0,120)}…"` : '';
      return { _err: `AI error: ${err}${raw}` };
    }
    if (data.issues && data.issues.length) return data;
    if (data.detected && data.issue_type) return { issues:[data], primary_index:0 };
    return { _err: 'AI returned empty result. Try a clearer shot — point closer to the issue with good light.' };
  } catch (e) {
    return { _err: `Network error: ${e.message}` };
  }
}

async function submitIssue() {
  if (!primaryIssue) return;
  const btn = document.getElementById('submit-btn');
  btn.disabled = true; btn.textContent = t('submitting');

  try {
    const r = await fetch('/api/submit', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        issues: detectedIssues,
        primary_index: detectedIssues.indexOf(primaryIssue),
        lat: userLat, lng: userLng,
        area_estimate: userArea || primaryIssue.area_estimate || 'Delhi',
        user: getCurrentUser(),
        image: capturedImage || null,
      }),
    });
    const d = await r.json();

    if (d.error) {
      btn.disabled = false;
      btn.textContent = t('submit_btn');
      showSubmitError(d.error);
      return;
    }

    const issueId = d.id || `CAM-${Date.now()}`;
    saveToMyReports(issueId);
    speak('Issue submitted successfully to AreaPulse.', 'समस्या सफलतापूर्वक AreaPulse पर भेज दी गई।');
    showSuccess(issueId);
    setTimeout(loadNearby, 2000);

  } catch (e) {
    btn.disabled = false;
    btn.textContent = t('submit_btn');
    showSubmitError(`Network error: ${e.message}. Check your connection and try again.`);
  }
}

function showSubmitError(msg) {
  let errEl = document.getElementById('submit-error');
  if (!errEl) {
    errEl = document.createElement('div');
    errEl.id = 'submit-error';
    errEl.style.cssText = 'color:#B85042;font-size:13px;margin-top:8px;padding:10px 12px;background:#FDE8E8;border-radius:8px;';
    document.getElementById('submit-btn').insertAdjacentElement('afterend', errEl);
  }
  errEl.textContent = `⚠️ ${msg}`;
}

// ══════════════════════════════════════════════════════════
//  REPORT
// ══════════════════════════════════════════════════════════
function renderReport(allIssues, data) {
  const meta = ISSUE[data.issue_type] || ISSUE.other;
  const conf = data.confidence || 88;
  const lat  = (userLat || 28.6139).toFixed(6);
  const lng  = (userLng || 77.2090).toFixed(6);
  const sevClass = `sev-${data.severity || 'medium'}`;
  const hzColor  = data.hazard_level === 'high' ? '#B85042' : data.hazard_level === 'medium' ? '#B7770D' : '#2D6A4F';
  const localeStr = voiceLang === 'hi' ? 'hi-IN' : 'en-IN';
  const reportDate = new Date().toLocaleString(localeStr, { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });

  // Pick title/description in current language; fall back to English
  const displayTitle = (voiceLang === 'hi' && data.title_hi) ? data.title_hi : (data.title || labelFor(data.issue_type));
  const displayDesc  = (voiceLang === 'hi' && data.description_hi) ? data.description_hi : (data.description || '');

  const tabsHtml = allIssues.length > 1 ? `
    <div class="issue-tabs">
      ${allIssues.map((iss, idx) => {
        const m = ISSUE[iss.issue_type] || ISSUE.other;
        const active = iss === data ? 'active' : '';
        return `<button class="issue-tab ${active}" onclick="switchIssue(${idx})">
          <span>${m.emoji}</span> ${labelFor(iss.issue_type)}
          <span class="tab-sev sev-${iss.severity}">${(iss.severity||'')[0].toUpperCase()}</span>
        </button>`;
      }).join('')}
    </div>` : '';

  // Image (from captured frame)
  const imageHtml = capturedImage ? `
    <div class="rpt-image-card">
      <div class="rpt-section-lbl">${t('captured_photo')}</div>
      <img src="${capturedImage}" class="rpt-image" alt="Captured issue photo"/>
    </div>` : '';

  // NGOs
  const matchedNGOs = nearbyNGOs.filter(n => !n.tag || n.tag === data.issue_type || n.tag === 'other').slice(0, 3);
  const showNGOs = matchedNGOs.length ? matchedNGOs : nearbyNGOs.slice(0, 2);
  const ngoHtml = showNGOs.length ? `
    <div class="rpt-section-lbl">${t('nearby_ngos')}</div>
    ${showNGOs.map(n => `
      <div class="ngo-rpt-card">
        <div class="ngo-rpt-top">
          <div class="ngo-rpt-name">${esc(n.name)}</div>
          <span class="ngo-rpt-dist">${n.distance_km} km</span>
        </div>
        <div class="ngo-rpt-focus">${esc(n.focus || '')}</div>
        ${n.phone ? `<a class="ngo-rpt-phone" href="tel:${n.phone}">📞 ${n.phone}</a>` : ''}
      </div>`).join('')}` : '';

  // Authority contact
  const authInfo = AUTHORITY_CONTACTS[data.recommended_authority];
  const authHtml = authInfo ? `
    <div class="rpt-section-lbl">${t('contact_authority')}</div>
    <div class="auth-rpt-card">
      <div class="auth-rpt-name">${esc(data.recommended_authority)}</div>
      <a class="auth-rpt-phone" href="tel:${authInfo.phone}">📞 ${t('helpline')}: ${authInfo.phone}</a>
      <div class="auth-rpt-email">✉ ${authInfo.email}</div>
    </div>` : '';

  document.getElementById('report-inner').innerHTML = `
    <div class="back-row">
      <button class="back-btn" onclick="scanAgainFromReport()">${t('back')}</button>
      <span class="rpt-tag">${t('issue_report')} · ${reportDate}</span>
    </div>
    ${tabsHtml}
    <div class="rpt-hero">
      <div class="rpt-accent-bar" style="background:${meta.color}"></div>
      <div class="rpt-emoji">${meta.emoji}</div>
      <div>
        <div class="rpt-type">${labelFor(data.issue_type)}</div>
        <div class="rpt-title">${esc(displayTitle)}</div>
        <span class="sev-badge ${sevClass}">● ${t('sev_' + (data.severity || 'medium'))}</span>
      </div>
    </div>
    ${imageHtml}
    <div class="info-grid">
      <div class="icard">
        <div class="icard-lbl">${t('ai_confidence')}</div>
        <div class="icard-val">${conf}%</div>
        <div class="conf-bg"><div class="conf-fill" id="cbar"></div></div>
      </div>
      <div class="icard">
        <div class="icard-lbl">${t('hazard_level')}</div>
        <div class="icard-val" style="color:${hzColor}">${t(data.hazard_level || 'medium')}</div>
      </div>
      <div class="icard">
        <div class="icard-lbl">${t('authority')}</div>
        <div class="icard-val" style="font-size:12px;line-height:1.35">${esc(data.recommended_authority||'MCD')}</div>
      </div>
      <div class="icard">
        <div class="icard-lbl">${t('est_repair')}</div>
        <div class="icard-val" style="font-size:12px;line-height:1.35">${esc(data.estimated_repair_time||'3-7 days')}</div>
      </div>
    </div>
    <div class="desc-box">
      <div class="box-lbl">${t('ai_analysis')}</div>
      <div class="desc-txt">${esc(displayDesc)}</div>
    </div>
    <div class="loc-box">
      <div class="loc-pin">📍</div>
      <div>
        <div class="loc-area">${esc(userArea || data.area_estimate || 'Delhi')}</div>
        <div class="loc-coords">${lat}° N, ${lng}° E</div>
      </div>
    </div>
    ${ngoHtml}
    ${authHtml}
    <div class="rpt-reporter">${t('reported_by')} <strong>${esc(getCurrentUser())}</strong></div>
    <button class="btn-primary" id="submit-btn" onclick="submitIssue()">${t('submit_btn')}</button>
    <button class="btn-ghost" onclick="scanAgainFromReport()">${t('scan_another')}</button>
    <div style="height:32px"></div>
  `;

  requestAnimationFrame(() => setTimeout(() => {
    const bar = document.getElementById('cbar');
    if (bar) bar.style.width = conf + '%';
  }, 120));
}

function scanAgainFromReport() {
  isDetected = false;
  detectedIssues = [];
  primaryIssue = null;
  capturedImage = null;
  document.getElementById('detect-action-bar').classList.add('hidden');
  renderSidePanels();
  setStatus('🎯', t('point_camera'));
  showScreen('s-camera');
}

function switchIssue(idx) {
  primaryIssue = detectedIssues[idx];
  renderReport(detectedIssues, primaryIssue);
}

function showSuccess(id) {
  document.getElementById('success-id').textContent = `Issue ID: ${id}`;
  document.getElementById('success-title').textContent = t('submitted');
  document.getElementById('success-sub').textContent = t('saved_to_db');
  document.getElementById('view-link').href = `${window.AREAPULSE_URL}/my-reports`;
  document.getElementById('view-link').textContent = t('my_reports_on_ap');
  document.getElementById('success-scan-btn').textContent = t('scan_another');
  document.getElementById('success-ov').classList.remove('hidden');
}

// ══════════════════════════════════════════════════════════
//  NARRATE DETECTION
// ══════════════════════════════════════════════════════════
function narrateDetection(issues) {
  if (!issues.length) return;
  let txtEn, txtHi;
  if (issues.length === 1) {
    const i = issues[0];
    const meta = ISSUE[i.issue_type] || ISSUE.other;
    const sevHi = i.severity === 'high' ? 'गंभीर' : i.severity === 'medium' ? 'मध्यम' : 'हल्की';
    txtEn = `${meta.label} detected. ${i.severity} severity. Recommended authority: ${i.recommended_authority || 'MCD'}.`;
    txtHi = `${meta.label_hi} पाई गई। ${sevHi} समस्या। ${i.recommended_authority || 'MCD'} को सूचित करें।`;
  } else {
    const types = issues.map(i => (ISSUE[i.issue_type] || ISSUE.other).label).join(', ');
    const typesHi = issues.map(i => (ISSUE[i.issue_type] || ISSUE.other).label_hi).join(', ');
    txtEn = `${issues.length} civic issues detected: ${types}. Tap to review and submit.`;
    txtHi = `${issues.length} समस्याएं पाई गईं: ${typesHi}। देखें और रिपोर्ट करें।`;
  }
  speak(txtEn, txtHi);
}

// ══════════════════════════════════════════════════════════
//  OVERLAYS
// ══════════════════════════════════════════════════════════
function showNoDetection(msg) {
  document.getElementById('no-detect-msg').textContent = msg;
  document.getElementById('no-detect-ov').classList.remove('hidden');
  speak('No civic issue detected. Please scan again.', 'कोई समस्या नहीं मिली। दोबारा स्कैन करें।');
}
function dismissNoDetection() { document.getElementById('no-detect-ov').classList.add('hidden'); }

function showScreen(id) {
  ['s-login','s-camera','s-analyze','s-report'].forEach(s =>
    document.getElementById(s).classList.toggle('hidden', s !== id)
  );
}

function resetApp() {
  isDetected = false; detectedIssues = []; primaryIssue = null; capturedImage = null;
  clearTimeout(detectTimer);
  document.getElementById('success-ov').classList.add('hidden');
  document.getElementById('no-detect-ov').classList.add('hidden');
  document.getElementById('detect-action-bar').classList.add('hidden');
  document.getElementById('my-reports-panel').classList.add('hidden');
  setStatus(cameraReady ? '🎯' : '⚠️', cameraReady ? t('point_camera') : 'Camera required to scan');
  renderSidePanels();
  showScreen('s-camera');
}

function setStatus(ico, msg) {
  document.getElementById('status-ico').textContent = ico;
  document.getElementById('status-msg').textContent = msg;
}

function esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : ''; }