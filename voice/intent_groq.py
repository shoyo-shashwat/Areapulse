"""
voice/intent_groq.py
Layer 4: complex-intent extraction using Groq.

Used only when a command is an ACTION that needs entities pulled out of natural
speech, e.g. "assign the water leak in Chandni Chowk to DJB team one" ->
{action: assign, issue_hint: "water leak chandni chowk", team_hint: "DJB team one"}

If GROQ_API_KEY is missing or the call fails, returns None and the caller falls
back to the plain fuzzy-matched action (which will open the relevant modal so the
user finishes manually).
"""

import os
import json

GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def extract_intent(transcript, portal, context=None):
    """
    transcript : raw speech text (may be English/Hindi/Hinglish)
    portal     : "gov" | "ngo"
    context    : optional dict, e.g. {"issues":[...], "teams":[...]} to help matching
    returns    : dict intent or None
    """
    if not GROQ_KEY:
        return None

    context = context or {}
    if portal == "gov":
        actions = "escalate, assign, resolve, navigate, filter, query"
        entity_hint = (
            "issue_hint (text describing the issue or its id), "
            "dept (one of: MCD North, MCD South, DJB, PWD, BSES, Delhi Traffic Police, NDMC), "
            "team_hint (field team name/id if mentioned)"
        )
    else:
        actions = "adopt, update, escalate, impact_story, navigate, query"
        entity_hint = (
            "issue_hint (text describing the issue or its id), "
            "dept (one of: DJB, MCD North, MCD South, PWD, BSES, Delhi Traffic Police), "
            "update_text (any progress note the user dictated)"
        )

    prompt = (
        f"You are a voice command parser for a civic {portal} dashboard. "
        f"The user may speak English, Hindi, or mixed Hinglish. "
        f"Extract the intent from this command and return ONLY valid JSON, no markdown, no prose.\n\n"
        f"Command: \"{transcript}\"\n\n"
        f"Valid actions: {actions}.\n"
        f"Possible fields: action (required), {entity_hint}, view (for navigate: "
        f"dashboard/issues/dispatch/alerts/analytics for gov, gap/adoptions/drives/impact for ngo).\n"
        f"If a field is not present in the command, omit it.\n"
        f"Return JSON like: {{\"action\":\"escalate\",\"issue_hint\":\"water leak chandni chowk\",\"dept\":\"DJB\"}}"
    )

    try:
        import requests
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.1,
            },
            timeout=8,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[voice intent_groq] {e}")
        return None
