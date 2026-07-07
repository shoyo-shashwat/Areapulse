"""
ngo_features/ngo_ops.py  — AreaPulse NGO Operations
=====================================================
All new NGO-specific operational endpoints.

Key design rules enforced here:
  1. NGOs CANNOT mark issues resolved — only government can.
  2. ngo_adopt() records NGO engagement WITHOUT touching issue lifecycle status.
  3. ngo_escalate() uses the same escalate_issue() DB function as gov, so it
     shows up in the gov portal's escalation view automatically.
  4. ngo_verify_resolution() records the NGO verdict but does NOT call
     update_issue_status('resolved') — the gov officer must close officially.
  5. All GET endpoints that NGOs need to read gov data use @require_auth,
     not @require_gov.

Register in app.py:
    from ngo_features.ngo_ops import ngo_ops_bp
    app.register_blueprint(ngo_ops_bp)
"""

import os
import time
import uuid
from flask import Blueprint, request, jsonify, render_template

from auth import require_ngo, require_auth, current_user

ngo_ops_bp = Blueprint("ngo_ops", __name__)

# ── In-memory stores  ─────────────────────────────────────────
# Pattern mirrors gov_features/verify_resolution.py.
# In production, replace with Postgres tables.

_adoptions        = {}   # str(issue_id) -> adoption dict
_evidence         = {}   # str(issue_id) -> [evidence dict, ...]
_escalations      = {}   # str(issue_id) -> escalation dict
_ngo_verifications = {}  # str(issue_id) -> verification dict


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _ctx():
    """Minimal template context for routes in this blueprint."""
    u = current_user()
    return {"cu": u, "maptiler_key": os.environ.get("MAPTILER_KEY", "")}


def _parse_location(body):
    """Extract lat/lng from request body, supporting both formats."""
    lat = body.get("lat")
    lng = body.get("lng")
    loc_str = body.get("location", "")
    if (lat is None or lng is None) and loc_str:
        try:
            parts = loc_str.split(",")
            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
        except Exception:
            lat, lng = None, None
    return lat, lng


# ─────────────────────────────────────────────────────────────
#  ADOPT ISSUE  (replaces the broken POST /ngo/commit)
# ─────────────────────────────────────────────────────────────

@ngo_ops_bp.route("/ngo/api/adopt", methods=["POST"])
@require_ngo
def ngo_adopt():
    """
    NGO adopts an issue as a community partner.

    CRITICAL: Does NOT change the issue's lifecycle status field.
    Records NGO engagement in _adoptions — a parallel track to the
    main issue workflow.
    """
    u    = current_user()
    body = request.get_json(silent=True) or {}
    iid  = body.get("issue_id")
    if not iid:
        return jsonify({"error": "issue_id required"}), 400

    adoption = {
        "issue_id":   str(iid),
        "ngo_id":     u["username"],
        "ngo_name":   u["name"],
        "plan":       body.get("plan", "").strip(),
        "volunteers": max(1, int(body.get("volunteers", 1))),
        "eta":        body.get("eta", "48h"),
        "adopted_at": time.time(),
        "updates":    [],
        "status":     "active",   # active | completed
    }
    _adoptions[str(iid)] = adoption

    return jsonify({
        "ok":      True,
        "adoption": adoption,
        "note":    "Issue status was NOT changed — gov lifecycle unaffected.",
    })


@ngo_ops_bp.route("/ngo/api/adoptions", methods=["GET"])
@require_ngo
def ngo_list_adoptions():
    """Return all issues adopted by the current NGO."""
    u    = current_user()
    mine = [a for a in _adoptions.values() if a["ngo_id"] == u["username"]]
    mine.sort(key=lambda x: x["adopted_at"], reverse=True)
    return jsonify({"adoptions": mine, "count": len(mine)})


@ngo_ops_bp.route("/ngo/api/adoption/update", methods=["POST"])
@require_ngo
def ngo_adoption_update():
    """Log a field update on an adopted issue — does NOT change issue status."""
    u    = current_user()
    body = request.get_json(silent=True) or {}
    iid  = str(body.get("issue_id", ""))
    text = body.get("text", "").strip()
    if not iid or not text:
        return jsonify({"error": "issue_id and text required"}), 400

    adoption = _adoptions.get(iid)
    if not adoption or adoption["ngo_id"] != u["username"]:
        # Auto-create a minimal adoption record if not found
        adoption = {
            "issue_id":   iid,
            "ngo_id":     u["username"],
            "ngo_name":   u["name"],
            "plan":       "",
            "volunteers": 1,
            "eta":        "",
            "adopted_at": time.time(),
            "updates":    [],
            "status":     "active",
        }
        _adoptions[iid] = adoption

    update = {
        "text": text,
        "by":   u["name"],
        "at":   time.time(),
    }
    adoption["updates"].append(update)
    return jsonify({"ok": True, "update": update})


# ─────────────────────────────────────────────────────────────
#  FIELD EVIDENCE
# ─────────────────────────────────────────────────────────────

@ngo_ops_bp.route("/ngo/api/evidence", methods=["POST"])
@require_ngo
def ngo_submit_evidence():
    """
    NGO submits GPS-tagged field evidence (photo + location + note).
    Separate from the gov resolution proof workflow.
    Both gov and NGO can read evidence via GET.
    """
    u    = current_user()
    body = request.get_json(silent=True) or {}
    iid  = str(body.get("issue_id", ""))
    if not iid:
        return jsonify({"error": "issue_id required"}), 400

    lat, lng = _parse_location(body)
    photo    = body.get("photo") or body.get("after_photo")
    note     = body.get("note", "").strip()

    record = {
        "id":           str(uuid.uuid4())[:8].upper(),
        "issue_id":     iid,
        "photo":        photo,
        "lat":          lat,
        "lng":          lng,
        "note":         note,
        "submitted_by": u["name"],
        "ngo_id":       u["username"],
        "submitted_at": time.time(),
        "has_photo":    bool(photo),
        "has_gps":      lat is not None and lng is not None,
    }

    _evidence.setdefault(iid, []).append(record)

    return jsonify({
        "ok":     True,
        "record": record,
        "count":  len(_evidence[iid]),
    })


@ngo_ops_bp.route("/ngo/api/evidence/<issue_id>", methods=["GET"])
@require_auth    # both gov and NGO can read field evidence
def get_evidence(issue_id):
    """Fetch all field evidence for an issue."""
    records = _evidence.get(str(issue_id), [])
    return jsonify({"evidence": records, "count": len(records)})


# ─────────────────────────────────────────────────────────────
#  NGO ESCALATION  (backend for the modal in ngo_portal.html)
# ─────────────────────────────────────────────────────────────

@ngo_ops_bp.route("/ngo/api/escalate", methods=["POST"])
@require_ngo
def ngo_escalate():
    """
    NGO formally escalates an issue to government.
    Calls escalate_issue() from database.py — same function gov uses —
    so it appears in the gov portal escalation view automatically.
    """
    try:
        from database import escalate_issue
    except ImportError:
        return jsonify({"error": "Database module not available"}), 500

    u    = current_user()
    body = request.get_json(silent=True) or {}
    iid  = body.get("issue_id") or body.get("id")
    if not iid:
        return jsonify({"error": "issue_id required"}), 400

    dept     = body.get("dept", "").strip()
    evidence = body.get("evidence", "").strip()
    attempts = max(0, int(body.get("attempts", 1)))
    reason   = (
        f"NGO escalation by {u['name']} ({u['username']}). "
        f"Dept: {dept or 'unspecified'}. "
        f"Contact attempts: {attempts}. "
        f"Evidence: {evidence[:300]}"
    )

    _escalations[str(iid)] = {
        "issue_id":     str(iid),
        "dept":         dept,
        "evidence":     evidence,
        "attempts":     attempts,
        "escalated_by": u["name"],
        "ngo_id":       u["username"],
        "escalated_at": time.time(),
    }

    ok = escalate_issue(int(iid), reason)
    return jsonify({
        "ok":      ok,
        "id":      iid,
        "message": f"Issue #{iid} escalated to {dept or 'responsible department'}.",
    })


# ─────────────────────────────────────────────────────────────
#  NGO VERIFICATION QUEUE
# ─────────────────────────────────────────────────────────────

@ngo_ops_bp.route("/ngo/verify")
@require_ngo
def ngo_verify_page():
    """
    NGO verification queue.
    Shows issues where gov has submitted resolution proof and
    NGO co-verification is needed.
    """
    try:
        from gov_features.verify_resolution import _resolutions
    except ImportError:
        _resolutions = {}

    try:
        from database import get_issues, annotate_issues
        all_issues = get_issues(limit=500)
        annotate_issues(all_issues)
        issues_by_id = {str(i["id"]): i for i in all_issues}
    except Exception:
        issues_by_id = {}

    u = current_user()

    # Issues awaiting NGO verification (gov submitted proof, NGO hasn't verified yet)
    pending = []
    for rec in _resolutions.values():
        if rec.get("status") != "awaiting_verification":
            continue
        issue = issues_by_id.get(str(rec["issue_id"]))
        if not issue:
            continue
        # Filter to NGO's focus tags
        if u.get("tags") and issue.get("tag") not in u["tags"]:
            continue
        pending.append({**rec, "issue": issue})

    # Issues this NGO has already verified
    verified = [
        v for v in _ngo_verifications.values()
        if v.get("ngo_id") == u["username"]
    ]
    # Enrich verified with issue data
    for v in verified:
        v["issue"] = issues_by_id.get(str(v["issue_id"]), {})

    return render_template(
        "ngo/verify.html",
        pending=pending,
        verified=verified,
        pending_count=len(pending),
        verified_count=len(verified),
        **_ctx(),
    )


@ngo_ops_bp.route("/ngo/api/resolution/verify", methods=["POST"])
@require_ngo
def ngo_verify_resolution():
    """
    NGO submits its co-verification verdict on a gov-resolved issue.

    CRITICAL DESIGN RULE:
      - approved=True  → records NGO approval; gov can now officially close
      - approved=False → records rejection; gov must re-inspect

    This endpoint NEVER calls update_issue_status('resolved').
    Only the government closes issues.
    """
    try:
        from gov_features.verify_resolution import _resolutions
    except ImportError:
        _resolutions = {}

    u    = current_user()
    body = request.get_json(silent=True) or {}
    iid  = str(body.get("issue_id", ""))
    if not iid:
        return jsonify({"error": "issue_id required"}), 400

    approved = bool(body.get("approved", False))
    note     = body.get("note", "").strip()

    verification = {
        "issue_id":     iid,
        "approved":     approved,
        "verdict":      "approved" if approved else "rejected",
        "note":         note,
        "ngo_id":       u["username"],
        "ngo_name":     u["name"],
        "submitted_at": time.time(),
    }
    _ngo_verifications[iid] = verification

    # Update the resolution record so gov verify page shows NGO verdict
    if iid in _resolutions:
        _resolutions[iid]["ngo_verification"] = verification
        _resolutions[iid]["status"] = (
            "ngo_approved_pending_close" if approved
            else "ngo_rejected_needs_rework"
        )

    message = (
        f"Issue #{iid} — NGO verdict: {'APPROVED ✓' if approved else 'REJECTED ✗'}. "
        + ("Government can now officially close the issue." if approved
           else "Government has been notified to re-inspect.")
    )

    return jsonify({
        "ok":           True,
        "verdict":      "approved" if approved else "rejected",
        "message":      message,
        "issue_status": "unchanged — only gov can resolve",
    })


# ─────────────────────────────────────────────────────────────
#  GOV ACTIVITY TRANSPARENCY  (NGO reads gov work on their issues)
# ─────────────────────────────────────────────────────────────

@ngo_ops_bp.route("/ngo/api/gov-activity/<int:issue_id>", methods=["GET"])
@require_ngo
def ngo_get_gov_activity(issue_id):
    """
    NGO reads gov activity on a specific issue.
    Returns: assigned officer, status history, resolution proof status, SLA data.
    Does NOT expose base64 photo data.
    """
    try:
        from database import get_issue_by_id, annotate_issues
        from gov_features.verify_resolution import _resolutions
    except ImportError:
        return jsonify({"error": "Database not available"}), 500

    issue = get_issue_by_id(issue_id)
    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    annotate_issues([issue])

    # Sanitise resolution proof — never send base64 to NGO
    res_rec = _resolutions.get(str(issue_id))
    res_summary = None
    if res_rec:
        res_summary = {
            "status":       res_rec.get("status"),
            "submitted_by": res_rec.get("submitted_by"),
            "submitted_at": res_rec.get("submitted_at"),
            "has_photo":    res_rec.get("has_photo", False),
            "has_gps":      res_rec.get("has_gps", False),
            "note":         res_rec.get("note", ""),
        }

    return jsonify({
        "issue_id":         issue_id,
        "status":           issue.get("status"),
        "assigned_to":      issue.get("assigned_to"),
        "dept":             issue.get("dept"),
        "status_history":   issue.get("status_history", []),
        "sla_state":        issue.get("sla_state"),
        "remaining_hours":  issue.get("remaining_hours"),
        "sla_pct_used":     issue.get("sla_pct_used"),
        "resolution_proof": res_summary,
        "ngo_verification": _ngo_verifications.get(str(issue_id)),
        "field_evidence":   _evidence.get(str(issue_id), []),
    })