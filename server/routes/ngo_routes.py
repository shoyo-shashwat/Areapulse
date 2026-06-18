"""routes/ngo_routes.py — NGO page routes. HTTP plumbing only → controller → render."""
import json
from flask import Blueprint, render_template, redirect, url_for, request

from middleware.auth       import require_ngo, current_user
from config.settings       import MAPTILER_KEY
from services.sla_service  import annotate_issues
from controllers.ngo_controller import (
    get_dashboard_data, get_opportunities_data, get_impact_data,
)

ngo_bp = Blueprint('ngo', __name__, url_prefix='/ngo')


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


def _ctx():
    return {'cu': current_user(), 'maptiler_key': MAPTILER_KEY}


@ngo_bp.route('/dashboard')
@require_ngo
def dashboard():
    data = get_dashboard_data(_get_issues(), current_user())
    return render_template('ngo/dashboard.html', **data, **_ctx())


@ngo_bp.route('/opportunities')
@require_ngo
def opportunities():
    u    = current_user()
    data = get_opportunities_data(_get_issues(), u,
                                  tag=request.args.get('tag'),
                                  area=request.args.get('area'),
                                  severity=request.args.get('severity'),
                                  sort=request.args.get('sort','impact'))
    areas = sorted(set(i.get('area','') for i in _get_issues() if i.get('area')))
    return render_template('ngo/opportunities.html',
                           opportunities=data['issues'], areas=areas,
                           filters={'tag':request.args.get('tag'),'area':request.args.get('area'),
                                    'severity':request.args.get('severity')}, **_ctx())


@ngo_bp.route('/projects')
@require_ngo
def projects():
    u        = current_user()
    issues   = annotate_issues(_get_issues())
    projects = [i for i in issues if i.get('tag') in u['tags']
                and i.get('status') in ('in_progress','acknowledged')]
    return render_template('ngo/projects.html', projects=projects, **_ctx())


@ngo_bp.route('/impact')
@require_ngo
def impact():
    data = get_impact_data(_get_issues(), current_user())
    return render_template('ngo/impact.html', **data, **_ctx())


@ngo_bp.route('/map')
@require_ngo
def map_view():
    u      = current_user()
    issues = annotate_issues(_get_issues())
    if u.get('tags'):
        issues = [i for i in issues if i.get('tag') in u['tags']]
    issues_json = json.dumps([{
        'id':i['id'],'lat':i.get('lat'),'lng':i.get('lng'),'tag':i.get('tag'),
        'area':i.get('area'),'description':(i.get('description',''))[:80],
        'status':i.get('status'),'severity':i.get('severity'),'upvotes':i.get('upvotes',0),
    } for i in issues if i.get('lat') and i.get('lng')])
    return render_template('ngo/map.html', issues_json=issues_json, **_ctx())


@ngo_bp.route('/analytics')
@require_ngo
def analytics():
    u       = current_user()
    issues  = annotate_issues(_get_issues())
    matching = [i for i in issues if i.get('tag') in u['tags']]
    by_area, by_status = {}, {}
    for i in matching:
        a=i.get('area','?');      by_area[a]  = by_area.get(a,0)+1
        s=i.get('status','open'); by_status[s]= by_status.get(s,0)+1
    return render_template('ngo/analytics.html', issues=matching,
                           by_area=by_area, by_status=by_status, **_ctx())


@ngo_bp.route('/ai-assistant')
@require_ngo
def ai_assistant():
    return render_template('ngo/ai_assistant.html', **_ctx())


@ngo_bp.route('/gov-coordination')
@require_ngo
def gov_coordination():
    u      = current_user()
    issues = annotate_issues(_get_issues())
    return render_template('ngo/gov_coordination.html',
                           issues=[i for i in issues if i.get('tag') in u['tags']], **_ctx())


@ngo_bp.route('/reports')
@require_ngo
def reports():
    return render_template('ngo/reports.html', **_ctx())


@ngo_bp.route('/notifications')
@require_ngo
def notifications():
    return render_template('ngo/notifications.html', **_ctx())


@ngo_bp.route('/settings')
@require_ngo
def settings():
    return render_template('ngo/settings.html', **_ctx())


@ngo_bp.route('/issue/<int:issue_id>')
@require_ngo
def issue_detail(issue_id):
    issue = _get_issue(issue_id)
    if not issue:
        return redirect(url_for('ngo.opportunities'))
    annotate_issues([issue])
    return render_template('ngo/issue_detail.html', issue=issue, **_ctx())
