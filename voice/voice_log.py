"""
voice/voice_log.py
In-memory Voice History Log (same pattern as _adoptions / _escalations in the
portal files). Records every voice command, how it was interpreted, and what
action fired — so a user can review and reverse an action later.

Swap the _LOG list for a Firebase collection in production.
"""

import time
import uuid

_LOG = []          # list of dicts, newest last
MAX_ENTRIES = 500


def add_entry(portal, user, transcript, decision, command_id, action_taken, lang="en"):
    entry = {
        "id":           str(uuid.uuid4())[:8],
        "portal":       portal,
        "user":         user,
        "transcript":   transcript,
        "decision":     decision,          # act / clarify / repeat
        "command_id":   command_id,
        "action_taken": action_taken,      # human-readable
        "lang":         lang,
        "ts":           time.time(),
        "reversed":     False,
    }
    _LOG.append(entry)
    if len(_LOG) > MAX_ENTRIES:
        del _LOG[0:len(_LOG) - MAX_ENTRIES]
    return entry


def get_log(portal=None, user=None, limit=50):
    items = _LOG
    if portal:
        items = [e for e in items if e["portal"] == portal]
    if user:
        items = [e for e in items if e["user"] == user]
    return list(reversed(items[-limit:]))


def mark_reversed(entry_id):
    for e in _LOG:
        if e["id"] == entry_id:
            e["reversed"] = True
            return e
    return None
