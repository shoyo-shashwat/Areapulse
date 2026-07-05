"""
voice/commands_ngo.py
NGO Portal voice command dictionary — English + Hindi + Hinglish.
Maps trigger phrases to actions executed by existing ngo_app.js functions.
"""

NGO_COMMANDS = [
    # ---- NAVIGATION ----
    {"id": "nav_gap", "type": "navigate", "view": "gap",
     "phrases_en": ["show gap map", "open gap map", "show ignored issues", "show issues", "gap map", "show opportunities"],
     "phrases_hi": ["gap map dikhao", "ignore kiye issue dikhao", "issues dikhao", "map kholo"]},

    {"id": "nav_adoptions", "type": "navigate", "view": "adoptions",
     "phrases_en": ["my adoptions", "show my adoptions", "open adoptions", "show adopted issues", "my issues"],
     "phrases_hi": ["mere adoptions dikhao", "adopt kiye issue dikhao", "mere issue dikhao"]},

    {"id": "nav_drives", "type": "navigate", "view": "drives",
     "phrases_en": ["show drives", "drive builder", "open drives", "create drive", "show campaigns", "volunteer drives"],
     "phrases_hi": ["drives dikhao", "drive banao", "campaign dikhao", "volunteer drive dikhao"]},

    {"id": "nav_impact", "type": "navigate", "view": "impact",
     "phrases_en": ["show impact", "impact dashboard", "open impact", "show my impact", "show donor report"],
     "phrases_hi": ["impact dikhao", "asar dikhao", "donor report dikhao", "mera impact dikhao"]},

    # ---- QUERIES ----
    {"id": "q_adopted", "type": "query", "metric": "total_adopted",
     "phrases_en": ["how many adopted", "adoption count", "how many issues adopted"],
     "phrases_hi": ["kitne adopt kiye", "kitne issue adopt", "adoption kitne"]},

    {"id": "q_resolved", "type": "query", "metric": "resolved",
     "phrases_en": ["how many resolved", "how many issues resolved", "resolved count"],
     "phrases_hi": ["kitne resolve hue", "kitne theek kiye"]},

    {"id": "q_volunteers", "type": "query", "metric": "total_volunteers",
     "phrases_en": ["how many volunteers", "volunteer count", "how many volunteers signed up"],
     "phrases_hi": ["kitne volunteer hai", "volunteer kitne", "kitne log jude"]},

    # ---- ACTIONS ----
    {"id": "act_adopt", "type": "action", "action": "adopt",
     "phrases_en": ["adopt this", "adopt issue", "adopt this issue", "claim this issue"],
     "phrases_hi": ["ye adopt karo", "isko adopt karo", "issue lelo", "ye issue lelo"]},

    {"id": "act_update", "type": "action", "action": "update",
     "phrases_en": ["log update", "add update", "log an update", "update this"],
     "phrases_hi": ["update daalo", "update karo", "progress daalo"]},

    {"id": "act_escalate", "type": "action", "action": "escalate",
     "phrases_en": ["escalate to government", "escalate this", "escalate", "send to government"],
     "phrases_hi": ["government ko bhejo", "escalate karo", "sarkar ko bhejo", "upar bhejo"]},

    {"id": "act_impact_story", "type": "action", "action": "impact_story",
     "phrases_en": ["generate impact story", "generate donor story", "create impact story", "generate story"],
     "phrases_hi": ["impact story banao", "donor story banao", "kahani banao"]},

    # ---- SESSION ----
    {"id": "sess_start", "type": "session", "action": "start_program",
     "phrases_en": ["start my program", "start work", "begin program", "start my day"],
     "phrases_hi": ["program shuru karo", "kaam shuru karo", "din shuru karo"]},

    {"id": "sess_logout", "type": "session", "action": "logout",
     "phrases_en": ["sign out", "log out", "logout"],
     "phrases_hi": ["logout karo", "sign out karo"]},
]
