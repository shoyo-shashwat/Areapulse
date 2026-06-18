"""services/notification_service.py — WhatsApp dispatch via Twilio."""
from config.settings import TWILIO_SID, TWILIO_TOKEN, TWILIO_WA_NUM


def send_whatsapp(phone: str, message: str) -> dict:
    if not phone:
        return {'ok': False, 'mode': 'skipped', 'detail': 'No phone number'}
    if not TWILIO_SID or not TWILIO_TOKEN:
        print(f'[wa] SIMULATED → {phone}: {message}')
        return {'ok': True, 'mode': 'simulated'}
    try:
        from twilio.rest import Client
        msg = Client(TWILIO_SID, TWILIO_TOKEN).messages.create(
            body=message, from_=TWILIO_WA_NUM, to=f'whatsapp:{phone}')
        return {'ok': True, 'mode': 'sent', 'detail': msg.sid}
    except Exception as e:
        return {'ok': False, 'mode': 'error', 'detail': str(e)}
