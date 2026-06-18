"""controllers/gov_controller.py — data aggregation for Gov pages. No HTTP objects."""
from services.sla_service import annotate_issues, get_sla_summary
from services.ai_service  import gov_briefing


def _filter_tags(issues, tags):
    if not tags:
        return list(issues)
    return [i for i in issues if i.get('tag') in tags]


def get_dashboard_data(issues_raw, user):
    my      = _filter_tags(issues_raw, user.get('tags'))
    annotate_issues(my)
    open_i  = [i for i in my if i.get('status') != 'resolved']
    sla_sum = get_sla_summary(open_i)
    urgent  = sorted([i for i in open_i if i.get('sla_state') in ('breached','critical')],
                     key=lambda x: x.get('sla_overdue_hours', 0), reverse=True)[:8]
    by_tag  = {}
    for i in open_i:
        t = i.get('tag','other'); by_tag[t] = by_tag.get(t,0)+1
    recent  = sorted(my, key=lambda x: x.get('timestamp',0), reverse=True)[:10]
    return {
        'issues':         open_i,
        'urgent':         urgent,
        'sla_summary':    sla_sum,
        'briefing':       gov_briefing(open_i),
        'by_tag':         by_tag,
        'recent':         recent,
        'total':          len(my),
        'open_count':     len(open_i),
        'resolved_count': len([i for i in my if i.get('status')=='resolved']),
        'breached_count': sla_sum.get('breached', 0),
    }


def get_queue_data(issues_raw, user, tag=None, status=None, sort='sla', page=1, per_page=30):
    issues = _filter_tags(issues_raw, user.get('tags'))
    annotate_issues(issues)
    open_i = [i for i in issues if i.get('status') != 'resolved']
    if tag:    open_i = [i for i in open_i if i.get('tag') == tag]
    if status: open_i = [i for i in open_i if i.get('status') == status]
    sort_keys = {
        'sla':     lambda x: (0 if x.get('sla_state')=='breached' else 1 if x.get('sla_state')=='critical' else 2, -x.get('sla_overdue_hours',0)),
        'severity':lambda x: {'high':0,'medium':1,'low':2}.get(x.get('severity'),3),
        'upvotes': lambda x: -x.get('upvotes',0),
        'newest':  lambda x: -x.get('timestamp',0),
    }
    open_i.sort(key=sort_keys.get(sort, sort_keys['sla']))
    total     = len(open_i)
    start     = (page-1)*per_page
    return {
        'issues':      open_i[start:start+per_page],
        'total':       total,
        'page':        page,
        'per_page':    per_page,
        'total_pages': max(1,(total+per_page-1)//per_page),
        'sla_summary': get_sla_summary(open_i),
        'tag_filter':  tag,
        'sort':        sort,
    }


def get_sla_board_data(issues_raw, user):
    issues  = _filter_tags(issues_raw, user.get('tags'))
    annotate_issues(issues)
    open_i  = [i for i in issues if i.get('status') != 'resolved']
    return {
        'lanes': {
            'breached': sorted([i for i in open_i if i.get('sla_state')=='breached'], key=lambda x:-x.get('sla_overdue_hours',0)),
            'critical': [i for i in open_i if i.get('sla_state')=='critical'],
            'at_risk':  [i for i in open_i if i.get('sla_state')=='at_risk'],
            'healthy':  [i for i in open_i if i.get('sla_state')=='healthy'],
        },
        'sla_summary': get_sla_summary(open_i),
    }


def get_analytics_data(issues_raw, user):
    issues = _filter_tags(issues_raw, user.get('tags'))
    annotate_issues(issues)
    by_tag, by_area, by_status = {}, {}, {}
    for i in issues:
        t=i.get('tag','other');   by_tag[t]    = by_tag.get(t,0)+1
        a=i.get('area','?');      by_area[a]   = by_area.get(a,0)+1
        s=i.get('status','open'); by_status[s] = by_status.get(s,0)+1
    open_i  = [i for i in issues if i.get('status')!='resolved']
    sla_sum = get_sla_summary(open_i)
    compliance = round((sla_sum.get('healthy',0)+sla_sum.get('at_risk',0))/max(sum(sla_sum.values()),1)*100,1)
    return {
        'issues':      issues,
        'by_tag':      by_tag,
        'by_area':     by_area,
        'by_status':   by_status,
        'top_areas':   sorted(by_area.items(),key=lambda x:-x[1])[:10],
        'sla_summary': sla_sum,
        'compliance':  compliance,
    }
