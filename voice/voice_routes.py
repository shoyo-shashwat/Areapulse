"""
voice/voice_routes.py — Areapulse-7 integrated
Voice-agent interpret/log/reverse endpoints. Uses portal auth (current_user,
require_auth). Frontend posts a transcript, gets back a decision (act/clarify/
repeat) + resolved command; the frontend then calls existing portal JS.
"""

import os
import json
import requests as _requests

from flask import Blueprint, request, jsonify

from auth import require_auth, current_user
from .commands_gov import GOV_COMMANDS
from .commands_ngo import NGO_COMMANDS
from .fuzzy_match import match_command
from . import voice_log

try:
    from .intent_groq import extract_intent
except Exception:
    def extract_intent(*a, **k):
        return None

voice_bp = Blueprint("voice", __name__)

# ── Groq config ───────────────────────────────────────────────
_GROQ_KEY   = os.environ.get("GROQ_API_KEY", "")
_GROQ_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"

_PARSE_SYSTEM = """You are the voice command interpreter for AreaPulse — a Delhi civic issue management portal used by government officers and NGO workers.

Users speak in English, Hindi, Hinglish, or a mix. Your job is to map ANYTHING they say to the best available command.

CRITICAL RULES:
1. NEVER return "unknown" if you can make a reasonable guess. Always pick the closest match.
2. If someone mentions a Delhi area/locality/ward (like "Chandni Chowk", "Rohini", "Dwarka", "Saket", "Lajpat Nagar", "Karol Bagh", etc.) they want to filter issues by that area → use filter_area with the area name as arg.
3. If someone mentions a problem type, map it to filter_tag.
4. If someone says show/dikhao/open/kholo → they want to navigate or filter.
5. Interpret loosely. "Chandni Chowk ke issues dikhao" = filter_area Chandni Chowk. "pani nahi aa raha" = filter_tag water. "sadak toot gayi hai" = filter_tag pothole.

Return ONLY valid JSON with exactly two keys:
{"cmd": "<command>", "arg": <value or null>}

━━━ FULL COMMAND LIST ━━━

NAVIGATION (arg = null):
nav_dashboard     — dashboard, home, ghar, main page, shuru
nav_queue         — queue, issues, sabhi issues, list, antah, sari samasya
nav_progress      — progress, in progress, chal raha, kaam chal raha
nav_sla           — sla, deadline, samay, breach, overtime
nav_map           — map, naksha, live map, field map
nav_analytics     — analytics, graphs, charts, data, statistics, viश्लेषण
nav_reports       — reports, report, riport
nav_departments   — departments, vibhag, dept
nav_ngo_coord     — ngo, partners, ngo coordination, saathi
nav_notifications — notifications, alerts, suchna, khabar
nav_settings      — settings, setting, preferences
nav_verify        — verify, closure verify, band karo check
nav_accountability — accountability, audit, jawabdehi
nav_ai            — ai, copilot, assistant, ai se baat, sahayak
nav_teams         — teams, team, meri team, apni team

FILTERS:
filter_area       — arg: area/locality name as spoken (e.g. "Chandni Chowk", "Rohini", "Dwarka", "Saket")
                    Use when user mentions any Delhi area, locality, ward, colony, or neighbourhood
filter_tag        — arg: one of: water | sewage | pothole | garbage | electricity | streetlight | traffic | noise | tree | other
                    water/pani/jal → water
                    sewage/naali/drain/moree/sewerage → sewage
                    pothole/sadak/road/gaddha/khudai → pothole
                    garbage/kachra/waste/safai/kuda → garbage
                    electricity/bijli/light/current/vidyut → electricity
                    streetlight/lamp/lamp post → streetlight
                    traffic/jam/signal/jaam → traffic
                    noise/awaaz/shor → noise
                    tree/ped/jungle → tree
filter_status     — arg: open | in_progress | resolved | escalated | acknowledged
                    open/khuli/nai → open
                    in progress/chal raha/shuru/active → in_progress
                    resolved/done/khatam/complete/band → resolved
                    escalated/urgent/emergency/tez → escalated
filter_severity   — arg: high | medium | low
filter_clear      — arg: null (show all, clear filter, sab dikhao)

SEARCH:
search_issues     — arg: search string (when user asks about something specific that isn't a filter — e.g. "find broken pipe near station")

ISSUE ACTIONS (arg = issue number as integer — extract from AP-141, "AP 141", "one forty one", "ek chaar ek"):
open_issue        — open/show/view/dikhao + issue number
issue_start       — start/begin/shuru/commence + issue number
issue_acknowledge — acknowledge/ack/dekha/noted + issue number
issue_resolve     — resolve/close/done/khatam/fix + issue number (ALWAYS use modal)
issue_reopen      — reopen/vapas kholo/phir se + issue number
issue_escalate    — escalate/urgent/emergency/upar bhejo + issue number
issue_deescalate  — de-escalate/neeche lao/deescalate + issue number
ngo_commit        — commit/adopt/le lo/ngo karega + issue number

BULK ACTIONS (arg = null):
bulk_start        — start all/sab shuru karo/sab active karo
bulk_resolve      — resolve all/sab khatam/sab close
bulk_escalate     — escalate all/sab urgent
bulk_select_all   — select all/sab chunna/sab select

EXPORTS (arg = null):
export_pdf        — pdf/download pdf/report download
export_csv        — csv/spreadsheet/excel download

MAP CONTROLS (arg = null):
map_heatmap       — heatmap/heat map/toggle heatmap
map_reset         — reset map/center map/wapas karo

TEAMS (arg = null):
teams_create      — new team/create team/naya team/team banao
teams_join        — join team/team join/code dalo/enter code

REPORTS (arg = null):
gen_report        — generate report/ai report/briefing/report banao
gen_donor_report  — donor report/ngo report/impact report

NOTIFICATIONS (arg = null):
notif_mark_read   — mark all read/sab padha/notifications clear

UTILITY (arg = null):
page_refresh      — refresh/reload/dobara/update
logout            — logout/sign out/nikal/exit/band karo
help              — help/commands/kya karo/madad
stop              — stop/chup/quiet/mic band

━━━ EXAMPLES ━━━
"Chandni Chowk ke issues dikhao" → {"cmd":"filter_area","arg":"Chandni Chowk"}
"Rohini mein kya chal raha hai" → {"cmd":"filter_area","arg":"Rohini"}
"Dwarka ke pothole dikhao" → {"cmd":"filter_area","arg":"Dwarka"}  
"bijli issues dikhao" → {"cmd":"filter_tag","arg":"electricity"}
"pani ki samasya" → {"cmd":"filter_tag","arg":"water"}
"naali band hai" → {"cmd":"filter_tag","arg":"sewage"}
"sadak toot gayi hai dikhao" → {"cmd":"filter_tag","arg":"pothole"}
"kachra issues" → {"cmd":"filter_tag","arg":"garbage"}
"ap131 dikhao" → {"cmd":"open_issue","arg":131}
"AP 141 shuru karo" → {"cmd":"issue_start","arg":141}
"issue 73 urgent hai" → {"cmd":"issue_escalate","arg":73}
"42 band karo" → {"cmd":"issue_resolve","arg":42}
"sab urgent issues" → {"cmd":"filter_status","arg":"escalated"}
"jo chal rahe hain dikhao" → {"cmd":"filter_status","arg":"in_progress"}
"dashboard kholo" → {"cmd":"nav_dashboard","arg":null}
"naksha dikhao" → {"cmd":"nav_map","arg":null}
"queue dikhao" → {"cmd":"nav_queue","arg":null}
"progress board" → {"cmd":"nav_progress","arg":null}
"sab shuru karo" → {"cmd":"bulk_start","arg":null}
"broken pipe near metro" → {"cmd":"search_issues","arg":"broken pipe near metro"}
"logout karo" → {"cmd":"logout","arg":null}

IMPORTANT: When in doubt, pick the closest command. NEVER say unknown if there is any reasonable interpretation.
Return ONLY the JSON object. No markdown, no explanation, no extra text."""


@voice_bp.route("/api/voice/parse", methods=["POST"])
@require_auth
def voice_parse():
    """
    AI-powered natural language → structured command.
    Frontend posts {transcript, portal} and gets back {cmd, arg}.
    Uses Groq Llama-4; falls back to a simple local parser if Groq fails.
    """
    body       = request.get_json(silent=True) or {}
    transcript = (body.get("transcript") or "").strip()
    portal     = body.get("portal") or current_user().get("role") or "gov"

    if not transcript:
        return jsonify({"cmd": "unknown", "arg": None}), 200

    # ── Try Groq ──────────────────────────────────────────────
    if _GROQ_KEY:
        try:
            resp = _requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {_GROQ_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": _GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": _PARSE_SYSTEM},
                        {"role": "user",   "content": transcript},
                    ],
                    "max_tokens": 80,
                    "temperature": 0.0,
                },
                timeout=6,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            # Validate shape
            if "cmd" not in result:
                raise ValueError("missing cmd")
            return jsonify(result), 200
        except Exception as e:
            print(f"[voice/parse] Groq failed: {e} — using local fallback")

    # ── Local fallback ────────────────────────────────────────
    return jsonify(_local_parse(transcript)), 200


# Known Delhi localities for local fallback area detection
_DELHI_AREAS = [
    'chandni chowk', 'rohini', 'dwarka', 'saket', 'lajpat nagar', 'karol bagh',
    'connaught place', 'janakpuri', 'pitampura', 'shahdara', 'preet vihar',
    'mayur vihar', 'vasant kunj', 'malviya nagar', 'hauz khas', 'green park',
    'south extension', 'greater kailash', 'nehru place', 'okhla', 'rajouri garden',
    'patel nagar', 'kirti nagar', 'moti nagar', 'punjabi bagh', 'ashok vihar',
    'model town', 'civil lines', 'paharganj', 'new delhi', 'old delhi',
    'laxmi nagar', 'dilshad garden', 'geeta colony', 'vivek vihar', 'krishna nagar',
    'uttam nagar', 'vikaspuri', 'subhash nagar', 'tilak nagar', 'tagore garden',
    'narela', 'bawana', 'alipur', 'burari', 'mukherjee nagar', 'adarsh nagar',
    'shalimar bagh', 'wazirpur', 'saraswati vihar', 'paschim vihar', 'nilothi',
    'mehrauli', 'chattarpur', 'sultanpur', 'lado sarai', 'ghitorni', 'arjangarh',
    'badarpur', 'jasola', 'jaitpur', 'sangam vihar', 'govindpuri', 'kalkaji',
    'nehru nagar', 'east of kailash', 'defence colony', 'jangpura', 'lodi colony',
    'safdarjung', 'rk puram', 'munirka', 'ber sarai', 'neb sarai',
]


def _local_parse(t):
    """Keyword fallback when Groq is unavailable. Handles area names, tags, actions."""
    import re
    tl = t.lower()

    # Extract issue number (handles ap-141, ap141, standalone digits)
    num = None
    m = re.search(r'(?<![\d])(\d{2,5})(?![\d])', re.sub(r'[a-zA-Z]', ' ', tl))
    if not m:
        m = re.search(r'(\d{2,5})', tl)
    if m:
        num = int(m.group(1))

    # 1. AREA NAMES — check first (most specific)
    for area in _DELHI_AREAS:
        if area in tl:
            proper = ' '.join(w.capitalize() for w in area.split())
            return {'cmd': 'filter_area', 'arg': proper}

    # 2. ISSUE ACTIONS (need a number)
    if any(w in tl for w in ['start','shuru','begin','chalu karo']) and num:
        return {'cmd':'issue_start', 'arg':num}
    if any(w in tl for w in ['resolve','khatam','band karo','close','fix']) and num:
        return {'cmd':'issue_resolve', 'arg':num}
    if any(w in tl for w in ['escalate','urgent karo']) and num and 'de' not in tl:
        return {'cmd':'issue_escalate', 'arg':num}
    if any(w in tl for w in ['de-escalate','deescalate','neeche lao','de escalate']) and num:
        return {'cmd':'issue_deescalate', 'arg':num}
    if any(w in tl for w in ['acknowledge','ack','dekha']) and num:
        return {'cmd':'issue_acknowledge', 'arg':num}
    if any(w in tl for w in ['reopen','vapas kholo','phir se']) and num:
        return {'cmd':'issue_reopen', 'arg':num}
    if any(w in tl for w in ['dikhao','kholo','open','show','view','dekho']) and num:
        return {'cmd':'open_issue', 'arg':num}

    # 3. TAGS
    if any(w in tl for w in ['bijli','electricity','light','vidyut','current']):
        return {'cmd':'filter_tag','arg':'electricity'}
    if any(w in tl for w in ['pani','water','jal','nali pani']):
        return {'cmd':'filter_tag','arg':'water'}
    if any(w in tl for w in ['naali','sewage','drain','moree','sewerage','nali']):
        return {'cmd':'filter_tag','arg':'sewage'}
    if any(w in tl for w in ['sadak','pothole','road','khudai','gaddha','toot']):
        return {'cmd':'filter_tag','arg':'pothole'}
    if any(w in tl for w in ['kachra','garbage','waste','safai','kuda','gandagi']):
        return {'cmd':'filter_tag','arg':'garbage'}
    if any(w in tl for w in ['traffic','jam','signal','jaam']):
        return {'cmd':'filter_tag','arg':'traffic'}
    if any(w in tl for w in ['noise','shor','awaaz','dhwani']):
        return {'cmd':'filter_tag','arg':'noise'}

    # 4. STATUS FILTERS
    if any(w in tl for w in ['escalated','urgent','emergency','tez']):
        return {'cmd':'filter_status','arg':'escalated'}
    if any(w in tl for w in ['resolved','complete','khatam','band']):
        return {'cmd':'filter_status','arg':'resolved'}
    if any(w in tl for w in ['in progress','chal raha','active','chalu']):
        return {'cmd':'filter_status','arg':'in_progress'}

    # 5. NAVIGATION
    if any(w in tl for w in ['dashboard','ghar','home','main']):
        return {'cmd':'nav_dashboard','arg':None}
    if any(w in tl for w in ['queue','issues','sabhi','list','antah']):
        return {'cmd':'nav_queue','arg':None}
    if any(w in tl for w in ['progress','chal raha','kaam']):
        return {'cmd':'nav_progress','arg':None}
    if any(w in tl for w in ['map','naksha','naqsha']):
        return {'cmd':'nav_map','arg':None}
    if any(w in tl for w in ['sla','deadline','samay']):
        return {'cmd':'nav_sla','arg':None}
    if any(w in tl for w in ['analytic','graph','chart','data']):
        return {'cmd':'nav_analytics','arg':None}
    if any(w in tl for w in ['team','group']):
        return {'cmd':'nav_teams','arg':None}
    if any(w in tl for w in ['notif','suchna','alert']):
        return {'cmd':'nav_notifications','arg':None}
    if any(w in tl for w in ['report','riport']):
        return {'cmd':'nav_reports','arg':None}
    if any(w in tl for w in ['setting']):
        return {'cmd':'nav_settings','arg':None}

    # 6. BULK
    if any(w in tl for w in ['sab shuru','start all','all start']):
        return {'cmd':'bulk_start','arg':None}
    if any(w in tl for w in ['sab khatam','resolve all','all resolve']):
        return {'cmd':'bulk_resolve','arg':None}

    # 7. UTIL
    if any(w in tl for w in ['refresh','reload','dobara']):
        return {'cmd':'page_refresh','arg':None}
    if any(w in tl for w in ['logout','sign out','nikal','exit']):
        return {'cmd':'logout','arg':None}
    if any(w in tl for w in ['help','kya kar','madad']):
        return {'cmd':'help','arg':None}

    # Last resort: if we couldn't match but there's a number, open that issue
    if num:
        return {'cmd':'open_issue','arg':num}

    return {'cmd':'nav_queue','arg':None}  # best guess — show issues




def _uname():
    u = current_user()
    return u.get("username") or u.get("name") or "user"


def _serialize_cmd(cmd):
    if not cmd:
        return None
    keep = ("id", "type", "view", "metric", "field", "value", "action", "sensitive")
    return {k: cmd[k] for k in keep if k in cmd}


@voice_bp.route("/api/voice/interpret", methods=["POST"])
@require_auth
def interpret():
    body       = request.get_json(silent=True) or {}
    u          = current_user()
    portal     = body.get("portal") or u.get("role") or "gov"
    transcript = (body.get("transcript") or "").strip()
    lang       = body.get("lang", "en")
    want_complex = bool(body.get("complex", False))
    context    = body.get("context") or {}

    if not transcript:
        return jsonify({"decision": "repeat", "reason": "empty"}), 200

    commands = GOV_COMMANDS if portal == "gov" else NGO_COMMANDS
    result   = match_command(transcript, commands)
    best_cmd = result["best"]
    decision = result["decision"]

    groq_intent = None
    if decision == "act" and best_cmd and best_cmd.get("type") == "action" and want_complex:
        groq_intent = extract_intent(transcript, portal, context)

    voice_log.add_entry(portal=portal, user=_uname(), transcript=transcript,
                        decision=decision, command_id=(best_cmd["id"] if best_cmd else None),
                        action_taken=(best_cmd["id"] if best_cmd else "unmatched"), lang=lang)

    return jsonify({
        "decision": decision, "score": round(result["score"], 3),
        "command": _serialize_cmd(best_cmd),
        "alternatives": [_serialize_cmd(c) for c in result["alternatives"]],
        "groq_intent": groq_intent, "transcript": transcript,
    })


@voice_bp.route("/api/voice/log", methods=["GET"])
@require_auth
def get_voice_log():
    u = current_user()
    portal = u.get("role") or "gov"
    return jsonify({"log": voice_log.get_log(portal=portal, user=_uname(), limit=50)})


@voice_bp.route("/api/voice/reverse", methods=["POST"])
@require_auth
def reverse():
    body = request.get_json(silent=True) or {}
    entry = voice_log.mark_reversed(body.get("entry_id", ""))
    if not entry:
        return jsonify({"error": "not found"}), 404
    return jsonify({"status": "ok", "entry": entry})