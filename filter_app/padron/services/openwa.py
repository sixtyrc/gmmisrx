"""Envio de WhatsApp via servidor open-wa self-hosted (https://openwa.dacio.com.ar).

Best-effort: nunca debe romper el flujo principal del pipeline. Si el
servidor esta caido, la sesion no esta activa, o faltan credenciales,
simplemente no se envia (se loguea y se sigue).
"""
import requests
from django.conf import settings


def _clean_phone(phone):
    return "".join(c for c in (phone or "") if c.isdigit())


def is_valid_phone(phone):
    digits = _clean_phone(phone)
    return 8 <= len(digits) <= 13


def send_text(phone, text):
    if not settings.OPENWA_KEY or not settings.OPENWA_BASE_URL:
        return False

    clean_phone = _clean_phone(phone)
    if not is_valid_phone(phone):
        print(f"[OpenWA] Numero invalido, no se envia: {phone!r}")
        return False

    chat_id = f"{clean_phone}@c.us"
    url = f"{settings.OPENWA_BASE_URL}/api/sessions/{settings.OPENWA_SESSION_ID}/messages/send-text"

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.OPENWA_KEY}",
                "Content-Type": "application/json",
            },
            json={"chatId": chat_id, "text": text, "mentions": []},
            timeout=30,
        )
        if response.status_code >= 400:
            print(f"[OpenWA] Error {response.status_code} enviando a {chat_id}: {response.text}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[OpenWA] Error de red enviando mensaje a {chat_id}: {e}")
        return False
