"""
gov_features/verify_resolution.py — Areapulse-7 integrated
Verified Resolution System — photo + GPS + confirmation before an issue closes.

Solves "false closure": an issue can't be marked truly resolved without proof
(after photo + GPS) plus a citizen/NGO/supervisor confirmation.

Routes (match portal /gov/api/ convention, guarded by require_gov):
  POST /gov/api/resolution/submit    {issue_id, after_photo, lat, lng, note}
  POST /gov/api/resolution/verify    {issue_id, verifier_type, verifier_id, approved}
  GET  /gov/api/resolution/pending
  GET  /gov/api/resolution/<issue_id>
"""

import time
from flask import Blueprint, request, jsonify

from auth import require_gov, current_user
from .audit_log import record

verify_bp = Blueprint("verify_resolution", __name__)

_resolutions = {}   # issue_id -> record


@verify_bp.route("/gov/api/resolution/submit", methods=["POST"])
@require_gov
def submit_resolution():
    u    = current_user()
    body = request.get_json(silent=True) or {}
    iid  = str(body.get("issue_id", ""))
    if not iid:
        return jsonify({"error": "issue_id required"}), 400

    after_photo = body.get("after_photo")
    lat, lng = body.get("lat"), body.get("lng")
    missing = []
    if not after_photo: missing.append("after_photo")
    if lat is None or lng is None: missing.append("gps")
    if missing:
        return jsonify({"error": "Proof required before closing", "missing": missing}), 422

    rec = {
        "issue_id": iid, "after_photo": after_photo,
        "lat": lat, "lng": lng, "note": str(body.get("note", "")),
        "submitted_by": u["name"], "submitted_at": time.time(),
        "status": "awaiting_verification", "verification": None,
    }
    _resolutions[iid] = rec
    record(action="resolution_submitted", issue_id=iid, actor=u["name"],
           dept=u.get("dept"), detail="Resolution submitted with photo + GPS, awaiting verification",
           meta={"lat": lat, "lng": lng, "has_photo": bool(after_photo)})
    return jsonify({"status": "ok", "resolution": rec})


@verify_bp.route("/gov/api/resolution/verify", methods=["POST"])
@require_gov
def verify_resolution():
    body = request.get_json(silent=True) or {}
    iid  = str(body.get("issue_id", ""))
    rec  = _resolutions.get(iid)
    if not rec:
        return jsonify({"error": "No resolution submitted for this issue"}), 404

    vtype    = body.get("verifier_type", "citizen")
    vid      = body.get("verifier_id", "")
    approved = bool(body.get("approved", False))
    rec["verification"] = {"verifier_type": vtype, "verifier_id": vid,
                           "approved": approved, "at": time.time()}
    rec["status"] = "verified_resolved" if approved else "verification_rejected"
    record(action="resolution_verified" if approved else "resolution_rejected",
           issue_id=iid, actor=f"{vtype}:{vid or 'anon'}",
           detail=("Confirmed fixed" if approved else "Rejected — issue reopened"),
           meta={"verifier_type": vtype, "approved": approved})
    return jsonify({"status": "ok", "resolution": rec})


@verify_bp.route("/gov/api/resolution/pending", methods=["GET"])
@require_gov
def pending():
    items = [r for r in _resolutions.values() if r["status"] == "awaiting_verification"]
    return jsonify({"pending": items, "count": len(items)})


@verify_bp.route("/gov/api/resolution/<issue_id>", methods=["GET"])
@require_gov
def get_resolution(issue_id):
    rec = _resolutions.get(str(issue_id))
    return jsonify({"exists": bool(rec), "resolution": rec})
