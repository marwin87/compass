import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set (see .env.example)")
    return value


def password() -> str:
    return _required("COMPASS_PASSWORD")


def secret_key() -> str:
    return _required("COMPASS_SECRET_KEY")


def ai_key() -> str:
    """Optional: the OpenRouter key (a local server usually needs none)."""
    return os.environ.get("OPENROUTER_API_KEY", "")
