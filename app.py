"""
AreaPulse — Map-First Civic Reporting Platform
Full-screen interactive city map. AI vision + auto-classification + NGO routing.
Runs out of the box with seeded data. Optionally connects to Firebase + Groq.
"""
import os, time, json, base64
import urllib.request as _ureq
import json as _json
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import (
    init_db, insert_issue, get_issues, upvote_issue,
    get_all_ngos, get_nearby_ngos, get_areas, AREA_COORDS,
    insert_spam_issue, find_nearby_duplicate, is_rate_limited,
    calculate_sla, escalate_issue, get_issue_by_id,
    update_issue_status, get_issues_for_gov,
    log_duplicate_merge,
    SLA_HOURS, CROWD_ESCALATION_THRESHOLD,
)
from classifier import auto_classify, severity_from_text
import ai_engine
import email_sender

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'areapulse-dev-secret-2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# Initialize DB (Firebase if configured, else seeded in-memory)
init_db()

# Public config exposed to template
MAPTILER_KEY = os.environ.get('MAPTILER_KEY', '')
MAPTILER_STYLE = os.environ.get('MAPTILER_STYLE', 'hybrid')  # FR24-style satellite + labels overlay


# ═══════════════════════════════════════════════════════
#  TWILIO WHATSAPP INTEGRATION
# ═══════════════════════════════════════════════════════
# Outbound: ping citizens on issue status changes
# Inbound:  citizens text photos of civic issues; bot files reports
# Degrades gracefully when Twilio creds are missing.

def _wa_notify(to_phone, message):
    """
    Send a WhatsApp message via Twilio.
    Returns {ok, mode, detail} where mode is sent/simulated/skipped/error.
    """
    sid       = os.environ.get('TWILIO_ACCOUNT_SID', '')
    token     = os.environ.get('TWILIO_AUTH_TOKEN', '')
    from_num  = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')
    dry_run   = os.environ.get('WA_NOTIFY_DRY_RUN', '0') == '1'

    if not to_phone:
        return {'ok': False, 'mode': 'skipped', 'detail': 'no_phone'}
    dest = to_phone.strip()
    if not dest.startswith('whatsapp:'):
        if not dest.startswith('+'):
            dest = '+91' + dest.lstrip('+')  # India country code default
        dest = 'whatsapp:' + dest

    if dry_run or not (sid and token and from_num):
        print(f'[wa_notify] (simulated) -> {dest}: {message[:80]}...')
        return {'ok': True, 'mode': 'simulated', 'detail': 'twilio not configured'}

    try:
        import urllib.request, urllib.parse
        url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
        from_full = from_num if from_num.startswith('whatsapp:') else f'whatsapp:{from_num}'
        body = urllib.parse.urlencode({
            'From': from_full, 'To': dest, 'Body': message[:1550],
        }).encode()
        req = urllib.request.Request(url, data=body)
        creds = base64.b64encode(f'{sid}:{token}'.encode()).decode()
        req.add_header('Authorization', f'Basic {creds}')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=10) as r:
            payload = json.loads(r.read().decode())
        return {'ok': True, 'mode': 'sent', 'detail': payload.get('sid', '')}
    except Exception as e:
        print(f'[wa_notify] send failed: {e}')
        return {'ok': False, 'mode': 'error', 'detail': str(e)[:120]}


def _status_change_message(issue, new_status):
    """Compose WhatsApp message for issue status change."""
    verbs = {
        'acknowledged': 'has been *acknowledged*',
        'in_progress':  'is now *being worked on*',
        'resolved':     'has been marked *RESOLVED* ✓',
        'escalated':    'has been *escalated to a higher authority*',
        'open':         'is open',
    }
    verb = verbs.get(new_status, f'is now {new_status}')
    return (
        f"📢 *AreaPulse update*\n\n"
        f"Your report #AP-{issue.get('id')} "
        f"({(issue.get('tag') or 'issue').title()} in {issue.get('area') or 'Delhi'}) "
        f"{verb}.\n\n"
        f"Track this and nearby issues on the live map.\n"
        f"Thank you for helping improve our city. 🇮🇳"
    )


def _wa_twiml(*messages):
    """Wrap reply strings in Twilio TwiML XML."""
    from flask import Response
    body = '<?xml version="1.0" encoding="UTF-8"?><Response>'
    for m in messages:
        m_escaped = (m.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
        body += f'<Message>{m_escaped}</Message>'
    body += '</Response>'
    return Response(body, mimetype='application/xml')


# ═══════════════════════════════════════════════════════
#  GOV DASHBOARD CONFIG (Feature 2)
# ═══════════════════════════════════════════════════════
# Demo gov-officer accounts. PIN '0000' for all in demo mode.
# Each officer sees only issues tagged for their department.
# To add real users in production: replace this dict with a Firestore lookup.
GOV_ACCOUNTS = {
    'gov_rmc': {
        'pin': '0000', 'name': 'RMC Officer',
        'authority': 'Ranchi Municipal Corporation',
        'tags': ['pothole', 'garbage', 'sewage', 'streetlight', 'tree', 'other'],
    },
    'gov_water': {
        'pin': '0000', 'name': 'Water Board Officer',
        'authority': 'Drinking Water & Sanitation Dept (Jharkhand)',
        'tags': ['water'],
    },
    'gov_electricity': {
        'pin': '0000', 'name': 'Electricity Officer',
        'authority': 'Jharkhand Bijli Vitran Nigam (JBVNL)',
        'tags': ['electricity'],
    },
    'gov_traffic': {
        'pin': '0000', 'name': 'Traffic Police',
        'authority': 'Ranchi Traffic Police',
        'tags': ['traffic', 'noise'],
    },
}


# ═══════════════════════════════════════════════════════
#  ROUTES — PAGES
# ═══════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════
#  DUPLICATE DETECTION DEBUG ENDPOINT
# ═══════════════════════════════════════════════════════
@app.route('/api/debug/dup-check')
def debug_dup_check():
    """
    Test what the duplicate detector would do without actually submitting.
    Usage: /api/debug/dup-check?lat=28.6514&lng=77.1907&tag=pothole

    Returns the match result + any candidates found. Useful for verifying
    duplicate detection works without polluting the issues collection.
    """
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
    except (TypeError, ValueError):
        return jsonify({
            'error': 'pass ?lat=...&lng=...&tag=...',
            'example': '/api/debug/dup-check?lat=28.6514&lng=77.1907&tag=pothole',
        }), 400

    tag = request.args.get('tag', 'pothole').strip()
    radius = int(request.args.get('radius', '50'))
    days = int(request.args.get('days', '7'))

    from database import _state
    dup = find_nearby_duplicate(lat, lng, tag, within_meters=radius, within_days=days)

    return jsonify({
        'query':            {'lat': lat, 'lng': lng, 'tag': tag, 'radius_m': radius, 'days': days},
        'mode':             _state.get('mode'),
        'matched':          dup is not None,
        'matched_issue_id': dup.get('id') if dup else None,
        'distance_meters':  round(dup.get('_distance_meters', 0), 1) if dup else None,
        'matched_description': (dup.get('description', '')[:100] if dup else None),
    })


@app.route('/')
def home():
    """Single page — the map IS the app."""
    return render_template(
        'index.html',
        current_user=session.get('user'),
        maptiler_key=MAPTILER_KEY,
        maptiler_style=MAPTILER_STYLE,
        ai_available=ai_engine.is_available(),
        email_available=email_sender.is_available(),
        wa_number=os.environ.get('TWILIO_WHATSAPP_NUMBER', '').replace('whatsapp:', '').replace('+', ''),
        wa_join_code=os.environ.get('TWILIO_SANDBOX_CODE', ''),
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        pin  = (request.form.get('pin') or '').strip()
        if not name or len(name) < 2:
            return render_template('login.html', error='Enter a name (min 2 chars)')
        if len(name) > 50:
            return render_template('login.html', error='Name too long (max 50 chars)')

        # GOV-account detection: if name matches a configured gov username,
        # require its PIN and route to the gov dashboard.
        gov = GOV_ACCOUNTS.get(name.lower())
        if gov:
            if pin != gov.get('pin'):
                return render_template('login.html', error='Incorrect PIN for government account', gov_attempt=name)
            session['user'] = gov['name']
            session['gov_role'] = {
                'username':  name.lower(),
                'authority': gov['authority'],
                'tags':      gov['tags'],
            }
            return redirect(url_for('gov_dashboard'))

        # Regular citizen login
        session.pop('gov_role', None)
        session['user'] = name
        return redirect(url_for('home'))

    if 'user' in session:
        return redirect(url_for('gov_dashboard') if session.get('gov_role') else url_for('home'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('gov_role', None)
    session.pop('google_email', None)
    session.pop('oauth_state', None)
    return redirect(url_for('login'))


# ═══════════════════════════════════════════════════════
#  GOOGLE OAUTH 2.0
# ═══════════════════════════════════════════════════════
# Env vars required:
#   GOOGLE_CLIENT_ID      — from Google Cloud Console
#   GOOGLE_CLIENT_SECRET  — from Google Cloud Console
#   GOOGLE_REDIRECT_URI   — optional override (e.g. on Render behind HTTPS proxy)
#                           default: auto-built from request URL
#
# Google Cloud Console setup:
#   1. APIs & Services → Credentials → Create OAuth 2.0 Client (Web application)
#   2. Authorised redirect URI: https://areapulse-a1k2.onrender.com/auth/google/callback
#   3. Copy Client ID + Secret → Render → Environment
# ═══════════════════════════════════════════════════════

_GOOGLE_AUTH_URL     = 'https://accounts.google.com/o/oauth2/v2/auth'
_GOOGLE_TOKEN_URL    = 'https://oauth2.googleapis.com/token'
_GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'


@app.route('/auth/google')
def auth_google():
    """Step 1 — redirect the browser to Google's consent screen."""
    import secrets as _secrets
    import urllib.parse as _uparse

    client_id = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    if not client_id:
        return redirect(url_for('login') + '?error=' + _uparse.quote(
            'Google Sign-In is not configured. Set GOOGLE_CLIENT_ID in environment variables.'))

    state = _secrets.token_urlsafe(20)
    session['oauth_state'] = state

    redirect_uri = (
        os.environ.get('GOOGLE_REDIRECT_URI', '').strip()
        or url_for('auth_google_callback', _external=True)
    )
    # Ensure HTTPS on Render (behind a TLS-terminating proxy)
    if redirect_uri.startswith('http://') and 'onrender.com' in redirect_uri:
        redirect_uri = 'https://' + redirect_uri[7:]

    auth_url = _GOOGLE_AUTH_URL + '?' + _uparse.urlencode({
        'client_id':     client_id,
        'redirect_uri':  redirect_uri,
        'response_type': 'code',
        'scope':         'openid email profile',
        'state':         state,
        'access_type':   'online',
        'prompt':        'select_account',
    })
    return redirect(auth_url)


@app.route('/auth/google/callback')
def auth_google_callback():
    """Step 2 — exchange code → tokens → user info → set session."""
    import urllib.parse as _uparse
    import requests as _rq

    client_id     = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()

    # Error returned by Google (e.g. user clicked Cancel)
    error = request.args.get('error', '')
    if error:
        return redirect(url_for('login') + '?error=' + _uparse.quote(
            f'Google sign-in cancelled: {error}'))

    code  = request.args.get('code', '')
    state = request.args.get('state', '')

    if not code:
        return redirect(url_for('login') + '?error=' + _uparse.quote(
            'No authorisation code received from Google.'))

    # CSRF guard
    if not state or state != session.pop('oauth_state', None):
        return redirect(url_for('login') + '?error=' + _uparse.quote(
            'Invalid OAuth state. Please try again.'))

    redirect_uri = (
        os.environ.get('GOOGLE_REDIRECT_URI', '').strip()
        or url_for('auth_google_callback', _external=True)
    )
    if redirect_uri.startswith('http://') and 'onrender.com' in redirect_uri:
        redirect_uri = 'https://' + redirect_uri[7:]

    # Exchange authorisation code for access token
    try:
        token_resp = _rq.post(_GOOGLE_TOKEN_URL, data={
            'code':          code,
            'client_id':     client_id,
            'client_secret': client_secret,
            'redirect_uri':  redirect_uri,
            'grant_type':    'authorization_code',
        }, timeout=10)
        token_resp.raise_for_status()
        token_data = token_resp.json()
    except Exception as exc:
        print(f'[google_oauth] token exchange failed: {exc}')
        return redirect(url_for('login') + '?error=' + _uparse.quote(
            'Failed to exchange token with Google. Please try again.'))

    access_token = token_data.get('access_token', '')
    if not access_token:
        return redirect(url_for('login') + '?error=' + _uparse.quote(
            'Google did not return an access token.'))

    # Fetch the authenticated user's profile
    try:
        info_resp = _rq.get(_GOOGLE_USERINFO_URL,
                            headers={'Authorization': f'Bearer {access_token}'},
                            timeout=10)
        info_resp.raise_for_status()
        userinfo = info_resp.json()
    except Exception as exc:
        print(f'[google_oauth] userinfo fetch failed: {exc}')
        return redirect(url_for('login') + '?error=' + _uparse.quote(
            'Could not retrieve your Google profile. Please try again.'))

    # Build a display name: prefer full name, fall back to email prefix
    name = (
        (userinfo.get('name') or '').strip()
        or (userinfo.get('email') or '').split('@')[0]
        or 'Google User'
    )

    # Log in — same session structure as the regular citizen form
    session.pop('gov_role', None)
    session['user']         = name
    session['google_email'] = userinfo.get('email', '')

    print(f'[google_oauth] ✓ signed in: {name} <{session["google_email"]}>')
    return redirect(url_for('home'))


# ═══════════════════════════════════════════════════════
#  ROUTES — ISSUE API
# ═══════════════════════════════════════════════════════

@app.route('/issues')
def issues_api():
    tag    = (request.args.get('tag')    or '').strip() or None
    status = (request.args.get('status') or '').strip() or None
    issues = get_issues(tag=tag, status=status)

    # ────── Feature 3: SLA AUTO-ESCALATION ──────
    # Compute SLA fields for each issue + auto-escalate any whose SLA is breached
    enriched = []
    for i in issues:
        sla = calculate_sla(i)
        # Auto-escalate if overdue and not yet escalated and not resolved
        if (sla['sla_state'] == 'overdue'
            and not i.get('escalated')
            and i.get('status') != 'resolved'):
            if escalate_issue(int(i.get('id')), reason='sla_breach'):
                i['escalated'] = True
                i['status'] = 'escalated'
        i.update(sla)
        enriched.append(i)
    return jsonify(enriched)


@app.route('/report', methods=['POST'])
def report_api():
    """
    Citizen report submission.

    Three possible outcomes — each writes to a distinct Firestore collection:
    1. SPAM     → spam_issues       (flagged as spam / abuse / test / rate-limited)
    2. MERGED   → duplicate_reports + upvote on original issue
    3. NEW      → issues            (unique report, new pin on map)

    Errors at any step surface as 500 with the underlying Firestore error.
    """
    user        = (request.form.get('user')        or 'anonymous').strip() or 'anonymous'
    description = (request.form.get('description') or '').strip()
    area        = (request.form.get('area')        or 'Delhi').strip()
    severity    = (request.form.get('severity')    or 'medium').strip()
    landmark    = (request.form.get('landmark')    or '').strip()
    contact     = (request.form.get('contact')     or '').strip()

    print(f'[report] incoming: user={user!r} area={area!r} desc={description[:60]!r}')

    if len(description) < 10:
        return jsonify({'error': 'Description must be at least 10 characters'}), 400

    # Coordinates: posted lat/lng if available, else area centroid
    try:
        lat = float(request.form.get('lat')) if request.form.get('lat') else None
        lng = float(request.form.get('lng')) if request.form.get('lng') else None
    except (TypeError, ValueError):
        lat = lng = None
    if (lat is None or lng is None) and area in AREA_COORDS:
        lat, lng = AREA_COORDS[area]

    # AI auto-classification of tag
    tag = auto_classify(description)

    # ════════════ 1. SPAM DETECTION ════════════
    rate_block = is_rate_limited(user)
    spam_result = ai_engine.classify_spam(description)
    spam_verdict = spam_result.get('verdict', 'real')

    if rate_block or spam_verdict != 'real':
        verdict = 'rate_limit' if rate_block else spam_verdict
        reason  = 'rate_limit_flood' if rate_block else spam_result.get('reason', '')
        try:
            spam_doc_id = insert_spam_issue(
                user=user, description=description, tag=tag, severity=severity, area=area,
                lat=lat, lng=lng, image=None,
                spam_verdict=verdict, spam_reason=reason,
                spam_confidence=spam_result.get('confidence', 0),
            )
            print(f'[report] → spam_issues/{spam_doc_id} (verdict={verdict})')
        except Exception as e:
            print(f'[report] ✗ spam write failed: {e}')
            return jsonify({
                'error': 'Failed to save filtered report',
                'detail': f'{type(e).__name__}: {e}',
                '_status': 'spam_write_failed',
            }), 500

        return jsonify({
            'status':         'spam_filtered',
            'spam_verdict':   verdict,
            'spam_reason':    reason,
            'spam_doc_id':    spam_doc_id,
            'collection':     'spam_issues',
            'message':        f'Filtered as {verdict}: {reason}',
        })

    # Image upload → base64 data URL (capped at 2 MB)
    image_data = None
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename:
            raw = f.read()
            if 0 < len(raw) < 2 * 1024 * 1024:
                image_data = f"data:{f.mimetype or 'image/jpeg'};base64,{base64.b64encode(raw).decode()}"
                print(f'[report] image attached: {len(raw)} bytes')

    # ════════════ 2. DUPLICATE DETECTION ════════════
    if lat and lng:
        dup = find_nearby_duplicate(lat, lng, tag, within_meters=50, within_days=7)
        if dup:
            dup_id = int(dup.get('id'))
            distance_m = dup.get('_distance_meters', 0)

            # Log the merge event to duplicate_reports collection
            try:
                merge_doc_id = log_duplicate_merge(
                    original_issue_id=dup_id,
                    duplicate_user=user,
                    duplicate_description=description,
                    duplicate_tag=tag,
                    duplicate_severity=severity,
                    lat=lat, lng=lng,
                    distance_meters=distance_m,
                    match_reason='geographic_radius',
                )
                print(f'[report] → duplicate_reports/{merge_doc_id} merged with #AP-{dup_id} ({distance_m:.1f}m)')
            except Exception as e:
                print(f'[report] ⚠ duplicate log write failed: {e}')
                merge_doc_id = None

            # Add this user as an upvoter on the original
            upvote_issue(dup_id, user)

            return jsonify({
                'status':         'merged',
                'id':             dup_id,
                'tag':            tag,
                'points_earned':  2,
                'collection':     'duplicate_reports',
                'merge_doc_id':   merge_doc_id,
                'distance_meters': round(distance_m, 1),
                'merged_with':    dup_id,
                'message':        f'Already reported as #AP-{dup_id} ({distance_m:.0f}m away). Added your voice (+1 corroboration).',
            })

    # ════════════ 3. NEW ISSUE ════════════
    try:
        issue_id = insert_issue(
            user=user, area=area, description=description, severity=severity, tag=tag,
            landmark=landmark, contact=contact, lat=lat, lng=lng, image=image_data,
        )
        print(f'[report] → issues/#{issue_id} (NEW) tag={tag}')
    except Exception as e:
        err_msg = f'{type(e).__name__}: {e}'
        print(f'[report] ✗ insert failed: {err_msg}')
        return jsonify({
            'error': 'Failed to save report to database',
            'detail': err_msg,
            '_status': 'db_error',
        }), 500

    nearby = get_nearby_ngos(lat, lng, tag, limit=3) if (lat and lng) else []

    return jsonify({
        'status':        'ok',
        'id':            issue_id,
        'tag':           tag,
        'points_earned': 5,
        'collection':    'issues',
        'nearby_ngos':   nearby,
    })


# ═══════════════════════════════════════════════════════
#  FIRESTORE HEALTH CHECK
# ═══════════════════════════════════════════════════════
@app.route('/api/health/firestore')
def firestore_health():
    """Round-trip Firestore write+read test, plus counts of all collections."""
    from database import _state
    import time as _t
    info = {
        'mode': _state.get('mode', 'unknown'),
        'firestore_client': bool(_state.get('fs_db')),
    }
    if _state.get('mode') != 'firebase':
        info['status'] = 'in_memory_only'
        info['message'] = 'Firebase not configured — running in memory mode'
        return jsonify(info), 200

    try:
        t0 = _t.time()
        test_ref = _state['fs_db'].collection('_health').document('ping')
        test_ref.set({'ts': _t.time(), 'test': 'ok'})
        snap = test_ref.get()
        info['write_ok']     = True
        info['read_ok']      = snap.exists
        info['roundtrip_ms'] = round((_t.time() - t0) * 1000, 1)

        # Count all 3 collections
        info['issues_count']            = len(list(_state['fs_db'].collection('issues').limit(500).stream()))
        info['spam_issues_count']       = len(list(_state['fs_db'].collection('spam_issues').limit(500).stream()))
        info['duplicate_reports_count'] = len(list(_state['fs_db'].collection('duplicate_reports').limit(500).stream()))
        info['ngos_count']              = len(list(_state['fs_db'].collection('ngos').limit(500).stream()))
        info['status'] = 'ok'
        return jsonify(info), 200
    except Exception as e:
        info['status'] = 'error'
        info['error']  = f'{type(e).__name__}: {e}'
        return jsonify(info), 500


@app.route('/upvote/<int:issue_id>', methods=['POST'])
def upvote_api(issue_id):
    data = request.get_json(silent=True) or {}
    user = (data.get('user') or 'anonymous').strip() or 'anonymous'
    action = upvote_issue(issue_id, user)

    # ────── Feature 6: CROWD-ESCALATION ──────
    # After upvote, check if total upvotes crossed the threshold → auto-escalate
    escalated_now = False
    if action == 'added':
        issue = get_issue_by_id(issue_id)
        if issue and not issue.get('escalated') and issue.get('upvotes', 0) >= CROWD_ESCALATION_THRESHOLD:
            escalated_now = escalate_issue(issue_id, reason='crowd_consensus')

    return jsonify({
        'status': 'ok',
        'action': action,
        'escalated_now': escalated_now,
    })


@app.route('/areas')
def areas_api():
    return jsonify(get_areas())


# ═══════════════════════════════════════════════════════
#  GOVERNMENT DASHBOARD (Feature 2)
# ═══════════════════════════════════════════════════════
@app.route('/gov')
def gov_dashboard():
    """Government officer view — only issues for their department."""
    gov = session.get('gov_role')
    if not gov:
        return redirect(url_for('login'))
    issues = get_issues_for_gov(tags=gov.get('tags'))
    # Stats for the header KPIs
    stats = {
        'total':       len(issues),
        'overdue':     sum(1 for i in issues if i.get('sla_state') == 'overdue'),
        'soon':        sum(1 for i in issues if i.get('sla_state') == 'soon'),
        'resolved':    sum(1 for i in issues if i.get('status') == 'resolved'),
        'in_progress': sum(1 for i in issues if i.get('status') == 'in_progress'),
        'open':        sum(1 for i in issues if i.get('status') == 'open'),
        'escalated':   sum(1 for i in issues if i.get('status') == 'escalated'),
    }
    return render_template('gov.html', issues=issues, stats=stats, gov=gov,
                           current_user=session.get('user'))


@app.route('/gov/update-status/<int:issue_id>', methods=['POST'])
def gov_update_status(issue_id):
    """Officer changes an issue's status. Updates the audit trail."""
    gov = session.get('gov_role')
    if not gov:
        return jsonify({'error': 'Not authorised'}), 401

    data = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').lower().strip()
    note       = (data.get('note') or '').strip()

    # Verify the officer is allowed to touch this issue's tag
    issue = get_issue_by_id(issue_id)
    if not issue:
        return jsonify({'error': f'Issue #{issue_id} not found'}), 404
    issue_tag = (issue.get('tag') or 'other').lower()
    if gov.get('tags') and issue_tag not in [t.lower() for t in gov['tags']]:
        return jsonify({'error': f'Your department does not handle "{issue_tag}" issues'}), 403

    updated = update_issue_status(issue_id, new_status, updated_by=gov['username'], note=note)
    if not updated:
        return jsonify({'error': f'Invalid status "{new_status}"'}), 400

    # ────── WhatsApp Status Ping ──────
    # Notify the citizen who filed the report (if they left a phone number)
    notify = {'mode': 'skipped'}
    if new_status in ('acknowledged', 'in_progress', 'resolved', 'escalated') and updated.get('contact'):
        contact = updated['contact'].strip()
        if any(ch.isdigit() for ch in contact) and '@' not in contact:
            notify = _wa_notify(contact, _status_change_message(updated, new_status))

    return jsonify({
        'status':         'ok',
        'issue_id':       issue_id,
        'new_status':     new_status,
        'updated_by':     gov['username'],
        'notify':         notify,
    })


# ═══════════════════════════════════════════════════════
#  PUBLIC STATS PAGE (Feature 8)
# ═══════════════════════════════════════════════════════
@app.route('/stats')
def public_stats():
    """Anonymous, read-only metrics dashboard. No login required."""
    issues = get_issues(limit=500)
    now = time.time()

    by_tag = {}
    by_area = {}
    by_severity = {'high': 0, 'medium': 0, 'low': 0}
    by_status = {'open': 0, 'acknowledged': 0, 'in_progress': 0, 'resolved': 0, 'escalated': 0}
    resolution_durations_hr = []
    overdue_count = 0
    last_7d_count = 0

    for i in issues:
        tag  = i.get('tag') or 'other'
        area = i.get('area') or 'Delhi'
        sev  = i.get('severity') or 'medium'
        stat = i.get('status') or 'open'

        by_tag[tag] = by_tag.get(tag, 0) + 1
        by_area[area] = by_area.get(area, 0) + 1
        if sev in by_severity:  by_severity[sev]  += 1
        if stat in by_status:   by_status[stat]   += 1

        sla = calculate_sla(i)
        if sla['sla_state'] == 'overdue': overdue_count += 1

        ts = i.get('timestamp') or now
        if now - ts < 7 * 86400: last_7d_count += 1

        if stat == 'resolved' and i.get('resolved_at') and ts:
            hours = (i['resolved_at'] - ts) / 3600
            if 0 < hours < 30 * 24:  # sanity cap at 30 days
                resolution_durations_hr.append(hours)

    total = len(issues)
    resolved = by_status['resolved']
    resolution_rate = round(resolved / total * 100, 1) if total else 0
    avg_resolution_hr = round(sum(resolution_durations_hr) / len(resolution_durations_hr), 1) \
                          if resolution_durations_hr else None
    sla_breach_rate = round(overdue_count / total * 100, 1) if total else 0

    top_areas = sorted(by_area.items(), key=lambda x: -x[1])[:10]
    tag_list  = sorted(by_tag.items(),  key=lambda x: -x[1])

    # By-department resolution rate
    dept_perf = []
    for tag, count in tag_list:
        dept_resolved = sum(1 for i in issues if i.get('tag') == tag and i.get('status') == 'resolved')
        dept_perf.append({
            'tag':           tag,
            'total':         count,
            'resolved':      dept_resolved,
            'resolution_rate': round(dept_resolved / count * 100, 1) if count else 0,
        })

    return render_template('stats.html',
        total=total,
        resolved=resolved,
        overdue=overdue_count,
        last_7d=last_7d_count,
        resolution_rate=resolution_rate,
        avg_resolution_hr=avg_resolution_hr,
        sla_breach_rate=sla_breach_rate,
        by_severity=by_severity,
        by_status=by_status,
        tag_list=tag_list,
        top_areas=top_areas,
        dept_perf=dept_perf,
        max_tag_count=max((c for _, c in tag_list), default=1),
        max_area_count=max((c for _, c in top_areas), default=1),
    )


# ═══════════════════════════════════════════════════════
#  ROUTES — NGO API
# ═══════════════════════════════════════════════════════

@app.route('/ngo/all')
def ngo_all_api():
    return jsonify({'ngos': get_all_ngos()})


@app.route('/ngo/nearby')
def ngo_nearby_api():
    try:
        lat = float(request.args.get('lat', 28.6139))
        lng = float(request.args.get('lng', 77.2090))
    except (TypeError, ValueError):
        lat, lng = 28.6139, 77.2090
    tag = (request.args.get('tag') or '').strip() or None
    return jsonify({'ngos': get_nearby_ngos(lat, lng, tag, limit=5)})


# ═══════════════════════════════════════════════════════
#  ROUTES — AI
# ═══════════════════════════════════════════════════════

@app.route('/ai/analyze-image', methods=['POST'])
def ai_analyze_image():
    """Groq Llama-4-Scout vision → classifies civic issue from photo."""
    data = request.get_json(silent=True) or {}
    b64  = (data.get('image') or '').strip()
    mime = data.get('mime_type', 'image/jpeg')
    if not b64:
        return jsonify({'error': 'No image provided'}), 400
    result = ai_engine.analyze_image(b64, mime)
    if 'error' in result:
        return jsonify(result), 500 if result.get('_status') == 'server_error' else 503
    return jsonify(result)


@app.route('/ai/ask', methods=['POST'])
def ai_ask():
    """Free-form Q&A about Delhi civic issues."""
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    context_issues = get_issues(limit=20)
    answer = ai_engine.ask_question(question, context_issues)
    return jsonify(answer)


@app.route('/ai/insights')
def ai_insights():
    """Summary stats + AI commentary on the current issue landscape."""
    issues = get_issues(limit=200)
    by_tag = {}
    by_severity = {'high': 0, 'medium': 0, 'low': 0}
    by_status = {}
    for i in issues:
        by_tag[i.get('tag', 'other')] = by_tag.get(i.get('tag', 'other'), 0) + 1
        sev = i.get('severity', 'medium')
        if sev in by_severity: by_severity[sev] += 1
        st = i.get('status', 'open')
        by_status[st] = by_status.get(st, 0) + 1
    return jsonify({
        'total': len(issues),
        'by_tag': by_tag,
        'by_severity': by_severity,
        'by_status': by_status,
        'ai_summary': ai_engine.summarize_landscape(by_tag, by_severity, by_status) if ai_engine.is_available() else None,
    })


@app.route('/ai/health')
def ai_health():
    return jsonify({
        'ai_available':    ai_engine.is_available(),
        'email_available': email_sender.is_available(),
        'provider':        ai_engine.provider_name(),
        'model':           ai_engine.model_name(),
    })


# ═══════════════════════════════════════════════════════
#  ROUTES — COMPLAINT LETTER + EMAIL
# ═══════════════════════════════════════════════════════

def _find_issue(issue_id):
    """Locate a single issue by id from current store."""
    for i in get_issues(limit=500):
        if int(i.get('id', -1)) == int(issue_id):
            return i
    return None


@app.route('/ai/draft-dispatch/<int:issue_id>', methods=['GET', 'POST'])
def ai_draft_dispatch(issue_id):
    """
    Flat format consumed by issues.html and my_issues.html JS:
      {llm_drafted, recipient_name, recipient_email, recipient_phone, subject, body}
    """
    issue = _find_issue(issue_id)
    if not issue:
        return jsonify({'error': f'Issue #{issue_id} not found'}), 404

    data     = request.get_json(silent=True) or {}
    citizen  = (data.get('citizen_name') or data.get('citizen') or
                session.get('user') or issue.get('user') or 'Concerned Citizen').strip()
    language = (data.get('language') or 'english').strip().lower()

    drafted   = ai_engine.draft_complaint(issue, citizen_name=citizen, language=language)
    authority = drafted.get('authority') or ai_engine.get_authority(issue.get('tag', 'other'))
    source    = (drafted.get('source') or '').lower()

    return jsonify({
        'llm_drafted':     ('groq' in source) or ('llama' in source),
        'recipient_name':  authority.get('name',  'Local Authority'),
        'recipient_email': authority.get('email', ''),
        'recipient_phone': authority.get('phone', ''),
        'subject':         drafted.get('subject', ''),
        'body':            drafted.get('body_text', '') or drafted.get('body_html', ''),
        'source':          source or 'template',
    })


@app.route('/ai/draft-complaint/<int:issue_id>', methods=['GET', 'POST'])
def ai_draft_complaint(issue_id):
    """Generate a formal complaint letter for an issue."""
    issue = _find_issue(issue_id)
    if not issue:
        return jsonify({'error': f'Issue #{issue_id} not found'}), 404

    data = request.get_json(silent=True) or {}
    citizen = (data.get('citizen_name') or session.get('user') or issue.get('user') or 'Concerned Citizen').strip()
    language = (data.get('language') or 'english').strip().lower()

    drafted = ai_engine.draft_complaint(issue, citizen_name=citizen, language=language)
    return jsonify({
        'status':   'ok',
        'issue_id': issue_id,
        'subject':  drafted['subject'],
        'body_text': drafted['body_text'],
        'body_html': drafted['body_html'],
        'authority': drafted['authority'],
        'source':   drafted.get('source', 'template'),
    })


# ────── Feature 5: PDF EXPORT (print-to-PDF route) ──────
@app.route('/complaint-print/<int:issue_id>')
def complaint_print(issue_id):
    """
    Returns a print-optimized HTML page of the complaint letter.
    User opens it in a new tab → browser print dialog → Save as PDF.
    Works on every browser, no server-side PDF library needed.
    """
    issue = _find_issue(issue_id)
    if not issue:
        return f"<h1>Issue #{issue_id} not found</h1>", 404

    citizen = session.get('user') or issue.get('user') or 'Concerned Citizen'
    drafted = ai_engine.draft_complaint(issue, citizen_name=citizen)
    sla = calculate_sla(issue)

    return render_template('complaint_print.html',
        issue=issue,
        subject=drafted['subject'],
        body_text=drafted['body_text'],
        authority=drafted['authority'],
        citizen=citizen,
        sla=sla,
        today=time.strftime('%d %B %Y'),
    )


@app.route('/email/send-complaint/<int:issue_id>', methods=['POST'])
def email_send_complaint(issue_id):
    """Dispatch the complaint letter via Resend."""
    if not email_sender.is_available():
        return jsonify({'error': 'Email not configured. Set RESEND_API_KEY in .env.'}), 503

    issue = _find_issue(issue_id)
    if not issue:
        return jsonify({'error': f'Issue #{issue_id} not found'}), 404

    data = request.get_json(silent=True) or {}
    subject   = (data.get('subject')   or '').strip()
    body_html = (data.get('body_html') or '').strip()
    body_text = (data.get('body_text') or '').strip()
    to_email  = (data.get('to_email')  or '').strip()
    reply_to  = (data.get('reply_to')  or '').strip() or None

    if not subject or (not body_html and not body_text):
        return jsonify({'error': 'Subject and body are required'}), 400

    if not to_email:
        authority = ai_engine.get_authority(issue.get('tag', 'other'))
        to_email = authority['email']

    # Demo override: if DEMO_RECIPIENT_EMAIL is set, ALWAYS send there.
    # Resend free tier without a verified domain can only deliver to
    # your verified Resend account email — this routes every complaint to your inbox.
    demo_override = os.environ.get('DEMO_RECIPIENT_EMAIL', '').strip()
    if demo_override:
        original_to = to_email
        to_email = demo_override
        if not subject.startswith('[DEMO'):
            subject = f'[DEMO → {original_to}] {subject}'

    if body_html and not body_text:
        body_text = body_html  # cheap fallback

    # Attach issue photo if present
    attachments = []
    image = issue.get('image') or ''
    if image.startswith('data:'):
        try:
            header, b64 = image.split(',', 1)
            mime = header.split(';')[0].replace('data:', '')
            ext = 'jpg' if 'jpeg' in mime else (mime.split('/')[-1] or 'jpg')
            attachments.append({
                'filename':     f'issue_{issue_id}.{ext}',
                'content_b64':  b64,
                'content_type': mime,
            })
        except Exception:
            pass

    result = email_sender.send_complaint(
        to_email=to_email, subject=subject,
        body_html=body_html or f'<pre>{body_text}</pre>',
        body_text=body_text or None,
        attachments=attachments or None,
        reply_to=reply_to,
    )

    if result.get('error'):
        status = 503 if result.get('_status') == 'not_configured' else 500
        return jsonify(result), status

    return jsonify({
        'status':     'ok',
        'message_id': result.get('id', ''),
        'to':         to_email,
        'subject':    subject,
    })


def _reverse_geocode(lat, lng):
    try:
        import urllib.request as _ureq
        url = f'https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=14'
        req = _ureq.Request(url, headers={'User-Agent': 'AreaPulse/1.0'})
        with _ureq.urlopen(req, timeout=6) as r:
            addr = json.loads(r.read()).get('address', {})
        return (addr.get('suburb') or addr.get('neighbourhood') or
                addr.get('city_district') or addr.get('town') or 'Delhi')
    except Exception:
        return 'Delhi'

# ═══════════════════════════════════════════════════════
#  ROUTES — WHATSAPP INBOUND BOT (Twilio webhook)
# ═══════════════════════════════════════════════════════
# Citizens text photos of civic issues to the AreaPulse WhatsApp number.
# Bot uses AI vision to classify, asks for confirmation, creates the issue.
# Twilio webhook URL → https://areapulse-a1k2.onrender.com/whatsapp
# ══════════════════════════════════════════════════════════
# WHATSAPP BOT  —  Twilio webhook
# Env vars needed: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
# Webhook URL   : POST /whatsapp
# Status URL    : POST /whatsapp/status
#
# Conversation flow:
#   1. User sends photo  → AI analyzes → bot asks YES / NO
#   2. User replies YES  → issue saved to Firebase → link sent
#   3. User replies NO   → cancelled
#   4. User shares location pin → updates GPS on pending issue
# ══════════════════════════════════════════════════════════

_WA_SESSIONS: dict = {}   # phone → session data
_WA_TTL      = 600        # session timeout in seconds

_SEV_EMOJI = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
_TAG_EMOJI = {
    'pothole': '🕳', 'garbage': '🗑', 'water': '💧',
    'streetlight': '💡', 'sewage': '🚧', 'electricity': '⚡',
    'traffic': '🚦', 'tree': '🌳', 'noise': '📢', 'other': '⚠️',
}


def _wa_twiml(*messages):
    """Return minimal TwiML XML with one or more <Message> nodes."""
    parts = ['<?xml version="1.0" encoding="UTF-8"?><Response>']
    for m in messages:
        safe = str(m).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        parts.append(f'<Message>{safe}</Message>')
    parts.append('</Response>')
    return ''.join(parts), 200, {'Content-Type': 'text/xml'}


def _wa_prune():
    now = time.time()
    for k in [k for k, v in _WA_SESSIONS.items() if now - v.get('ts', 0) > _WA_TTL]:
        del _WA_SESSIONS[k]


def _wa_download_image(url):
    """Use requests so Authorization header survives the Twilio CDN redirect."""
    import requests as _rq
    sid   = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
    token = os.environ.get('TWILIO_AUTH_TOKEN', '').strip()
    auth  = (sid, token) if (sid and token) else None
    resp  = _rq.get(url, auth=auth, timeout=20, allow_redirects=True)
    print(f'[wa_dl] HTTP {resp.status_code} · {len(resp.content)} bytes · auth={"yes" if auth else "NO"}')
    resp.raise_for_status()
    ct = resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
    return resp.content, ct


def _wa_reverse_geocode(lat, lng):
    try:
        url = (f'https://nominatim.openstreetmap.org/reverse'
               f'?format=json&lat={lat}&lon={lng}&zoom=14')
        req = _ureq.Request(url, headers={'User-Agent': 'AreaPulse/1.0'})
        with _ureq.urlopen(req, timeout=6) as r:
            addr = _json.loads(r.read()).get('address', {})
        return (addr.get('suburb') or addr.get('neighbourhood') or
                addr.get('city_district') or addr.get('town') or 'Delhi')
    except Exception:
        return 'Delhi'


def _wa_extract_issue(result):
    """Normalise both old single-dict and new issues-array AI response."""
    if not isinstance(result, dict):
        return None
    if 'issues' in result:
        arr = result['issues']
        return arr[0] if arr else None
    if result.get('tag') or result.get('issue_type') or result.get('category'):
        return result
    return None


@app.route('/whatsapp', methods=['POST'])
def whatsapp():
    _wa_prune()

    from_num  = request.form.get('From', '')
    body      = (request.form.get('Body') or '').strip()
    num_media = int(request.form.get('NumMedia', 0))
    media_url = request.form.get('MediaUrl0', '')
    lat_str   = request.form.get('Latitude', '')
    lng_str   = request.form.get('Longitude', '')
    phone     = from_num.replace('whatsapp:', '')
    sess      = _WA_SESSIONS.get(from_num, {})

    # ── 1. LOCATION PIN ───────────────────────────────
    if lat_str and lng_str:
        try:
            lat, lng = float(lat_str), float(lng_str)
            if sess.get('state') == 'AWAITING_CONFIRM':
                sess['pending'].update({'lat': lat, 'lng': lng,
                                        'area': _wa_reverse_geocode(lat, lng)})
                sess['ts'] = time.time()
                _WA_SESSIONS[from_num] = sess
                return _wa_twiml(
                    "📍 Location saved!\n\nReply *YES* to submit or *NO* to cancel."
                )
        except Exception:
            pass

    # ── 2. PHOTO ──────────────────────────────────────
    if num_media > 0 and media_url:
        try:
            img_bytes, mime = _wa_download_image(media_url)
            img_b64         = base64.b64encode(img_bytes).decode()
            ai_result       = ai_engine.analyze_image(img_b64, mime=mime)
            issue           = _wa_extract_issue(ai_result)

            if not issue:
                return _wa_twiml(
                    "🔍 I couldn't identify a clear civic issue in this photo.\n\n"
                    "Please send a clearer image (pothole, garbage, broken light, etc.)."
                )

            tag       = (issue.get('tag') or issue.get('issue_type') or 'other').lower()
            severity  = (issue.get('severity') or 'medium').lower()
            desc      = (issue.get('improved_description') or
                         issue.get('description') or
                         issue.get('summary') or
                         f'{tag.title()} issue detected').strip()
            authority = (issue.get('suggested_authority') or
                         issue.get('recommended_authority') or 'MCD')
            confidence = issue.get('confidence') or issue.get('confidence_score') or 0

            _WA_SESSIONS[from_num] = {
                'state':   'AWAITING_CONFIRM',
                'ts':      time.time(),
                'img':     f'data:{mime};base64,{img_b64}',
                'pending': {
                    'user':        phone,
                    'area':        'Delhi',
                    'description': desc,
                    'tag':         tag,
                    'severity':    severity,
                    'lat':         None,
                    'lng':         None,
                },
            }

            conf_txt = f" ({confidence}% confidence)" if confidence else ""
            te = _TAG_EMOJI.get(tag, '⚠️')
            se = _SEV_EMOJI.get(severity, '🟡')

            return _wa_twiml(
                f"{te} *{tag.replace('_',' ').title()} Detected*{conf_txt}\n\n"
                f"{se} Severity: *{severity.upper()}*\n"
                f"🏛 Authority: {authority}\n\n"
                f"_{desc[:140]}{'…' if len(desc) > 140 else ''}_\n\n"
                f"Reply *YES* to submit ✅\n"
                f"Reply *NO* to cancel ❌\n"
                f"Or share your 📍 *location pin* for precise GPS"
            )

        except Exception as e:
            print(f"[WhatsApp] Image error: {e}")
            import traceback; traceback.print_exc()
            return _wa_twiml("❌ Trouble analyzing that image. Please try again.")

    # ── 3. TEXT COMMANDS ──────────────────────────────
    bl = body.lower()

    # YES → submit
    if bl in ('yes', 'y', 'yeah', 'ha', 'haan', 'ok', 'okay', 'submit', 'confirm', '✅'):
        if sess.get('state') == 'AWAITING_CONFIRM':
            p = sess['pending']
            try:
                lat = p.get('lat') or AREA_COORDS.get(p.get('area', ''), [28.6139, 77.2090])[0]
                lng = p.get('lng') or AREA_COORDS.get(p.get('area', ''), [28.6139, 77.2090])[1]

                issue_id = insert_issue(
                    user        = p.get('user', phone),
                    area        = p.get('area', 'Delhi'),
                    description = p['description'],
                    severity    = p.get('severity', 'medium'),
                    tag         = p['tag'],
                    landmark    = '',
                    contact     = phone,
                    lat         = lat,
                    lng         = lng,
                    image       = sess.get('img'),
                )
                del _WA_SESSIONS[from_num]

                base_url = os.environ.get('AREAPULSE_URL', 'https://areapulse-a1k2.onrender.com')
                te = _TAG_EMOJI.get(p['tag'], '⚠️')
                se = _SEV_EMOJI.get(p.get('severity'), '🟡')
                return _wa_twiml(
                    f"✅ *Issue #{issue_id} Reported!*\n\n"
                    f"{te} {p['tag'].title()}  {se} {p.get('severity','medium').title()}\n"
                    f"📍 {p['area']}\n\n"
                    f"🗺 Track all issues:\n{base_url}/issues-all\n\n"
                    f"Thank you for making Delhi better! 🙏"
                )
            except Exception as e:
                print(f"[WhatsApp] Insert error: {e}")
                return _wa_twiml("❌ Error saving report. Please try again.")
        return _wa_twiml("Please send a *photo* first, then reply YES to confirm.")

    # NO → cancel
    if bl in ('no', 'n', 'cancel', 'nahi', 'nope', '❌'):
        _WA_SESSIONS.pop(from_num, None)
        return _wa_twiml("❌ Cancelled. Send a new photo anytime to report an issue.")

    # Greeting / help
    if any(w in bl for w in ('hi', 'hello', 'hey', 'start', 'help', 'helo',
                              'namaste', 'namaskar', 'menu')):
        base_url = os.environ.get('AREAPULSE_URL',
                                  'https://areapulse-a1k2.onrender.com')
        return _wa_twiml(
            f"👋 *Welcome to AreaPulse!*\n\n"
            f"Report civic issues in Delhi instantly.\n\n"
            f"📸 Just *send a photo* of any problem:\n"
            f"  🕳 Pothole  🗑 Garbage  💧 Water leak\n"
            f"  💡 Broken light  🚧 Sewage  ⚡ Electrical\n\n"
            f"Our AI identifies it and routes it to the right authority automatically. "
            f"No forms. No apps. No login.\n\n"
            f"🗺 View all issues: {base_url}"
        )

    # Pending issue reminder
    if sess.get('state') == 'AWAITING_CONFIRM':
        p = sess['pending']
        return _wa_twiml(
            f"Waiting for your confirmation.\n\n"
            f"Detected: *{p['tag'].title()}* ({p.get('severity','medium')} severity)\n\n"
            f"Reply *YES* to submit or *NO* to cancel."
        )

    # Fallback
    return _wa_twiml(
        "📸 Send me a *photo* of a civic issue (pothole, garbage, broken light, etc.) "
        "and I'll report it automatically!\n\nType *hi* for help."
    )


@app.route('/whatsapp/status', methods=['POST'])
def whatsapp_status():
    """Twilio delivery status callback — just acknowledge."""
    return '', 204


# ═══════════════════════════════════════════════════════════
#  Navigation pages — rendered via base.html
# ═══════════════════════════════════════════════════════════
def _common_ctx():
    """Shared context passed into every navigation template."""
    return dict(
        current_user=session.get("user"),
        wa_number=(os.environ.get("TWILIO_WHATSAPP_NUMBER") or "").replace("whatsapp:+", "").replace("whatsapp:", "").replace("+", ""),
        wa_join_code=os.environ.get("TWILIO_SANDBOX_CODE") or "",
        maptiler_key=MAPTILER_KEY,
        maptiler_style=MAPTILER_STYLE,
    )


@app.route("/issues-all")
def issues_all_page():
    return render_template("issues.html", **_common_ctx())


@app.route("/my-reports")
def my_reports_page():
    return render_template("my_issues.html", **_common_ctx())


@app.route("/community")
def community_page():
    return render_template("community.html", **_common_ctx())


# ── Govt authority map — consumed by NGO page "Govt Agencies" tab ──────────
_GOV_LOCATIONS = {
    'pothole':     (28.6131, 77.2295, 'ITO'),
    'water':       (28.6304, 77.2177, 'Civil Lines'),
    'garbage':     (28.6517, 77.2219, 'Chandni Chowk'),
    'streetlight': (28.6517, 77.2219, 'Chandni Chowk'),
    'traffic':     (28.6275, 77.2410, 'ITO'),
    'noise':       (28.6304, 77.2050, 'Civil Lines'),
    'sewage':      (28.6210, 77.2090, 'New Delhi'),
    'electricity': (28.5274, 77.2497, 'Nehru Place'),
    'tree':        (28.5494, 77.2001, 'Hauz Khas'),
    'other':       (28.6139, 77.2090, 'Connaught Place'),
}
_GOV_ICONS = {
    'pothole': '🛣', 'water': '💧', 'garbage': '🗑',
    'streetlight': '💡', 'traffic': '🚦', 'noise': '🔊',
    'sewage': '🚧', 'electricity': '⚡', 'tree': '🌳', 'other': '🏛',
}

@app.route('/gov/all')
def gov_all_api():
    """Govt authority list for NGO page 'Govt Agencies' tab."""
    tag_filter = (request.args.get('tag') or '').strip().lower()
    results = []
    for tag, info in ai_engine._AUTHORITY_MAP.items():
        if tag_filter and tag != tag_filter:
            continue
        loc = _GOV_LOCATIONS.get(tag, _GOV_LOCATIONS['other'])
        results.append({
            'name':            info.get('name', ''),
            'email':           info.get('email', ''),
            'phone':           info.get('phone', ''),
            'tag':             tag,
            'focus':           f"{tag.replace('_',' ').title()} issues · Govt of Delhi",
            'department':      info.get('name', ''),
            'area':            loc[2],
            'lat':             loc[0],
            'lng':             loc[1],
            'icon':            _GOV_ICONS.get(tag, '🏛'),
            'rating':          4.0,
            'issues_resolved': 0,
        })
    return jsonify(results)


# ── data endpoints used by sub-pages ──
@app.route("/my-issues-data")
def my_issues_data():
    user = (request.args.get("user") or "").strip().lower()
    if not user:
        return jsonify([])
    all_issues = get_issues()
    mine = [i for i in all_issues if (i.get("user") or "").strip().lower() == user]
    enriched = []
    for i in mine:
        try:
            i.update(calculate_sla(i))
        except Exception:
            pass
        enriched.append(i)
    enriched.sort(key=lambda i: i.get("timestamp") or 0, reverse=True)
    return jsonify(enriched)


@app.route("/user/stats")
def user_stats():
    name = (request.args.get("name") or "").strip().lower()
    if not name:
        return jsonify({"total_reported": 0, "total_resolved": 0, "points": 0})
    mine = [i for i in get_issues() if (i.get("user") or "").strip().lower() == name]
    resolved = sum(1 for i in mine if i.get("status") == "resolved")
    # 5 points per report + 10 bonus per resolved
    points = len(mine) * 5 + resolved * 10
    return jsonify({
        "total_reported": len(mine),
        "total_resolved": resolved,
        "points": points,
    })


@app.route("/issue/<int:issue_id>/detail")
def issue_detail(issue_id):
    """Returns {issue, timeline, matched_agency, nearby_ngos, maps_link} for my_issues.html."""
    try:
        issue = get_issue_by_id(issue_id)
        if not issue:
            issue = next((i for i in get_issues() if int(i.get("id") or 0) == issue_id), None)
        if not issue:
            return jsonify({"error": "issue not found"}), 404
        try:
            issue.update(calculate_sla(issue))
        except Exception:
            pass

        # ── Timeline (4 steps) ──────────────────────────────────────────────
        status       = issue.get("status", "open")
        is_verified  = bool(issue.get("is_verified") or issue.get("verified"))
        is_escalated = bool(issue.get("is_escalated") or issue.get("escalated"))
        is_resolved  = (status == "resolved") or bool(issue.get("resolved"))

        def _step(key):
            if key == "open":      return "done"
            if key == "verified":  return "done" if is_verified  else ("active" if status in ("open","acknowledged") else "pending")
            if key == "escalated": return "done" if is_escalated else ("active" if is_verified and not is_resolved else "pending")
            return                         "done" if is_resolved  else ("active" if is_escalated else "pending")

        timeline = [
            {"key": "open",      "label": "Reported",  "desc": "Issue submitted",        "state": _step("open")},
            {"key": "verified",  "label": "Verified",  "desc": "Confirmed by community", "state": _step("verified")},
            {"key": "escalated", "label": "Escalated", "desc": "Forwarded to authority", "state": _step("escalated")},
            {"key": "resolved",  "label": "Resolved",  "desc": "Issue fixed",            "state": _step("resolved")},
        ]

        # ── Matched authority ───────────────────────────────────────────────
        tag = issue.get("tag", "other")
        try:
            matched_agency = ai_engine.get_authority(tag)
        except Exception:
            matched_agency = {}

        # ── Nearby NGOs ─────────────────────────────────────────────────────
        lat, lng = issue.get("lat"), issue.get("lng")
        try:
            nearby_ngos = get_nearby_ngos(float(lat), float(lng), tag, limit=5) if (lat and lng) else []
        except Exception:
            nearby_ngos = []

        # Scrub any non-JSON-serialisable types (e.g. sets from upvoters)
        def _scrub(d):
            if not isinstance(d, dict): return d
            return {k: (list(v) if isinstance(v, set) else v) for k, v in d.items()}

        return jsonify({
            "issue":          _scrub(issue),
            "timeline":       timeline,
            "matched_agency": _scrub(matched_agency),
            "nearby_ngos":    [_scrub(n) for n in nearby_ngos],
            "maps_link":      f"https://maps.google.com/?q={lat},{lng}" if (lat and lng) else None,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"{type(e).__name__}: {str(e)[:200]}", "issue_id": issue_id}), 500

@app.route('/verify/<int:issue_id>', methods=['POST'])
def verify_issue(issue_id):
    try:
        data           = request.get_json(silent=True) or {}
        admin_password = data.get('admin_password', '')
        user           = data.get('user', 'anonymous')
        if admin_password != 'admin123':
            return jsonify({'error': 'Invalid admin password'}), 403
        issue = get_issue_by_id(issue_id)
        if not issue:
            return jsonify({'error': 'Issue not found'}), 404
        current = bool(issue.get('is_verified', False))
        new_val = not current
        from database import _state
        if _state.get('mode') == 'postgres':
            with _state['pg_pool'].connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE issues SET is_verified=%s, verified=%s, verified_by=%s WHERE id=%s",
                        (new_val, new_val, user if new_val else None, issue_id)
                    )
        elif _state.get('mode') == 'firebase':
            _state['fs_db'].collection('issues').document(str(issue_id)).update({
                'is_verified': new_val, 'verified': new_val,
                'verified_by': user if new_val else None,
            })
        else:
            issue['is_verified'] = new_val
            issue['verified']    = new_val
            issue['verified_by'] = user if new_val else None
        return jsonify({'status': 'ok', 'action': 'removed' if current else 'added'})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)[:120]}), 500


@app.route('/ngo/escalate/<int:issue_id>', methods=['POST'])
def escalate_issue_route(issue_id):
    try:
        issue = get_issue_by_id(issue_id)
        if not issue:
            return jsonify({'error': 'Issue not found'}), 404
        if not issue.get('is_verified', False) and not issue.get('is_escalated', False):
            return jsonify({
                'error':   'verification_required',
                'message': 'Please verify the issue before escalating it.'
            }), 400
        current = bool(issue.get('is_escalated', False))
        new_val = not current
        from database import _state
        if _state.get('mode') == 'postgres':
            with _state['pg_pool'].connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE issues SET is_escalated=%s, escalated=%s, escalated_at=%s WHERE id=%s",
                        (new_val, new_val, time.time() if new_val else None, issue_id)
                    )
        elif _state.get('mode') == 'firebase':
            _state['fs_db'].collection('issues').document(str(issue_id)).update({
                'is_escalated': new_val, 'escalated': new_val,
            })
        else:
            issue['is_escalated'] = new_val
            issue['escalated']    = new_val
        return jsonify({'status': 'ok', 'action': 'removed' if current else 'added'})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)[:120]}), 500


import threading as _threading
_community_lock = _threading.Lock()
_community_posts = []           # list of {id, user, message, area, post_type, timestamp, likes}
_community_likes = {}           # post_id -> set of usernames who liked
_community_seq = [0]


def _community_seed():
    """Seed a few realistic community posts so the page isn't empty on first load."""
    import time as _t
    if _community_posts:
        return
    now = int(_t.time())
    seed = [
        ("RMC_admin",  "Garbage collection schedule for Karol Bagh updated — pickup at 7am daily.", "Karol Bagh",    "update",   now - 600),
        ("citizen42",  "Anyone else losing power in Dwarka Sector 14? Third outage this week.",   "Dwarka",        "question", now - 1800),
        ("RWA_Rohini", "ALERT: water tanker delayed. Expected by 4pm. Stay tuned.",                "Rohini",        "alert",    now - 3000),
        ("citizen99",  "Big pothole near Karol Bagh metro has been filled. Thanks RMC!",          "Karol Bagh",    "resolved", now - 7200),
        ("volunteerD", "Cleanup drive at Hauz Khas park this Saturday 7am. DM to join.",          "Hauz Khas",     "update",   now - 14400),
        ("citizenA",   "Streetlight repair team active in Lajpat Nagar block C. Working tonight.","Lajpat Nagar",  "update",   now - 28000),
    ]
    for user, msg, area, t, ts in seed:
        _community_seq[0] += 1
        _community_posts.append({
            "id": _community_seq[0],
            "user": user,
            "message": msg,
            "area": area,
            "post_type": t,
            "timestamp": ts,
            "likes": 0,
        })


@app.route("/community/posts")
def community_posts_api():
    _community_seed()
    area = (request.args.get("area") or "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit") or 50), 200))
    except Exception:
        limit = 50
    with _community_lock:
        posts = list(_community_posts)
    if area:
        posts = [p for p in posts if (p.get("area") or "").lower() == area.lower()]
    posts.sort(key=lambda p: p.get("timestamp") or 0, reverse=True)
    return jsonify(posts[:limit])


@app.route("/community/post", methods=["POST"])
def community_post_create():
    import time as _t
    data = request.get_json(silent=True) or {}
    user = (data.get("user") or "").strip()
    message = (data.get("message") or "").strip()
    area = (data.get("area") or "Delhi").strip()
    post_type = (data.get("type") or "update").strip()
    if not user:
        return jsonify({"error": "name required"}), 400
    if len(message) < 5:
        return jsonify({"error": "message too short"}), 400
    if post_type not in ("update", "question", "alert", "resolved"):
        post_type = "update"
    with _community_lock:
        _community_seq[0] += 1
        post = {
            "id": _community_seq[0],
            "user": user,
            "message": message,
            "area": area,
            "post_type": post_type,
            "timestamp": int(_t.time()),
            "likes": 0,
        }
        _community_posts.append(post)
    return jsonify({"status": "ok", "id": post["id"], "points_earned": 3})


@app.route("/community/like/<int:post_id>", methods=["POST"])
def community_like(post_id):
    data = request.get_json(silent=True) or {}
    user = (data.get("user") or "").strip()
    if not user:
        return jsonify({"error": "name required"}), 400
    with _community_lock:
        likers = _community_likes.setdefault(post_id, set())
        if user in likers:
            return jsonify({"error": "already liked"}), 409
        likers.add(user)
        for p in _community_posts:
            if p.get("id") == post_id:
                p["likes"] = len(likers)
                return jsonify({"status": "ok", "likes": p["likes"]})
    return jsonify({"error": "post not found"}), 404


# ═══════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'[areapulse] starting on http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', '1') == '1')
