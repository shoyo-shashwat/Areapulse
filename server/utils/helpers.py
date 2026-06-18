"""utils/helpers.py — shared formatting utilities."""
import time
from datetime import datetime


def time_ago(timestamp: float) -> str:
    delta = time.time() - timestamp
    if delta < 60:    return 'just now'
    if delta < 3600:  return f'{int(delta/60)}m ago'
    if delta < 86400: return f'{int(delta/3600)}h ago'
    return f'{int(delta/86400)}d ago'


def fmt_timestamp(timestamp: float) -> str:
    if not timestamp: return '—'
    return datetime.fromtimestamp(timestamp).strftime('%d %b %Y, %H:%M')


def severity_order(severity: str) -> int:
    return {'high': 0, 'medium': 1, 'low': 2}.get(severity, 3)


def status_color(status: str) -> str:
    return {'open':'blue','acknowledged':'amber','in_progress':'indigo',
            'resolved':'green','escalated':'red'}.get(status, 'gray')
