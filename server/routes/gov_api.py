"""routes/gov_api.py — Gov JSON API blueprint. Returns JSON only."""
import csv, io, json
from flask import Blueprint, jsonify, request, Response, stream_with_context, send_file

from middleware.auth              import require_gov, current_user
from config.settings              import SLA_HOURS
from services.sla_service         import annotate_issues, get_sla_summary
from services.ai_service          import gov_briefing, chat_stream
from services.notification_service import send_whatsapp
from services.weather_service     import get_weather_risk

gov_api_bp = Blueprint('gov_api', __name__, url_prefix='/gov/api')


def _db():
    import importlib
    for m in ['database','config.db_stub']:
        try: return importlib.import_module(m)
        except ImportError: continue

def _my_issues(annotated=True):
    u      = current_user()
    issues = _db().get_issues(limit=300)
    if u.get('tags'):
        issues = [i for i in issues if i.get('tag') in u['tags']]
    if annotated:
        annotate_issues(issues)
    return issues, u


# ── ISSUES ────────────────────────────────────────────────────

@gov_api_bp.route('/issues')
@require_gov
def issues():
    tag    = request.args.get('tag')
    status = request.args.get('status')
    limit  = min(int(request.args.get('limit',300)),500)
    issues_list, u = _my_issues()
    if tag:    issues_list = [i for i in issues_list if i.get('tag')==tag]
    if status: issues_list = [i for i in issues_list if i.get('status')==status]
    return jsonify({'issues':issues_list[:limit],'total':len(issues_list)})


@gov_api_bp.route('/update-status', methods=['POST'])
@require_gov
def update_status():
    data      = request.get_json(silent=True) or {}
    issue_id  = data.get('id')
    new_status= (data.get('status') or '').lower().strip()
    note      = data.get('note','')
    u         = current_user()
    if not issue_id or not new_status:
        return jsonify({'error':'id and status required'}),400
    db     = _db()
    result = db.update_issue_status(int(issue_id), new_status, updated_by=u['username'], note=note)
    if result is None:
        return jsonify({'error':'Update failed'}),400
    issue = db.get_issue_by_id(int(issue_id))
    if issue and issue.get('contact') and new_status in ('resolved','in_progress','acknowledged','escalated'):
        send_whatsapp(issue['contact'],
            f"AreaPulse: Your report #AP-{issue_id} in {issue.get('area','?')} is now "
            f"{new_status.replace('_',' ')}.")
    return jsonify({'ok':True,'id':issue_id,'status':new_status})


# Legacy path kept for backwards compat with any old JS
@gov_api_bp.route('/bulk-update', methods=['POST'])
@require_gov
def bulk_update():
    data = request.get_json(silent=True) or {}
    ids, status = data.get('ids',[]), (data.get('status') or '').lower()
    u = current_user(); updated=0
    for iid in ids:
        if _db().update_issue_status(int(iid),status,updated_by=u['username']): updated+=1
    return jsonify({'ok':True,'updated':updated})


@gov_api_bp.route('/escalate', methods=['POST'])
@require_gov
def escalate():
    data = request.get_json(silent=True) or {}
    iid  = data.get('id')
    if not iid: return jsonify({'error':'id required'}),400
    ok = _db().escalate_issue(int(iid), reason=data.get('reason','manual'))
    return jsonify({'ok':ok})


@gov_api_bp.route('/deescalate', methods=['POST'])
@require_gov
def deescalate():
    data = request.get_json(silent=True) or {}
    iid  = data.get('id')
    u    = current_user()
    if not iid: return jsonify({'error':'id required'}),400
    result = _db().update_issue_status(int(iid),'in_progress',updated_by=u['username'],note=data.get('note',''))
    return jsonify({'ok':result is not None,'id':iid,'status':'in_progress'})


# ── SLA ───────────────────────────────────────────────────────

@gov_api_bp.route('/sla-data')
@require_gov
def sla_data():
    issues_list, _ = _my_issues()
    open_i  = [i for i in issues_list if i.get('status')!='resolved']
    summary = get_sla_summary(open_i)
    return jsonify({'summary':summary,
                    'breached':[i for i in open_i if i.get('sla_state')=='breached'][:20],
                    'total_open':len(open_i)})


# ── AI ────────────────────────────────────────────────────────

@gov_api_bp.route('/ai-briefing', methods=['POST'])
@require_gov
def ai_briefing_route():
    issues_list, _ = _my_issues()
    return jsonify({'briefing': gov_briefing([i for i in issues_list if i.get('status')!='resolved'])})


@gov_api_bp.route('/ai-chat', methods=['POST'])
@require_gov
def ai_chat():
    data    = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message: return jsonify({'error':'message required'}),400
    issues_list, u = _my_issues()
    def generate():
        yield from chat_stream(message,'gov',u,history=data.get('history',[]),issues_snapshot=issues_list)
    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


# ── WEATHER ───────────────────────────────────────────────────

@gov_api_bp.route('/weather', defaults={'area': None})
@gov_api_bp.route('/weather/<area>')
@require_gov
def weather(area):
    u    = current_user()
    area = area or u.get('area', 'Connaught Place')
    lat  = request.args.get('lat', u.get('lat'), type=float)
    lng  = request.args.get('lng', u.get('lng'), type=float)
    return jsonify(get_weather_risk(area, lat=lat, lng=lng))


# ── NOTIFICATIONS ─────────────────────────────────────────────

@gov_api_bp.route('/notifications')
@require_gov
def notifications():
    issues_list, _ = _my_issues()
    notifs = []
    for i in issues_list:
        if i.get('sla_state')=='breached':
            notifs.append({'type':'sla',
                'title':f"SLA Breached: {(i.get('tag','')+'').title()} in {i.get('area','?')}",
                'body':f"#AP-{i['id']} is {round(i.get('sla_overdue_hours',0),1)}h overdue.",
                'issue_id':i['id']})
        if i.get('upvotes',0)>=25:
            notifs.append({'type':'crowd',
                'title':f"Crowd Escalation: {i.get('area','?')} #{i['id']}",
                'body':f"{i.get('upvotes')} upvotes — crowd threshold reached.",
                'issue_id':i['id']})
    return jsonify({'notifications':notifs,'total':len(notifs)})


# ── EXPORT ────────────────────────────────────────────────────

@gov_api_bp.route('/export/csv')
@require_gov
def export_csv():
    issues_list, _ = _my_issues()
    buf    = io.StringIO()
    fields = ['id','area','tag','severity','status','sla_state','upvotes','description','timestamp']
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for i in issues_list:
        writer.writerow({k: i.get(k,'') for k in fields})
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment; filename=areapulse-issues.csv'})


# ── MISC ──────────────────────────────────────────────────────

@gov_api_bp.route('/realtime-token')
def realtime_token():
    return jsonify({'firebase_config': None})
