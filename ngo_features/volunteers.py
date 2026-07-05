"""
ngo_features/volunteers.py — Areapulse-7 integrated
Volunteer roster, attendance, hours, leaderboard, portable record.
Uses portal auth (require_ngo, current_user) and /ngo/api/ convention.
"""

import time
import uuid
from flask import Blueprint, request, jsonify

from auth import require_ngo, current_user

volunteers_bp = Blueprint("volunteers", __name__)

_volunteers = {}
_sessions   = {}


@volunteers_bp.route("/ngo/api/volunteers/add", methods=["POST"])
@require_ngo
def add_volunteer():
    u    = current_user()
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    vid = "V-" + str(uuid.uuid4())[:6].upper()
    _volunteers[vid] = {
        "id": vid, "ngo_id": u["username"], "name": name,
        "phone": body.get("phone", ""), "skills": body.get("skills", ""),
        "total_hours": 0.0, "drives_count": 0, "tasks": [], "joined": time.time(),
    }
    return jsonify({"status": "ok", "volunteer": _volunteers[vid]})


@volunteers_bp.route("/ngo/api/volunteers", methods=["GET"])
@require_ngo
def list_volunteers():
    u = current_user()
    mine = [v for v in _volunteers.values() if v["ngo_id"] == u["username"]]
    mine.sort(key=lambda v: v["total_hours"], reverse=True)
    return jsonify({"volunteers": mine, "count": len(mine)})


@volunteers_bp.route("/ngo/api/volunteers/checkin", methods=["POST"])
@require_ngo
def checkin():
    body = request.get_json(silent=True) or {}
    vid, did = body.get("volunteer_id", ""), body.get("drive_id", "")
    if vid not in _volunteers:
        return jsonify({"error": "volunteer not found"}), 404
    _sessions[(vid, did)] = {"checkin_ts": time.time()}
    return jsonify({"status": "ok", "checked_in": True})


@volunteers_bp.route("/ngo/api/volunteers/checkout", methods=["POST"])
@require_ngo
def checkout():
    body = request.get_json(silent=True) or {}
    vid, did = body.get("volunteer_id", ""), body.get("drive_id", "")
    task = body.get("task", "")
    v = _volunteers.get(vid)
    if not v:
        return jsonify({"error": "volunteer not found"}), 404
    hours = body.get("hours")
    sess = _sessions.pop((vid, did), None)
    if hours is None and sess:
        hours = round((time.time() - sess["checkin_ts"]) / 3600.0, 2)
    hours = float(hours or 0)
    v["total_hours"] = round(v["total_hours"] + hours, 2)
    v["drives_count"] += 1
    v["tasks"].append({"drive_id": did, "task": task, "hours": hours, "at": time.time()})
    return jsonify({"status": "ok", "volunteer": v})


@volunteers_bp.route("/ngo/api/volunteers/leaderboard", methods=["GET"])
@require_ngo
def leaderboard():
    u = current_user()
    mine = [v for v in _volunteers.values() if v["ngo_id"] == u["username"]]
    mine.sort(key=lambda v: v["total_hours"], reverse=True)
    board = [{"rank": i + 1, "id": v["id"], "name": v["name"],
              "total_hours": v["total_hours"], "drives_count": v["drives_count"]}
             for i, v in enumerate(mine[:20])]
    return jsonify({"leaderboard": board})


@volunteers_bp.route("/ngo/api/volunteers/<vid>/record", methods=["GET"])
@require_ngo
def portable_record(vid):
    v = _volunteers.get(vid)
    if not v:
        return jsonify({"exists": False}), 404
    return jsonify({"exists": True, "record": {
        "volunteer_id": v["id"], "name": v["name"], "total_hours": v["total_hours"],
        "drives_count": v["drives_count"], "member_since": v["joined"],
        "verified_by": v["ngo_id"], "tasks": v["tasks"][-10:]}})
