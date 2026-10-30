import secrets


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_recovery_code():
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(16))
    return "HEW-" + "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def normalize_recovery_code(code):
    return (code or "").strip().upper()
