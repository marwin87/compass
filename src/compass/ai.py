"""AI connection status: a static check of what is configured (no model call, no network)."""

from urllib.parse import urlparse

from compass import config

LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def status(s: dict[str, object]) -> dict[str, object]:
    """Whether the chosen connection is configured, what is missing, and whether notes leave the machine."""
    local = s["ai_connection"] == "local"
    address = str(s["ai_address"]).strip()
    missing: list[str] = []
    if local and not address:
        missing.append("address")
    if not local and not config.ai_key():
        missing.append("key")
    if not str(s["ai_model"]).strip():
        missing.append("model")
    host = urlparse(address if "//" in address else f"//{address}").hostname or ""
    return {
        "enabled": s["ai_enabled"],
        "connection": s["ai_connection"],
        "configured": not missing,
        "missing": missing,
        "leaves_machine": not local or host not in LOOPBACK,
    }
