"""Normalize owner-entered phone allowlists without reinterpreting platform IDs."""
import re
import unicodedata


def normalize_phone_allowlist(value, default_country="international"):
    if default_country not in {"IN", "international"}:
        raise ValueError("Choose India or international phone numbering.")
    raw = str(value or "").strip()
    if len(raw) > 2048:
        raise ValueError("Phone allowlist is too long.")
    entries = raw.split(",") if raw else []
    if len(entries) > 32:
        raise ValueError("Use at most 32 phone numbers.")
    normalized = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        # Explicit existing platform IDs are not national phone numbers.
        if entry == "*" or re.fullmatch(r"[0-9]+(?::[0-9]+)?@(s\.whatsapp\.net|lid)", entry):
            number = entry
        else:
            entry = "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in entry)
            number = re.sub(r"[\s()\-]", "", entry)
            international = number.startswith("+") or number.startswith("00")
            if number.startswith("+"):
                number = number[1:]
            elif number.startswith("00"):
                number = number[2:]
            if default_country == "IN" and not international:
                if re.fullmatch(r"0?[6-9][0-9]{9}", number):
                    number = "91" + number.lstrip("0")
            if not re.fullmatch(r"[1-9][0-9]{7,14}", number):
                raise ValueError("Use a valid number with country code, or an Indian 10-digit mobile number.")
            if default_country == "IN" and len(number) == 10 and not international:
                raise ValueError("Indian mobile numbers must start with 6, 7, 8 or 9.")
        if number not in normalized:
            normalized.append(number)
    return ",".join(normalized)
