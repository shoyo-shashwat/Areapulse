"""services/sla_service.py — pure SLA business logic, no Flask imports."""
import time
from config.settings import SLA_HOURS


def calc_sla(issue):
    tag      = issue.get('tag', 'other')
    ts       = issue.get('timestamp', time.time())
    sla_h    = SLA_HOURS.get(tag, 120)
    sla_due  = ts + (sla_h * 3600)
    now      = time.time()
    remaining = sla_due - now
    elapsed   = now - ts

    if remaining <= 0:
        return {
            'sla_hours': sla_h, 'sla_due_at': sla_due,
            'sla_overdue_hours': round(abs(remaining) / 3600, 1),
            'sla_state': 'breached', 'sla_pct_used': 100.0,
            'remaining_seconds': 0, 'remaining_hours': 0,
        }
    pct   = min((elapsed / (sla_h * 3600)) * 100, 100)
    state = 'critical' if pct >= 75 else 'at_risk' if pct >= 50 else 'healthy'
    return {
        'sla_hours': sla_h, 'sla_due_at': sla_due,
        'sla_overdue_hours': 0, 'sla_state': state,
        'sla_pct_used': round(pct, 1),
        'remaining_seconds': max(remaining, 0),
        'remaining_hours': max(remaining / 3600, 0),
    }


def annotate_issues(issues):
    for i in issues:
        if i.get('status') == 'resolved':
            i.update({'sla_state':'healthy','sla_overdue_hours':0,'sla_pct_used':0,'remaining_hours':0})
        else:
            i.update(calc_sla(i))
    return issues


def get_sla_summary(issues):
    s = {'healthy': 0, 'at_risk': 0, 'critical': 0, 'breached': 0}
    for i in issues:
        if i.get('status') != 'resolved':
            st = i.get('sla_state', 'healthy')
            if st in s:
                s[st] += 1
    return s


def format_remaining(seconds):
    if seconds <= 0:
        return f'OVERDUE +{int(abs(seconds)/3600)}h'
    if seconds < 3600:
        return f'{int(seconds/60)}m'
    if seconds < 86400:
        return f'{int(seconds/3600)}h {int((seconds%3600)/60)}m'
    return f'{int(seconds/86400)}d {int((seconds%86400)/3600)}h'
