import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set (see .env.example)")
    return value


MIN_SECRET_LEN = 32
PLACEHOLDERS = {"change-me", "change-me-too"}  # the values of .env.example


def password() -> str:
    value = _required("COMPASS_PASSWORD")
    if value in PLACEHOLDERS:
        raise RuntimeError("COMPASS_PASSWORD is still the .env.example placeholder")
    return value


def secret_key() -> str:
    value = _required("COMPASS_SECRET_KEY")
    if value in PLACEHOLDERS or len(value) < MIN_SECRET_LEN:
        raise RuntimeError(
            f"COMPASS_SECRET_KEY must be at least {MIN_SECRET_LEN} characters and not the "
            'placeholder (python3 -c "import secrets; print(secrets.token_hex(32))")'
        )
    return value


def ai_key() -> str:
    """Optional: the OpenRouter key (a local server usually needs none)."""
    return os.environ.get("OPENROUTER_API_KEY", "")
