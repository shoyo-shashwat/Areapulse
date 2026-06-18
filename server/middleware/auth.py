"""middleware/auth.py — session auth, require_gov / require_ngo decorators, account definitions."""
import functools
from flask import session, redirect, url_for, request, jsonify

GOV_ACCOUNTS = {
    'gov_rmc':         {'pin':'0000','name':'RMC Officer',        'dept':'Delhi Municipal Corporation','tags':['pothole','garbage','sewage','streetlight','tree','other'],'avatar':'RO','area':'Connaught Place','lat':28.6315,'lng':77.2167},
    'gov_water':       {'pin':'0000','name':'Water Board Officer', 'dept':'Delhi Jal Board',            'tags':['water','sewage'],                                        'avatar':'WB','area':'Karol Bagh',      'lat':28.6520,'lng':77.1904},
    'gov_electricity': {'pin':'0000','name':'Electricity Officer', 'dept':'BSES / TPDDL',              'tags':['electricity','streetlight'],                             'avatar':'EO','area':'Dwarka',          'lat':28.5921,'lng':77.0460},
    'gov_traffic':     {'pin':'0000','name':'Traffic Police',      'dept':'Delhi Traffic Police',       'tags':['traffic','noise'],                                       'avatar':'TP','area':'Chandni Chowk',   'lat':28.6507,'lng':77.2334},
}

NGO_ACCOUNTS = {
    'ngo_sanitation': {'pin':'0000','name':'Delhi Green Mission', 'dept':'Sanitation & Waste', 'tags':['garbage','sewage'],          'avatar':'DG','area':'Rohini',         'lat':28.7493,'lng':77.1000,'rating':4.6},
    'ngo_water':      {'pin':'0000','name':'Jal Seva Trust',      'dept':'Water & Sewage',     'tags':['water','sewage'],            'avatar':'JS','area':'Hauz Khas',       'lat':28.5494,'lng':77.2001,'rating':4.7},
    'ngo_civic':      {'pin':'0000','name':'Sahayata Foundation', 'dept':'General Civic',      'tags':['other','pothole','tree'],    'avatar':'SF','area':'Connaught Place',  'lat':28.6315,'lng':77.2167,'rating':4.2},
    'ngo_power':      {'pin':'0000','name':'Light Up Delhi',      'dept':'Street Lighting',    'tags':['streetlight','electricity'], 'avatar':'LD','area':'Saket',           'lat':28.5244,'lng':77.2090,'rating':4.3},
}

ALL_ACCOUNTS = {**GOV_ACCOUNTS, **NGO_ACCOUNTS}


def login_user(username, pin):
    """Returns (success, role, account_dict)."""
    acct = ALL_ACCOUNTS.get(username)
    if not acct or acct['pin'] != pin:
        return False, None, None
    role = 'gov' if username in GOV_ACCOUNTS else 'ngo'
    session.update({
        'portal_user':   username,
        'portal_role':   role,
        'portal_name':   acct['name'],
        'portal_dept':   acct.get('dept', ''),
        'portal_tags':   acct.get('tags', []),
        'portal_avatar': acct.get('avatar', username[:2].upper()),
    })
    return True, role, acct


def logout_user():
    for k in ['portal_user','portal_role','portal_name','portal_dept','portal_tags','portal_avatar']:
        session.pop(k, None)


def current_user():
    return {
        'username': session.get('portal_user'),
        'role':     session.get('portal_role'),
        'name':     session.get('portal_name', 'Guest'),
        'dept':     session.get('portal_dept', ''),
        'tags':     session.get('portal_tags', []),
        'avatar':   session.get('portal_avatar', '?'),
        'is_gov':   session.get('portal_role') == 'gov',
        'is_ngo':   session.get('portal_role') == 'ngo',
    }


def require_gov(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('portal_user'):
            if request.path.startswith('/gov/api'):
                return jsonify({'error': 'Not authenticated'}), 401
            return redirect(url_for('auth.login'))
        if session.get('portal_role') != 'gov':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def require_ngo(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('portal_user'):
            if request.path.startswith('/ngo/api'):
                return jsonify({'error': 'Not authenticated'}), 401
            return redirect(url_for('auth.login'))
        if session.get('portal_role') != 'ngo':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
