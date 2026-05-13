import re


def normalize_phone(phone: str) -> str:
    if not phone:
        return phone

    p = phone.strip()

    if p.lower().startswith("whatsapp:"):
        p = p[9:]

    if p.startswith("+"):
        p = p[1:]

    digits = re.sub(r"\D", "", p)

    if digits.startswith("55") and len(digits) >= 12:
        return "+" + digits

    return "+55" + digits


def normalize_phone_for_whatsapp(phone: str) -> str:
    return "whatsapp:" + normalize_phone(phone)