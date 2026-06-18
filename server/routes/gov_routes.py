"""routes/gov_routes.py — Gov page routes. HTTP plumbing only → controller → render."""
import json
from flask import Blueprint, render_template, redirect, url_for, request

from middleware.auth      import require_gov, current_user
from config.settings      import MAPTILER_KEY, SLA_HOURS
from services.sla_service import annotate_issues
from controllers.gov_controller import (
    get_dashboard_data, get_queue_data, get_sla_board_data, get_analytics_data,
)

gov_bp = Blueprint('gov', __name__, url_prefix='/gov')

# DB functions — imported dynamically so app.py controls which DB is used
import sys
def _db():
    import importlib
    for mod_name in ['database', 'config.db_stub']:
        try:
            return importlib.import_module(mod_name)
        except ImportError:
            continue
    raise RuntimeError('No database module found')

def _get_issues(tag=None, status=None, limit=300):
    return _db().get_issues(tag=tag, status=status, limit=limit)

def _get_issue(iid):
    return _db().get_issue_by_id(iid)

def _ngos():
    return _db().get_all_ngos()


def _ctx():
    return {'cu': current_user(), 'maptiler_key': MAPTILER_KEY}


@gov_bp.route('/dashboard')
@require_gov
def dashboard():
    data = get_dashboard_data(_get_issues(), current_user())
    return render_template('gov/dashboard.html', **data, **_ctx())


@gov_bp.route('/queue')
@require_gov
def queue():
    u    = current_user()
    tag  = request.args.get('tag')
    st   = request.args.get('status')
    sort = request.args.get('sort', 'sla')
    page = int(request.args.get('page', 1))
    data = get_queue_data(_get_issues(), u, tag=tag, status=st, sort=sort, page=page)
    areas = sorted(set(i.get('area','') for i in _get_issues() if i.get('area')))
    return render_template('gov/queue.html', **data, areas=areas,
                           sla_hours=SLA_HOURS, ngos=_ngos(),
                           filters={'tag':tag,'status':st}, **_ctx())


@gov_bp.route('/sla')
@require_gov
def sla():
    data = get_sla_board_data(_get_issues(), current_user())
    return render_template('gov/sla.html', **data, sla_hours=SLA_HOURS, **_ctx())


@gov_bp.route('/map')
@require_gov
def map_view():
    u      = current_user()
    issues = annotate_issues(_get_issues())
    if u.get('tags'):
        issues = [i for i in issues if i.get('tag') in u['tags']]
    issues_json = json.dumps([{
        'id':i['id'],'lat':i.get('lat'),'lng':i.get('lng'),'tag':i.get('tag'),
        'area':i.get('area'),'description':(i.get('description',''))[:80],
        'status':i.get('status'),'severity':i.get('severity'),
        'upvotes':i.get('upvotes',0),'sla_state':i.get('sla_state','healthy'),
    } for i in issues if i.get('lat') and i.get('lng')])
    return render_template('gov/map.html', issues_json=issues_json, **_ctx())


@gov_bp.route('/analytics')
@require_gov
def analytics():
    data = get_analytics_data(_get_issues(), current_user())
    return render_template('gov/analytics.html', **data, **_ctx())


@gov_bp.route('/ai-assistant')
@require_gov
def ai_assistant():
    return render_template('gov/ai_assistant.html', **_ctx())


@gov_bp.route('/reports')
@require_gov
def reports():
    return render_template('gov/reports.html', **_ctx())


@gov_bp.route('/departments')
@require_gov
def departments():
    from middleware.auth import GOV_ACCOUNTS
    issues = annotate_issues(_get_issues())
    depts  = {}
    for username, acct in GOV_ACCOUNTS.items():
        di = [i for i in issues if i.get('tag') in acct['tags']]
        depts[username] = {
            'name':acct['name'], 'dept':acct['dept'], 'tags':acct['tags'],
            'total':len(di),
            'open':len([i for i in di if i.get('status')!='resolved']),
            'resolved':len([i for i in di if i.get('status')=='resolved']),
            'breached':len([i for i in di if i.get('sla_state')=='breached']),
            'compliance':round(len([i for i in di if i.get('status')=='resolved'])/max(len(di),1)*100,1),
        }
    return render_template('gov/departments.html', depts=depts, **_ctx())


@gov_bp.route('/ngo-coordination')
@require_gov
def ngo_coordination():
    return render_template('gov/ngo_coordination.html',
                           ngos=_ngos(), issues=annotate_issues(_get_issues()), **_ctx())


@gov_bp.route('/notifications')
@require_gov
def notifications():
    return render_template('gov/notifications.html', **_ctx())


@gov_bp.route('/settings')
@require_gov
def settings():
    return render_template('gov/settings.html', **_ctx())


@gov_bp.route('/issue/<int:issue_id>')
@require_gov
def issue_detail(issue_id):
    issue = _get_issue(issue_id)
    if not issue:
        return redirect(url_for('gov.queue'))
    annotate_issues([issue])
    ngos = _ngos()
    return render_template('gov/issue_detail.html',
                           issue=issue,
                           nearby_ngos=[n for n in ngos if n.get('tag')==issue.get('tag')][:3],
                           sla_hours=SLA_HOURS, **_ctx())
