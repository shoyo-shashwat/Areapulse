"""
AI engine — Groq Llama-4-Scout vision for image analysis, Q&A, and insights.
Gracefully degrades when GROQ_API_KEY is not set (returns 503-style errors).
"""
import os, json, re, time

_client = None
_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'

try:
    from groq import Groq
    if os.environ.get('GROQ_API_KEY'):
        _client = Groq(api_key=os.environ['GROQ_API_KEY'])
        print(f'[ai_engine] Groq enabled · model={_MODEL}')
except Exception as e:
    print(f'[ai_engine] Groq not available: {e}')


# ═══════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════
def is_available():
    return _client is not None


def provider_name():
    return 'Groq' if _client else 'none'


def model_name():
    return _MODEL if _client else None


# ═══════════════════════════════════════════════════════
#  IMAGE ANALYSIS
# ═══════════════════════════════════════════════════════
_VISION_PROMPT = """You are AreaPulse, a civic issue detection AI for Delhi.

A citizen uploaded this photo because they see a civic problem. Identify it confidently. Even subtle issues count: cracked roads, garbage piles, dim lights, exposed wires, leaking pipes, fallen branches, blocked drains, anything resembling municipal neglect.

Respond with ONLY valid JSON. No markdown, no preamble:
{
  "category": "pothole|water|garbage|streetlight|traffic|noise|sewage|electricity|tree|other",
  "severity": "low|medium|high",
  "confidence": <integer 70-98>,
  "description": "<one clear sentence describing what you see, max 25 words>",
  "source": "groq-llama4-scout"
}"""


def analyze_image(image_b64, mime='image/jpeg'):
    """Groq Llama-4-Scout vision → classify a civic-issue photo."""
    if not _client:
        return {
            'error': 'AI vision not configured. Set GROQ_API_KEY in your .env file.',
            '_status': 'not_configured',
        }

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{image_b64}'}},
                {'type': 'text', 'text': _VISION_PROMPT},
            ]}],
            max_tokens=400,
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or '').strip()
        parsed = _extract_json(raw)
        if not parsed:
            return {'error': 'AI returned unparseable response', 'raw': raw[:200], '_status': 'parse_error'}
        parsed.setdefault('source', 'groq-llama4-scout')
        return parsed
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}', '_status': 'server_error'}


# ═══════════════════════════════════════════════════════
#  Q&A
# ═══════════════════════════════════════════════════════
def ask_question(question, context_issues=None):
    """Free-form Q&A about Delhi civic issues, optionally grounded in current issues."""
    if not _client:
        return {'error': 'AI not configured', '_status': 'not_configured'}

    context = ''
    if context_issues:
        context = '\n\nCurrent issues snapshot (' + str(len(context_issues)) + ' total):\n'
        for i in context_issues[:15]:
            context += f"- [{i.get('tag','other')}/{i.get('severity','?')}] {i.get('area','?')}: {i.get('description','')[:80]}\n"

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {'role': 'system', 'content': 'You are AreaPulse, an AI civic-data assistant for Delhi. Answer concisely (2-4 sentences). Cite specific areas/issues from the context when relevant.'},
                {'role': 'user', 'content': question + context},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        return {'answer': (resp.choices[0].message.content or '').strip(), 'source': 'groq-llama4-scout'}
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}', '_status': 'server_error'}


# ═══════════════════════════════════════════════════════
#  INSIGHTS / SUMMARY
# ═══════════════════════════════════════════════════════
def summarize_landscape(by_tag, by_severity, by_status):
    """One-paragraph AI summary of the current issue landscape."""
    if not _client:
        return None

    stats_text = (
        f"Total issues by type: {dict(sorted(by_tag.items(), key=lambda x: -x[1]))}\n"
        f"By severity: {by_severity}\n"
        f"By status: {by_status}"
    )

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {'role': 'system', 'content': 'You are AreaPulse civic analytics. Given issue stats, write a single-paragraph executive summary (2-3 sentences) noting the most urgent pattern and one actionable recommendation.'},
                {'role': 'user', 'content': stats_text},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        return (resp.choices[0].message.content or '').strip()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════
#  COMPLAINT LETTER DRAFTING
# ═══════════════════════════════════════════════════════
_AUTHORITY_MAP = {
    'pothole':     {'name': 'PWD Delhi (Public Works Department)',         'email': 'secretary-pwd@nic.in'},
    'water':       {'name': 'Delhi Jal Board',                              'email': 'cmo@delhijalboard.in'},
    'garbage':     {'name': 'Municipal Corporation of Delhi (MCD)',         'email': 'pgms@mcdonline.nic.in'},
    'streetlight': {'name': 'MCD Lighting Department',                      'email': 'pgms@mcdonline.nic.in'},
    'traffic':     {'name': 'Delhi Traffic Police',                         'email': 'cp.delhipolice@nic.in'},
    'noise':       {'name': 'Delhi Pollution Control Committee',            'email': 'dpcc@nic.in'},
    'sewage':      {'name': 'Delhi Jal Board (Sewerage Division)',          'email': 'cmo@delhijalboard.in'},
    'electricity': {'name': 'BSES Delhi',                                   'email': 'customercare@bsesdelhi.com'},
    'tree':        {'name': 'Forest Department, Delhi',                     'email': 'dofdelhi@nic.in'},
    'other':       {'name': 'Office of the District Magistrate, Delhi',     'email': 'dm.newdelhi@delhi.gov.in'},
}


def get_authority(tag):
    """Map an issue tag to the responsible authority."""
    return _AUTHORITY_MAP.get(tag or 'other', _AUTHORITY_MAP['other'])


def draft_complaint(issue, citizen_name=None, language='english'):
    """
    Generate a formal complaint letter for an issue.

    Returns: {'subject': str, 'body_html': str, 'body_text': str, 'authority': {...}}
    """
    authority = get_authority(issue.get('tag', 'other'))
    citizen = citizen_name or issue.get('user') or 'Concerned Citizen'
    area     = issue.get('area', 'Delhi')
    severity = (issue.get('severity') or 'medium').upper()
    desc     = issue.get('description', '')
    landmark = issue.get('landmark', '')
    lat      = issue.get('lat', '')
    lng      = issue.get('lng', '')
    issue_id = issue.get('id', '')
    tag      = issue.get('tag', 'other').replace('_', ' ').title()
    today    = time.strftime('%d %B %Y')

    # Fallback letter — works even if Groq is unavailable
    fallback_text = _fallback_letter(citizen, area, severity, desc, landmark, tag, authority, today, issue_id, lat, lng)
    fallback_html = _text_to_html(fallback_text)
    subject_fallback = f'Civic Complaint · {tag} in {area} · Ref #AP-{issue_id}'

    if not _client:
        return {
            'subject':   subject_fallback,
            'body_html': fallback_html,
            'body_text': fallback_text,
            'authority': authority,
            'source':    'template',
        }

    prompt = f"""Write a formal civic complaint letter for the Indian government in {language}.

ISSUE DETAILS:
- Reference: #AP-{issue_id}
- Date: {today}
- Citizen: {citizen}
- Issue type: {tag}
- Severity: {severity}
- Area: {area}
- Landmark: {landmark or 'N/A'}
- Coordinates: {lat}, {lng}
- Description: {desc}
- Filed via: AreaPulse civic platform

ADDRESSED TO: {authority['name']}

REQUIREMENTS:
- Formal, respectful Indian bureaucratic tone
- 4 short paragraphs maximum
- Subject line first (start with "Subject:")
- Para 1: state the issue and reference number
- Para 2: location details and what citizens are facing
- Para 3: respectfully request specific action with a reasonable timeline
- Para 4: closing with citizen name and AreaPulse reference
- No markdown, no asterisks. Plain text only.
- Do NOT invent contact details or facts not provided above.
"""

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {'role': 'system', 'content': 'You are an expert civic complaint letter drafter for Indian municipal authorities. You write in formal, respectful, action-oriented language.'},
                {'role': 'user',   'content': prompt},
            ],
            max_tokens=700,
            temperature=0.4,
        )
        raw = (resp.choices[0].message.content or '').strip()
        if not raw:
            raise ValueError('empty response from Groq')

        # Extract subject + body
        subject = subject_fallback
        body = raw
        first_line = raw.split('\n', 1)[0].strip()
        if first_line.lower().startswith('subject:'):
            subject = first_line.split(':', 1)[1].strip()
            body = raw.split('\n', 1)[1].strip() if '\n' in raw else raw

        body_html = _text_to_html(body)
        return {
            'subject':   subject,
            'body_html': body_html,
            'body_text': body,
            'authority': authority,
            'source':    'groq-llama4-scout',
        }
    except Exception as e:
        print(f'[ai_engine] draft_complaint Groq fallback due to: {e}')
        return {
            'subject':   subject_fallback,
            'body_html': fallback_html,
            'body_text': fallback_text,
            'authority': authority,
            'source':    'template',
        }


def _fallback_letter(citizen, area, severity, desc, landmark, tag, authority, today, issue_id, lat, lng):
    location = area + (f', near {landmark}' if landmark else '')
    coords = f'\nCoordinates: {lat}, {lng}' if lat and lng else ''
    return f"""Date: {today}

To,
The Concerned Officer,
{authority['name']},
New Delhi.

Subject: Civic Complaint regarding {tag} issue in {area} (AreaPulse Ref #AP-{issue_id})

Respected Sir/Madam,

I am writing to formally bring to your attention a {severity.lower()}-severity civic issue affecting residents of {location}. The issue has been documented via the AreaPulse civic platform (Reference: #AP-{issue_id}, filed on {today}) and warrants prompt action from your office.

Issue description: {desc}{coords}

This problem is causing significant inconvenience and, in cases of high severity, poses a safety risk to citizens passing through the area. As the authority responsible for resolving such matters, I respectfully request your office to:

1. Inspect the location at the earliest opportunity.
2. Initiate corrective action within a reasonable timeline.
3. Update the citizen on action taken via the contact provided.

I trust that your office will treat this complaint with due seriousness and respond promptly. The citizens of Delhi rely on the timely action of departments like yours to maintain the quality of urban life.

Thank you for your attention to this matter.

Yours sincerely,
{citizen}
Filed via AreaPulse · Civic Issue Map · Delhi
Reference: #AP-{issue_id}"""


def _text_to_html(text):
    """Plain text → simple HTML email body."""
    if not text:
        return ''
    escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    paragraphs = [p.strip() for p in escaped.split('\n\n') if p.strip()]
    body = '\n'.join(f'<p style="margin:0 0 14px;line-height:1.6">{p.replace(chr(10), "<br>")}</p>' for p in paragraphs)
    return f"""<div style="font-family:Georgia, 'Times New Roman', serif; font-size:14px; color:#1a1a1a; max-width:640px; margin:0 auto; padding:24px;">
{body}
<hr style="margin:20px 0; border:none; border-top:1px solid #ddd">
<p style="font-size:11px; color:#888; margin:0">Filed via <b>AreaPulse</b> — Delhi Civic Issue Platform · Real-time city map of citizen-reported issues.</p>
</div>"""


# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════
def _extract_json(text):
    """Robust JSON extraction — handles markdown fences, prose wrapping."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    cleaned = text.replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None

# ═══════════════════════════════════════════════════════
#  AR SCANNER — RICH FORMAT
# ═══════════════════════════════════════════════════════
_AR_PROMPT = """You are AreaPulse AR vision AI for Delhi civic issues. Analyze this photo.
Return ONLY valid JSON, no markdown:
{
  "issues": [
    {
      "issue_type": "pothole|water|garbage|streetlight|traffic|noise|sewage|electricity|tree|other",
      "severity": "low|medium|high",
      "hazard_level": "low|medium|high",
      "confidence": <70-98>,
      "title": "<short 3-5 word title>",
      "description": "<one sentence what you see>",
      "recommended_authority": "<authority name e.g. PWD Delhi, MCD, DJB>",
      "estimated_repair_time": "<e.g. 1-3 days>",
      "ar_label": "<UPPERCASE 1-2 word label>",
      "area_estimate": "Delhi",
      "x_hint": <30-70>,
      "y_hint": <35-65>
    }
  ],
  "primary_index": 0
}
List ALL visible issues (1-3). x_hint/y_hint = percentage of image width/height where issue appears."""


def analyze_image_ar(image_b64, mime='image/jpeg'):
    """AR Scanner vision — rich format with issues array, authority, repair time, AR hints."""
    if not _client:
        return {'error': 'AI not configured. Set GROQ_API_KEY in .env.'}
    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{image_b64}'}},
                {'type': 'text', 'text': _AR_PROMPT},
            ]}],
            max_tokens=600, temperature=0.2,
        )
        raw = (resp.choices[0].message.content or '').strip()
        parsed = _extract_json(raw)
        if not parsed:
            return {'error': 'AI returned unparseable response', 'raw': raw[:200]}
        return parsed
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}'}


# ═══════════════════════════════════════════════════════
#  SPAM CLASSIFICATION (Feature 1)
# ═══════════════════════════════════════════════════════
_SPAM_PROMPT = """You are a spam filter for a civic issue reporting platform in India (potholes, water, garbage, sewage, electricity, etc.).

Classify the following citizen report into ONE of these categories:
- REAL: legitimate civic infrastructure issue, even if briefly described
- SPAM: gibberish, advertising, alien/joke/fantasy content (e.g. "alien invasion", "dragons in park"), unrelated promotional text
- ABUSE: profanity, hate speech, personal attacks, targeted harassment
- TEST: clearly a test submission ("test", "testing 123", "abc def")

Be generous toward REAL: low-literacy or short reports about real issues should be REAL.
Only flag SPAM if content is clearly fantastical or commercial.

Return ONLY valid JSON, no other text:
{"verdict": "REAL"|"SPAM"|"ABUSE"|"TEST", "confidence": 0-100, "reason": "short explanation under 12 words"}

REPORT TEXT:
"""

# Hard-coded keyword fallback when Groq unavailable
_OBVIOUS_SPAM_KEYWORDS = [
    'alien', 'aliens', 'invasion', 'ufo', 'martian', 'zombie', 'vampire',
    'dragon', 'unicorn', 'ghost haunt', 'haunted', 'demon', 'witch',
    'wormhole', 'time travel',
    'buy now', 'click here', 'free money', 'lottery', 'win prize',
    'lorem ipsum', 'asdf', 'qwerty',
]
_OBVIOUS_TEST_KEYWORDS = ['test test', 'testing 123', 'abc def', 'just testing', 'ignore this']
_OBVIOUS_ABUSE_KEYWORDS = []  # left configurable; do not hardcode profanity lists

def classify_spam(description, has_photo=False):
    """
    Returns dict: {'verdict': 'real'|'spam'|'abuse'|'test', 'confidence': int, 'reason': str}
    Always returns a verdict — falls back to keyword check if Groq unavailable.
    Never raises.
    """
    text = (description or '').strip().lower()

    # Hard fallbacks first (instant)
    for kw in _OBVIOUS_SPAM_KEYWORDS:
        if kw in text:
            return {'verdict': 'spam', 'confidence': 95, 'reason': f'contains "{kw}"'}
    for kw in _OBVIOUS_TEST_KEYWORDS:
        if kw in text:
            return {'verdict': 'test', 'confidence': 92, 'reason': 'test-pattern submission'}
    if len(text) < 6:
        return {'verdict': 'test', 'confidence': 60, 'reason': 'too short to be meaningful'}

    # Groq-powered classification
    if not _client:
        return {'verdict': 'real', 'confidence': 50, 'reason': 'no AI; defaulted to real'}

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[{'role': 'user', 'content': _SPAM_PROMPT + description.strip()[:600]}],
            max_tokens=80,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()
        data = _extract_json(raw) or {}
        verdict = (data.get('verdict') or 'REAL').lower().strip()
        if verdict not in ('real', 'spam', 'abuse', 'test'):
            verdict = 'real'
        return {
            'verdict':    verdict,
            'confidence': int(data.get('confidence') or 70),
            'reason':     (data.get('reason') or 'classified by groq')[:80],
        }
    except Exception as e:
        return {'verdict': 'real', 'confidence': 40, 'reason': f'classify error: {str(e)[:40]}'}
