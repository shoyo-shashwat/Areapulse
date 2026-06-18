"""routes/auth_routes.py — /login /logout / root redirect."""
from flask import Blueprint, render_template, request, redirect, url_for, session
from middleware.auth import login_user, logout_user, current_user
from config.settings import MAPTILER_KEY

auth_bp = Blueprint('auth', __name__)


def _ctx():
    return {'cu': current_user(), 'maptiler_key': MAPTILER_KEY}


@auth_bp.route('/')
def root():
    if session.get('portal_user'):
        role = session.get('portal_role', 'gov')
        return redirect(url_for('gov.dashboard' if role == 'gov' else 'ngo.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('portal_user'):
        role = session.get('portal_role', 'gov')
        return redirect(url_for('gov.dashboard' if role == 'gov' else 'ngo.dashboard'))
    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip().lower()
        pin      = (request.form.get('pin')      or '').strip()
        ok, role, _ = login_user(username, pin)
        if ok:
            return redirect(url_for('gov.dashboard' if role == 'gov' else 'ngo.dashboard'))
        error = 'Invalid username or PIN. Try gov_rmc / ngo_sanitation with PIN 0000.'
    return render_template('auth/login.html', error=error, **_ctx())


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
