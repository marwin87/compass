"""AI: the static connection check (`status`) and the model calls (OpenAI-compatible, stdlib only).

Neither the key nor note content is ever logged or returned.
"""

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from compass import config

LOOPBACK = {"localhost", "127.0.0.1", "::1"}
OPENROUTER_URL = "https://openrouter.ai/api/v1"
TIMEOUT = 60  # seconds; a slow model must not hang a request forever

TRANSLATE_PROMPT = (
    "Translate the Markdown note you receive: into English if it is mostly Polish, otherwise into Polish. "
    "Keep the Markdown structure exactly (headings, lists, tables, links). Do not translate code blocks, "
    "inline code or URLs. Start the reply with one line holding only [en] or [pl], the language you translated "
    "into, then the translated note and nothing else."
)


class AIError(Exception):
    """code: not_enabled | not_configured | timeout | failed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def model(s: dict[str, object]) -> str:
    """The model of the chosen connection (each connection has its own)."""
    return str(s[f"ai_model_{s['ai_connection']}"]).strip()


def status(s: dict[str, object]) -> dict[str, object]:
    """Whether the chosen connection is configured, what is missing, and whether notes leave the machine."""
    local = s["ai_connection"] == "local"
    address = str(s["ai_address"]).strip()
    missing: list[str] = []
    if local and not address:
        missing.append("address")
    if not local and not config.ai_key():
        missing.append("key")
    if not model(s):
        missing.append("model")
    host = urlparse(address if "//" in address else f"//{address}").hostname or ""
    return {
        "enabled": s["ai_enabled"],
        "connection": s["ai_connection"],
        "configured": not missing,
        "missing": missing,
        "leaves_machine": not local or host not in LOOPBACK,
    }


def base_url(s: dict[str, object]) -> str:
    if s["ai_connection"] != "local":
        return OPENROUTER_URL
    address = str(s["ai_address"]).strip().rstrip("/")
    return address if "//" in address else f"http://{address}"


def _chat(s: dict[str, object], system: str, user: str) -> str:
    payload = {
        "model": model(s),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json"}
    if key := config.ai_key():
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        base_url(s) + "/chat/completions",
        json.dumps(payload).encode(),
        headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            answer = json.load(response)["choices"][0]["message"]["content"]
    except TimeoutError:
        raise AIError("timeout") from None
    except urllib.error.URLError as problem:
        raise AIError(
            "timeout" if isinstance(problem.reason, TimeoutError) else "failed"
        ) from None
    except (OSError, ValueError, LookupError, TypeError):
        raise AIError("failed") from None
    if not isinstance(answer, str):
        raise AIError("failed")
    return answer.strip()


LANG_LINE = re.compile(r"^\s*\[(en|pl)\]\s*", re.IGNORECASE)


def translate(text: str, s: dict[str, object]) -> tuple[str, str]:
    """Translate a note body PL<->EN: (language it was translated into, text); the language is "" when
    the model did not say. Raises AIError; makes no call when AI is off or unconfigured."""
    state = status(s)
    if not state["enabled"]:
        raise AIError("not_enabled")
    if not state["configured"]:
        raise AIError("not_configured")
    if not text.strip():
        return "", ""
    answer = _chat(s, TRANSLATE_PROMPT, text)
    found = LANG_LINE.match(answer)
    return (found.group(1).lower(), answer[found.end() :]) if found else ("", answer)
