import os, json, time, math, re
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from groq import Groq
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app, origins=["https://areapulse.onrender.com/", "*"])

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

db = None
try:
    key_path = "firebase_key.json"
    if os.path.exists(key_path):
        cred = credentials.Certificate(key_path)
    else:
        key_json = os.environ.get("FIREBASE_KEY_JSON") or os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if key_json:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            tmp.write(key_json); tmp.close()
            cred = credentials.Certificate(tmp.name)
        else:
            raise FileNotFoundError("No Firebase key found")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase connected")
except Exception as e:
    print(f"⚠️  Firebase not configured: {e}")


def _next_int_id(collection_name):
    """Mirror main app's _next_int_id so IDs and counter stay consistent."""
    counter_ref = db.collection('_counters').document(collection_name)
    snap = counter_ref.get()
    if snap.exists:
        n = snap.to_dict().get('n', 0) + 1
    else:
        n = 1
    counter_ref.set({'n': n})
    return n


def haversine(lat1, lng1, lat2, lng2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

DETECT_PROMPT = """You are a civic issue detection AI for AreaPulse — Delhi smart city platform.

CRITICAL INSTRUCTION: A citizen pointed their camera at this scene because they see a civic problem. You MUST identify it. Look very carefully — even subtle issues count: cracked roads, small piles of trash, dim/broken lights, exposed wires, leaking pipes, fallen branches, blocked drains, anything that looks like infrastructure damage or municipal neglect.

ALWAYS return at least 1 issue. Only return an empty array if the image is clearly a face, indoor selfie, or has zero outdoor/street context.

Respond with ONLY valid JSON. No markdown fences. No preamble. No "Here is..." text. Do not include any reasoning or thinking before the JSON:
{
  "issues": [
    {
      "issue_type": "pothole|garbage|water|streetlight|sewage|electricity|traffic|tree|noise|other",
      "severity": "low|medium|high",
      "confidence": <integer 70-98>,
      "title": "<clear English title, max 8 words>",
      "title_hi": "<same title translated to Hindi (Devanagari script), max 8 words>",
      "description": "<English 2-3 sentences>",
      "description_hi": "<same description translated to Hindi (Devanagari script), 2-3 sentences>",
      "ar_label": "<max 3 English words>",
      "recommended_authority": "MCD North|MCD South|DJB|PWD|BSES Yamuna|BSES Rajdhani|Delhi Traffic Police|NDMC",
      "estimated_repair_time": "24-48 hours|3-7 days|1-2 weeks|2-4 weeks",
      "hazard_level": "low|medium|high",
      "area_estimate": "<Delhi locality>",
      "x_hint": <0-100>,
      "y_hint": <0-100>,
      "bbox": [<x1>, <y1>, <x2>, <y2>]
    }
  ],
  "primary_index": 0
}

bbox is a bounding box around the issue in normalized image coords 0-100. x1,y1 = top-left, x2,y2 = bottom-right. Be tight — only the defective region, not the whole road or scene. Example: a single pothole occupying the center-right of the road: [55, 60, 75, 80].

IMPORTANT: title_hi and description_hi must be in Devanagari script (हिंदी). Do not transliterate — actually translate. Example: "Large pothole on main road" → "मुख्य सड़क पर बड़ा गड्ढा".

Up to 4 issues if multiple distinct problems visible. Be aggressive — citizens depend on you to detect problems."""


def extract_json(text):
    if not text:
        return None
    # Strip any leaked reasoning trace before parsing (Qwen3.6 is a hybrid reasoning model)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None


def call_groq_vision(image_b64):
    """Single attempt at calling Groq + parsing JSON. Returns (parsed, raw, finish_reason)."""
    response = groq_client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role":"user","content":[
            {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{image_b64}"}},
            {"type":"text","text":DETECT_PROMPT}
        ]}],
        max_tokens=2000,
        temperature=0.4,
        # NOTE: response_format={"type": "json_object"} was tried and removed —
        # Groq rejected valid-looking generations from this model with
        # json_validate_failed + empty failed_generation. Relying on prompt
        # instructions + extract_json() below instead, which is more reliable
        # for this specific model.
    )
    choice = response.choices[0]
    raw = choice.message.content or ""
    finish_reason = choice.finish_reason
    print(f"[GROQ RAW] finish_reason={finish_reason} len={len(raw)}: {raw[:500]}", flush=True)
    if finish_reason == "length":
        print("[WARN]
