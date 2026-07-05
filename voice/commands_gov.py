"""
voice/commands_gov.py
Government Portal voice command dictionary — English + Hindi + Hinglish.

Each command maps a list of trigger phrases (both languages) to a structured
action that the frontend voice_agent.js knows how to execute by calling the
EXISTING functions (showView, submitEscalate, quickResolve, etc.).

action types:
  navigate  -> calls showView(view)
  query     -> reads already-loaded data aloud (no data change)
  action    -> calls an existing mutating function (needs undo)
  session   -> shift/login helpers
"""

GOV_COMMANDS = [
    # ---- NAVIGATION (zero-risk) ----
    {"id": "nav_dashboard", "type": "navigate", "view": "dashboard",
     "phrases_en": ["show dashboard", "open dashboard", "command centre", "command center", "home", "main screen", "go to dashboard"],
     "phrases_hi": ["dashboard dikhao", "dashboard kholo", "home dikhao", "mukhya screen", "command centre dikhao"]},

    {"id": "nav_issues", "type": "navigate", "view": "issues",
     "phrases_en": ["show issues", "open issues", "issues board", "show live issues", "show complaints", "live feed", "show me issues"],
     "phrases_hi": ["issues dikhao", "shikayat dikhao", "complaints dikhao", "issues kholo", "live issues dikhao"]},

    {"id": "nav_dispatch", "type": "navigate", "view": "dispatch",
     "phrases_en": ["show dispatch", "open dispatch", "field dispatch", "show teams", "field teams", "show team"],
     "phrases_hi": ["dispatch dikhao", "team dikhao", "field team dikhao", "teams kholo"]},

    {"id": "nav_alerts", "type": "navigate", "view": "alerts",
     "phrases_en": ["show alerts", "predictive alerts", "show predictions", "show risk", "risk alerts", "what's critical", "show critical"],
     "phrases_hi": ["alerts dikhao", "khatra dikhao", "risk dikhao", "predictions dikhao", "critical dikhao"]},

    {"id": "nav_analytics", "type": "navigate", "view": "analytics",
     "phrases_en": ["show analytics", "show graphs", "show charts", "show reports", "analytics", "show statistics", "show performance"],
     "phrases_hi": ["analytics dikhao", "graph dikhao", "charts dikhao", "report dikhao", "aankde dikhao", "performance dikhao"]},

    # ---- QUERIES (read-only, spoken back) ----
    {"id": "q_breached", "type": "query", "metric": "sla_breached",
     "phrases_en": ["how many breached", "how many issues breached", "sla breach", "breach count", "how many sla breached"],
     "phrases_hi": ["kitne breach hue", "kitne sla breach", "breach kitne hai"]},

    {"id": "q_open", "type": "query", "metric": "total_open",
     "phrases_en": ["how many open", "how many open issues", "open count", "total open"],
     "phrases_hi": ["kitne open hai", "kitne issue open", "open kitne hai"]},

    {"id": "q_critical", "type": "query", "metric": "sla_critical",
     "phrases_en": ["how many critical", "critical count", "how many critical issues"],
     "phrases_hi": ["kitne critical hai", "critical kitne hai"]},

    {"id": "q_resolved", "type": "query", "metric": "resolved_today",
     "phrases_en": ["how many resolved", "resolved today", "how many resolved today"],
     "phrases_hi": ["kitne resolve hue", "aaj kitne theek hue", "resolved kitne"]},

    # ---- FILTERS (low-risk view change) ----
    {"id": "filter_high", "type": "filter", "field": "severity", "value": "high",
     "phrases_en": ["show high severity", "filter high", "only high", "high priority only"],
     "phrases_hi": ["high severity dikhao", "sirf high dikhao", "zyada gambhir dikhao"]},

    {"id": "filter_breached", "type": "filter", "field": "sla", "value": "breached",
     "phrases_en": ["show breached only", "filter breached", "only breached"],
     "phrases_hi": ["sirf breached dikhao", "breach wale dikhao"]},

    {"id": "filter_clear", "type": "filter", "field": "clear", "value": "",
     "phrases_en": ["clear filters", "reset filters", "show all", "remove filter"],
     "phrases_hi": ["filter hatao", "sab dikhao", "reset karo"]},

    # ---- ACTIONS (mutating -> undo required) ----
    # entity (issue id / dept / team) resolved by Groq intent layer when phrase is complex
    {"id": "act_escalate", "type": "action", "action": "escalate",
     "phrases_en": ["escalate this", "escalate issue", "escalate", "send to another department", "escalate to"],
     "phrases_hi": ["escalate karo", "isko escalate karo", "aage bhejo", "dusre department ko bhejo", "upar bhejo"]},

    {"id": "act_assign", "type": "action", "action": "assign",
     "phrases_en": ["assign this", "assign team", "assign to team", "dispatch team", "send team"],
     "phrases_hi": ["team bhejo", "assign karo", "isko assign karo", "team ko do"]},

    {"id": "act_resolve", "type": "action", "action": "resolve", "sensitive": True,
     "phrases_en": ["mark resolved", "resolve this", "mark as resolved", "close this issue", "mark complete"],
     "phrases_hi": ["resolve kar do", "theek ho gaya", "band karo", "isko resolve karo", "poora ho gaya"]},

    # ---- SESSION ----
    {"id": "sess_start", "type": "session", "action": "start_shift",
     "phrases_en": ["start my shift", "start work", "begin shift", "start my day", "clock in"],
     "phrases_hi": ["shift shuru karo", "kaam shuru karo", "duty shuru", "din shuru karo"]},

    {"id": "sess_logout", "type": "session", "action": "logout",
     "phrases_en": ["sign out", "log out", "logout", "end shift"],
     "phrases_hi": ["logout karo", "sign out karo", "shift khatam"]},
]
