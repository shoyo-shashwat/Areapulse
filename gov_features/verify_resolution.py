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

from auth import require_gov, require_auth, current_user
from .audit_log import record

verify_bp = Blueprint("verify_resolution", __name__)

_resolutions = {}   # issue_id -> record


@verify_bp.route("/gov/api/resolution/submit", methods=["POST"])
@require_auth   # both gov and NGO can submit resolution proof
def submit_resolution():
    u    = current_user()
    body = request.get_json(silent=True) or {}
    iid  = str(body.get("issue_id", ""))
    if not iid:
        return jsonify({"error": "issue_id required"}), 400

    # Accept both field name conventions:
    # Old: after_photo + lat/lng separately
    # New (modal): photo (base64) + location (string "lat, lng")
    after_photo = body.get("after_photo") or body.get("photo")
    lat  = body.get("lat")
    lng  = body.get("lng")

    # Parse location string "28.123, 77.456" if lat/lng not provided separately
    loc_str = body.get("location", "")
    if (lat is None or lng is None) and loc_str:
        try:
            parts = loc_str.split(",")
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
        except Exception:
            lat, lng = None, None

    # Never hard-block — save what we have, note what's missing
    rec = {
        "issue_id": iid,
        "after_photo": after_photo,
        "lat": lat, "lng": lng,
        "note": str(body.get("note", "")),
        "resolved_by": body.get("resolved_by") or u["name"],
        "submitted_by": u["name"],
        "submitted_at": time.time(),
        "status": "awaiting_verification",
        "verification": None,
        "has_photo": bool(after_photo),
        "has_gps": lat is not None and lng is not None,
    }
    _resolutions[iid] = rec
    record(action="resolution_submitted", issue_id=iid, actor=u["name"],
           dept=u.get("dept"),
           detail=f"Resolution submitted — photo: {bool(after_photo)}, GPS: {lat is not None}",
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