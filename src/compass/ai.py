"""AI: the static connection check (`status`) and the model calls (OpenAI-compatible, stdlib only).

Neither the key nor note content is ever logged or returned.
"""

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

from compass import config

LOOPBACK = {"localhost", "127.0.0.1", "::1"}
OPENROUTER_URL = "https://openrouter.ai/api/v1"
TIMEOUT = 60  # seconds; a slow model must not hang a request forever

LANGUAGES = {"en": "English", "pl": "Polish"}


def translate_prompt(to: str) -> str:
    source = LANGUAGES["pl" if to == "en" else "en"]
    return (
        f"Translate the Markdown note you receive from {source} into {LANGUAGES[to]}. "
        "Keep the Markdown structure exactly (headings, lists, tables, links). Do not translate code blocks, "
        "inline code or URLs. Reply with the translated note and nothing else."
    )


class AIError(Exception):
    """code: not_enabled | not_configured | timeout | failed. `detail` says why in a few words
    (an HTTP status and the provider's message, a refused connection...); it never holds the key or
    note content."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _http_detail(problem: urllib.error.HTTPError) -> str:
    text = f"HTTP {problem.code}"
    try:
        message = json.loads(problem.read(4000))["error"]["message"]
        if isinstance(message, str) and message.strip():
            text += f": {message.strip()[:200]}"
    except (OSError, ValueError, LookupError, TypeError):
        pass
    return text


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


def _chat(
    s: dict[str, object], system: str, user: str, timeout: int | None = None
) -> str:
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
        with urllib.request.urlopen(request, timeout=timeout or TIMEOUT) as response:
            answer = json.load(response)["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as problem:  # before URLError, its parent
        raise AIError("failed", _http_detail(problem)) from None
    except TimeoutError:
        raise AIError("timeout") from None
    except urllib.error.URLError as problem:
        if isinstance(problem.reason, TimeoutError):
            raise AIError("timeout") from None
        raise AIError("failed", str(problem.reason)[:200]) from None
    except (OSError, ValueError, LookupError, TypeError):
        raise AIError("failed", "unexpected reply from the provider") from None
    if not isinstance(answer, str):
        raise AIError("failed", "unexpected reply from the provider")
    return answer.strip()


def ready(s: dict[str, object]) -> None:
    """Raise AIError unless AI is on and its connection is configured (no call is made)."""
    state = status(s)
    if not state["enabled"]:
        raise AIError("not_enabled")
    if not state["configured"]:
        raise AIError("not_configured")


def ask(
    s: dict[str, object], system: str, user: str, timeout: int | None = None
) -> str:
    """One model call for any feature. Raises AIError; makes no call when AI is off or unconfigured."""
    ready(s)
    return _chat(s, system, user, timeout)


def translate(text: str, s: dict[str, object], to: str) -> str:
    """Translate a note body into `to` ("en" or "pl"). Raises AIError; makes no call when AI is off or
    unconfigured."""
    ready(s)
    if not text.strip():
        return ""
    return _chat(s, translate_prompt(to), text)
