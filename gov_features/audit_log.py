"""
gov_features/audit_log.py  — Areapulse-7 integrated
Immutable, append-only action audit log.

Uses the portal's own auth (require_gov, current_user) and route conventions
(/gov/api/...). Registered as a blueprint in app.py.

record(...) is called by other feature modules to log actions.
"""

import time
import hashlib
import json
from flask import Blueprint, request, jsonify

from auth import require_gov, current_user

audit_bp = Blueprint("audit", __name__)

_CHAIN = []   # append-only list


def _hash(prev_hash, content):
    h = hashlib.sha256()
    h.update((prev_hash + json.dumps(content, sort_keys=True)).encode())
    return h.hexdigest()


def record(action, issue_id=None, actor=None, dept=None, detail=None, meta=None):
    """Append an immutable audit entry. Safe to call from anywhere."""
    prev_hash = _CHAIN[-1]["hash"] if _CHAIN else "GENESIS"
    content = {
        "seq":      len(_CHAIN),
        "action":   action,
        "issue_id": str(issue_id) if issue_id is not None else None,
        "actor":    actor or "system",
        "dept":     dept,
        "detail":   detail or "",
        "meta":     meta or {},
        "ts":       time.time(),
    }
    entry = dict(content)
    entry["prev_hash"] = prev_hash
    entry["hash"]      = _hash(prev_hash, content)
    _CHAIN.append(entry)
    return entry


@audit_bp.route("/gov/api/audit", methods=["GET"])
@require_gov
def get_audit():
    issue_id = request.args.get("issue_id")
    items = _CHAIN
    if issue_id:
        items = [e for e in _CHAIN if e.get("issue_id") == str(issue_id)]
    return jsonify({"entries": list(reversed(items)), "total": len(items)})


@audit_bp.route("/gov/api/audit/verify", methods=["GET"])
@require_gov
def verify_chain():
    prev = "GENESIS"
    for i, e in enumerate(_CHAIN):
        content = {k: e[k] for k in ("seq", "action", "issue_id", "actor", "dept", "detail", "meta", "ts")}
        if _hash(prev, content) != e["hash"] or e["prev_hash"] != prev:
            return jsonify({"intact": False, "broken_at": i, "total": len(_CHAIN)})
        prev = e["hash"]
    return jsonify({"intact": True, "total": len(_CHAIN)})
