"""routes/ngo_api.py — NGO JSON API blueprint. Returns JSON only."""
from flask import Blueprint, jsonify, request, Response, stream_with_context

from middleware.auth       import require_ngo, current_user
from services.sla_service  import annotate_issues, get_sla_summary
from services.ai_service   import ngo_recommend, chat_stream
from services.weather_service import get_weather_risk

ngo_api_bp = Blueprint('ngo_api', __name__, url_prefix='/ngo/api')


def _db():
    import importlib
    for m in ['database','config.db_stub']:
        try: return importlib.import_module(m)
        except ImportError: continue

def _matching(annotated=True):
    u      = current_user()
    issues = _db().get_issues(limit=300)
    if u.get('tags'):
        issues = [i for i in issues if i.get('tag') in u['tags']]
    if annotated:
        annotate_issues(issues)
    return issues, u


@ngo_api_bp.route('/opportunities')
@require_ngo
def opportunities():
    issues_list, u = _matching()
    opps = [i for i in issues_list if i.get('status')!='resolved']
    return jsonify({'issues':opps,'total':len(opps)})


@ngo_api_bp.route('/commit', methods=['POST'])
@require_ngo
def commit():
    data = request.get_json(silent=True) or {}
    iid  = data.get('issue_id')
    u    = current_user()
    if not iid: return jsonify({'error':'issue_id required'}),400
    result = _db().update_issue_status(int(iid),'in_progress',updated_by=u['username'],
        note=f"NGO {u['name']} committed. Volunteers:{data.get('volunteers',1)}. ETA:{data.get('eta','')}.")
    return jsonify({'ok':result is not None})


@ngo_api_bp.route('/deescalate', methods=['POST'])
@require_ngo
def deescalate():
    data = request.get_json(silent=True) or {}
    iid  = data.get('id')
    u    = current_user()
    if not iid: return jsonify({'error':'id required'}),400
    result = _db().update_issue_status(int(iid),'in_progress',updated_by=u['username'],note=data.get('note',''))
    return jsonify({'ok':result is not None,'id':iid,'status':'in_progress'})


@ngo_api_bp.route('/ai-recommend', methods=['GET','POST'])
@require_ngo
def ai_recommend():
    issues_list, u = _matching()
    open_i = [i for i in issues_list if i.get('status')!='resolved']
    return jsonify({'recommendation': ngo_recommend(open_i, u.get('tags',[]), u.get('area','Delhi'))})


@ngo_api_bp.route('/ai-chat', methods=['POST'])
@require_ngo
def ai_chat():
    data    = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message: return jsonify({'error':'message required'}),400
    issues_list, u = _matching()
    def generate():
        yield from chat_stream(message,'ngo',u,history=data.get('history',[]),issues_snapshot=issues_list)
    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


@ngo_api_bp.route('/weather', defaults={'area': None})
@ngo_api_bp.route('/weather/<area>')
@require_ngo
def weather(area):
    u    = current_user()
    area = area or u.get('area', 'Connaught Place')
    lat  = request.args.get('lat', u.get('lat'), type=float)
    lng  = request.args.get('lng', u.get('lng'), type=float)
    return jsonify(get_weather_risk(area, lat=lat, lng=lng))


@ngo_api_bp.route('/impact-data')
@require_ngo
def impact_data():
    issues_list, u = _matching()
    resolved = [i for i in issues_list if i.get('status')=='resolved']
    return jsonify({'issues_resolved':len(resolved),'total_upvotes':sum(i.get('upvotes',0) for i in resolved)})


@ngo_api_bp.route('/projects')
@require_ngo
def projects():
    issues_list, u = _matching()
    committed = [i for i in issues_list if i.get('status') in ('in_progress','acknowledged')]
    return jsonify({'projects':committed})


@ngo_api_bp.route('/notifications')
@require_ngo
def notifications():
    issues_list, _ = _matching()
    notifs = []
    for i in issues_list:
        if i.get('upvotes',0)>=25 and i.get('status')!='resolved':
            notifs.append({'type':'crowd','title':f"High demand: {i.get('area','?')} #{i['id']}",
                'body':f"{i.get('upvotes')} upvotes.",'issue_id':i['id']})
        if i.get('sla_state')=='breached':
            notifs.append({'type':'sla','title':f"Gov SLA Breached: #{i['id']}",
                'body':f"{round(i.get('sla_overdue_hours',0),1)}h overdue — NGO can step in.",
                'issue_id':i['id']})
    return jsonify({'notifications':notifs,'total':len(notifs)})
