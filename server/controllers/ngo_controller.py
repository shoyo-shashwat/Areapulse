"""controllers/ngo_controller.py — data aggregation for NGO pages. No HTTP objects."""
from services.sla_service import annotate_issues, get_sla_summary
from services.ai_service  import ngo_recommend


def _filter_matching(issues, user):
    tags = user.get('tags', [])
    if not tags:
        return list(issues)
    return [i for i in issues if i.get('tag') in tags]


def get_dashboard_data(issues_raw, user):
    matching = _filter_matching(issues_raw, user)
    annotate_issues(matching)
    open_i   = [i for i in matching if i.get('status') != 'resolved']
    high_pri = sorted(
        [i for i in open_i if i.get('severity')=='high' or i.get('sla_state') in ('breached','critical')],
        key=lambda x: x.get('upvotes',0)+(100 if x.get('sla_state')=='breached' else 0),
        reverse=True)[:6]
    by_tag = {}
    for i in open_i:
        t=i.get('tag','other'); by_tag[t]=by_tag.get(t,0)+1
    all_ann = list(issues_raw)
    annotate_issues(all_ann)
    return {
        'issues':          open_i,
        'high_priority':   high_pri,
        'recommendation':  ngo_recommend(open_i, user.get('tags',[]), user.get('area','Delhi')),
        'by_tag':          by_tag,
        'total_matched':   len(open_i),
        'total_issues':    len(issues_raw),
        'resolved_count':  len([i for i in all_ann if i.get('status')=='resolved']),
    }


def get_opportunities_data(issues_raw, user, tag=None, area=None, severity=None, sort='impact'):
    matching = _filter_matching(issues_raw, user)
    annotate_issues(matching)
    opps = [i for i in matching if i.get('status') != 'resolved']
    if tag:      opps = [i for i in opps if i.get('tag')==tag]
    if area:     opps = [i for i in opps if i.get('area')==area]
    if severity: opps = [i for i in opps if i.get('severity')==severity]
    sort_keys = {
        'impact':   lambda x: -(x.get('upvotes',0)+(50 if x.get('severity')=='high' else 0)),
        'severity': lambda x: {'high':0,'medium':1,'low':2}.get(x.get('severity'),3),
        'upvotes':  lambda x: -x.get('upvotes',0),
        'newest':   lambda x: -x.get('timestamp',0),
    }
    opps.sort(key=sort_keys.get(sort, sort_keys['impact']))
    for i in opps:
        i['impact_score'] = min(100, i.get('upvotes',0)*2
            + (40 if i.get('severity')=='high' else 20 if i.get('severity')=='medium' else 5)
            + (20 if i.get('sla_state')=='breached' else 0))
    return {'issues': opps, 'total': len(opps), 'tag_filter': tag, 'area_filter': area, 'sort': sort}


def get_impact_data(issues_raw, user):
    all_ann = list(issues_raw)
    annotate_issues(all_ann)
    resolved = [i for i in all_ann if i.get('status')=='resolved']
    return {
        'resolved_count':  len(resolved),
        'total_upvotes':   sum(i.get('upvotes',0) for i in resolved),
        'citizens_helped': sum(i.get('upvotes',0) for i in resolved)*3,
        'issues':          all_ann,
    }
