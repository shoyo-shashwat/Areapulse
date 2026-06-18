"""
AreaPulse GovNGO Portal — app.py
Entry point. Creates Flask app pointing at client/ for templates + static.
Registers all blueprints. All route logic lives in routes/.
"""
import os, sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── PATHS ─────────────────────────────────────────────────────
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR   = os.path.dirname(_SERVER_DIR)
_CLIENT_DIR = os.path.join(_ROOT_DIR, 'client')

# ── MAKE server/ subfolders importable ───────────────────────
sys.path.insert(0, _SERVER_DIR)

# ── DATABASE ─────────────────────────────────────────────────
_parent_areapulse = os.path.join(_ROOT_DIR, '..', 'Areapulse')
if os.path.isdir(_parent_areapulse):
    sys.path.insert(0, _parent_areapulse)

try:
    from database import (
        init_db, get_issues, get_issue_by_id, update_issue_status,
        get_all_ngos, escalate_issue, get_issues_for_gov,
        SLA_HOURS, CROWD_ESCALATION_THRESHOLD,
    )
    print('[portal] ✓ Connected to AreaPulse database')
except ImportError:
    from config.db_stub import (
        init_db, get_issues, get_issue_by_id, update_issue_status,
        get_all_ngos, escalate_issue, get_issues_for_gov,
        SLA_HOURS, CROWD_ESCALATION_THRESHOLD,
    )
    print('[portal] ⚠ Using stub data — set DATABASE_URL for Postgres')

from flask import Flask
from config.settings import SECRET_KEY, MAPTILER_KEY

# ── FLASK APP — client/ for templates + static ───────────────
app = Flask(
    __name__,
    template_folder=os.path.join(_CLIENT_DIR, 'templates'),
    static_folder=os.path.join(_CLIENT_DIR, 'static'),
)
app.secret_key = SECRET_KEY

# ── REGISTER BLUEPRINTS ──────────────────────────────────────
from routes.auth_routes import auth_bp
from routes.gov_routes  import gov_bp
from routes.ngo_routes  import ngo_bp
from routes.gov_api     import gov_api_bp
from routes.ngo_api     import ngo_api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(gov_bp)
app.register_blueprint(ngo_bp)
app.register_blueprint(gov_api_bp)
app.register_blueprint(ngo_api_bp)

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f'\n  AreaPulse Portal → http://localhost:{port}')
    print(f'  Templates : {os.path.join(_CLIENT_DIR, "templates")}')
    print(f'  Static    : {os.path.join(_CLIENT_DIR, "static")}')
    print(f'  Login     : gov_rmc / ngo_sanitation  PIN: 0000\n')
    app.run(host='0.0.0.0', port=port, debug=True)
