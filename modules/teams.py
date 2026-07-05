"""
Teams module — cross-portal team collaboration with invite codes + chat.

Anyone (gov or NGO user) can:
- Create a team (auto-generates a 6-char join code like AP-K8X2)
- Share the code with colleagues
- Others join by entering the code
- Team members chat inside the team panel

Storage: local JSON at /static/data/teams.json (no schema migration needed).
"""
import json, os, secrets, string, time
from datetime import datetime
from threading import Lock
from flask import Blueprint, request, jsonify, render_template
from modules.auth import require_auth, require_gov, require_ngo, current_user

teams_bp = Blueprint('teams', __name__)

# ── Storage ────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'data')
_FILE = os.path.join(_DATA_DIR, 'teams.json')
_LOCK = Lock()

def _load():
    if not os.path.exists(_FILE):
        return {'teams': [], 'messages': {}}
    try:
        with open(_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'teams': [], 'messages': {}}

def _save(data):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _gen_code():
    """Generate a friendly team code like AP-K8X2."""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    return 'AP-' + ''.join(secrets.choice(chars) for _ in range(4))


# ── Context helper (avoids circular import from app.py) ────────

def _ctx():
    """Minimal template context — same keys as app._portal_ctx()."""
    import os
    return {
        'cu':           current_user(),
        'maptiler_key': os.environ.get('MAPTILER_KEY', ''),
    }


# ── Routes: Pages ──────────────────────────────────────────────

@teams_bp.route('/gov/teams')
@require_gov
def gov_teams_page():
    return render_template('gov/teams.html', **_ctx())

@teams_bp.route('/ngo/teams')
@require_ngo
def ngo_teams_page():
    return render_template('ngo/teams.html', **_ctx())


# ── Routes: API ────────────────────────────────────────────────

@teams_bp.route('/api/teams/mine', methods=['GET'])
@require_auth
def api_my_teams():
    """List teams the current user belongs to."""
    u = current_user()
    with _LOCK:
        data = _load()
    mine = [t for t in data['teams'] if u['username'] in t['members']]
    return jsonify({'teams': mine, 'me': u['username']})


@teams_bp.route('/api/teams/create', methods=['POST'])
@require_auth
def api_create_team():
    """Create a new team. Creator is auto-added as first member."""
    u = current_user()
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()
    purpose = (body.get('purpose') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    with _LOCK:
        data = _load()
        # generate unique code
        for _ in range(10):
            code = _gen_code()
            if not any(t['code'] == code for t in data['teams']):
                break
        team = {
            'id': secrets.token_hex(4),
            'name': name,
            'purpose': purpose,
            'code': code,
            'creator': u['username'],
            'creator_role': u['role'],
            'created_at': datetime.utcnow().isoformat(),
            'members': [u['username']],
            'member_details': {u['username']: {'name': u.get('name', u['username']),
                                                 'role': u['role'],
                                                 'dept': u.get('dept', '')}},
        }
        data['teams'].append(team)
        data['messages'][team['id']] = []
        _save(data)

    return jsonify({'ok': True, 'team': team})


@teams_bp.route('/api/teams/join', methods=['POST'])
@require_auth
def api_join_team():
    """Join a team using its invite code."""
    u = current_user()
    body = request.get_json(silent=True) or {}
    code = (body.get('code') or '').strip().upper()
    if not code:
        return jsonify({'error': 'code required'}), 400

    with _LOCK:
        data = _load()
        team = next((t for t in data['teams'] if t['code'] == code), None)
        if not team:
            return jsonify({'error': 'Invalid code'}), 404
        if u['username'] in team['members']:
            return jsonify({'ok': True, 'team': team, 'already_member': True})
        team['members'].append(u['username'])
        team['member_details'][u['username']] = {
            'name': u.get('name', u['username']),
            'role': u['role'],
            'dept': u.get('dept', '')
        }
        # System message
        data['messages'].setdefault(team['id'], []).append({
            'id': secrets.token_hex(4),
            'system': True,
            'text': f"{u.get('name', u['username'])} joined the team",
            'ts': datetime.utcnow().isoformat(),
        })
        _save(data)

    return jsonify({'ok': True, 'team': team})


@teams_bp.route('/api/teams/<team_id>', methods=['GET'])
@require_auth
def api_team_detail(team_id):
    u = current_user()
    with _LOCK:
        data = _load()
    team = next((t for t in data['teams'] if t['id'] == team_id), None)
    if not team or u['username'] not in team['members']:
        return jsonify({'error': 'not found or not a member'}), 404
    messages = data.get('messages', {}).get(team_id, [])
    return jsonify({'team': team, 'messages': messages, 'me': u['username']})


@teams_bp.route('/api/teams/<team_id>/message', methods=['POST'])
@require_auth
def api_team_message(team_id):
    """Post a message to team chat."""
    u = current_user()
    body = request.get_json(silent=True) or {}
    text = (body.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text required'}), 400
    if len(text) > 2000:
        text = text[:2000]

    with _LOCK:
        data = _load()
        team = next((t for t in data['teams'] if t['id'] == team_id), None)
        if not team or u['username'] not in team['members']:
            return jsonify({'error': 'not a member'}), 403
        msg = {
            'id': secrets.token_hex(4),
            'author': u['username'],
            'author_name': u.get('name', u['username']),
            'author_role': u['role'],
            'text': text,
            'ts': datetime.utcnow().isoformat(),
        }
        data['messages'].setdefault(team_id, []).append(msg)
        # trim old messages if too many
        if len(data['messages'][team_id]) > 500:
            data['messages'][team_id] = data['messages'][team_id][-500:]
        _save(data)

    return jsonify({'ok': True, 'message': msg})


@teams_bp.route('/api/teams/<team_id>/leave', methods=['POST'])
@require_auth
def api_team_leave(team_id):
    u = current_user()
    with _LOCK:
        data = _load()
        team = next((t for t in data['teams'] if t['id'] == team_id), None)
        if not team:
            return jsonify({'error': 'not found'}), 404
        if u['username'] in team['members']:
            team['members'].remove(u['username'])
            team['member_details'].pop(u['username'], None)
            data['messages'].setdefault(team['id'], []).append({
                'id': secrets.token_hex(4),
                'system': True,
                'text': f"{u.get('name', u['username'])} left the team",
                'ts': datetime.utcnow().isoformat(),
            })
            _save(data)
    return jsonify({'ok': True})