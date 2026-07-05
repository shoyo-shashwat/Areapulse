"""
gov_features/auto_escalation.py — Areapulse-7 integrated
Automatic time-based escalation ladder (24h->Supervisor, 48h->AC, 72h->Commissioner+public).
Writes each escalation to the immutable audit log.

start_sweeper(get_issues_fn) is called once from app.py __main__.
Routes guarded by require_gov, using /gov/api/ convention.
"""

import time
import threading
from flask import Blueprint, request, jsonify

from auth import require_gov
from .audit_log import record

auto_esc_bp = Blueprint("auto_esc", __name__)

TIERS = [
    {"name": "Supervisor",             "hours": 24, "level": 1},
    {"name": "Assistant Commissioner", "hours": 48, "level": 2},
    {"name": "Commissioner",           "hours": 72, "level": 3, "public": True},
]
SEVERITY_MULT = {"high": 1.0, "medium": 2.0, "low": 3.0}

_state = {}
_config = {"enabled": True, "sweep_seconds": 60}
_sweeper_started = False


def _evaluate(issue):
    iid = str(issue.get("id", ""))
    if not iid:
        return
    if issue.get("status") in ("resolved",):
        return
    ts = float(issue.get("timestamp", time.time()))
    age_h = (time.time() - ts) / 3600.0
    mult = SEVERITY_MULT.get(issue.get("severity", "medium"), 2.0)
    cur = _state.get(iid, {"level": 0, "history": [], "public": False})
    for tier in TIERS:
        if age_h >= tier["hours"] * mult and cur["level"] < tier["level"]:
            cur["level"] = tier["level"]
            if tier.get("public"):
                cur["public"] = True
            cur["history"].append({"tier": tier["name"], "level": tier["level"],
                                    "at": time.time(), "age_hours": round(age_h, 1)})
            record(action="auto_escalation", issue_id=iid, actor="system (auto-escalation)",
                   dept=issue.get("area", ""),
                   detail=f"Auto-escalated to {tier['name']} after {round(age_h,1)}h unresolved",
                   meta={"tier": tier["name"], "level": tier["level"], "severity": issue.get("severity")})
    _state[iid] = cur


def start_sweeper(get_issues_fn):
    global _sweeper_started
    if _sweeper_started:
        return
    _sweeper_started = True

    def _loop():
        while True:
            try:
                if _config["enabled"]:
                    for issue in (get_issues_fn() or []):
                        _evaluate(issue)
            except Exception as e:
                print(f"[auto-escalation] sweep error: {e}")
            time.sleep(_config["sweep_seconds"])

    threading.Thread(target=_loop, daemon=True).start()
    print("[portal] ✓ Auto-escalation sweeper started")


@auto_esc_bp.route("/gov/api/auto-escalations", methods=["GET"])
@require_gov
def get_auto_escalations():
    tiers_count = {1: 0, 2: 0, 3: 0}
    public_issues = []
    for iid, st in _state.items():
        if st["level"] in tiers_count:
            tiers_count[st["level"]] += 1
        if st.get("public"):
            public_issues.append(iid)
    return jsonify({"config": _config, "escalations": _state, "summary": {
        "supervisor": tiers_count[1], "assistant_commissioner": tiers_count[2],
        "commissioner": tiers_count[3], "public_flagged": public_issues}})


@auto_esc_bp.route("/gov/api/auto-escalations/config", methods=["POST"])
@require_gov
def set_config():
    body = request.get_json(silent=True) or {}
    if "enabled" in body:
        _config["enabled"] = bool(body["enabled"])
    if "sweep_seconds" in body:
        _config["sweep_seconds"] = max(10, int(body["sweep_seconds"]))
    return jsonify({"status": "ok", "config": _config})
