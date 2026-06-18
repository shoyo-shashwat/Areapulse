"""config/settings.py — all env vars in one place. Import from here, never os.environ directly."""
import os

SECRET_KEY     = os.environ.get('SECRET_KEY', 'areapulse-portal-dev-2026')
MAPTILER_KEY   = os.environ.get('MAPTILER_KEY', '')
DATABASE_URL   = os.environ.get('DATABASE_URL', '')
GROQ_API_KEY   = os.environ.get('GROQ_API_KEY', '')
TWILIO_SID     = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN   = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WA_NUM  = os.environ.get('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
CIVICALERT_URL = os.environ.get('CIVICALERT_URL', 'http://localhost:5050')

SLA_HOURS = {
    'sewage': 24, 'electricity': 24, 'traffic': 24, 'noise': 24,
    'water': 48,  'streetlight': 48, 'garbage': 72, 'other': 120,
    'pothole': 168, 'tree': 168,
}
CROWD_ESCALATION_THRESHOLD = 25
