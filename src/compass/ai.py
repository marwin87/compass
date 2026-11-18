"""AI: the static connection check (`status`) and the model calls (OpenAI-compatible, stdlib only).

Neither the key nor note content is ever logged or returned.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlparse

from compass import config

LOOPBACK = {"localhost", "127.0.0.1", "::1"}
OPENROUTER_URL = "https://openrouter.ai/api/v1"
TIMEOUT = 60  # seconds; a slow model must not hang a request forever

LANGUAGES = {"en": "English", "pl": "Polish"}
SUMMARY_TIMEOUT = (
    120  # a summary of a long note is a longer answer than a translation of a short one
)
SUMMARY = (
    "Summarize the note you receive (Markdown, with its title first). Reply in Markdown, in the "
    "language of the note, in exactly two parts, each under a level-2 heading named in that language "
    "(for example 'Summary' and 'Key points'): first a short summary of 2 to 4 sentences, then a "
    "bulleted list of 3 to 7 key points, each a complete short statement. Keep names, numbers, code "
    "identifiers and links exactly as they are. Do not add anything that is not in the note and do not "
    "wrap the answer in a code fence."
)


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


def embed_model(s: dict[str, object]) -> str:
    """The embedding model of the chosen connection; empty = no embeddings (chat falls back to keyword search)."""
    return str(s[f"ai_embed_model_{s['ai_connection']}"]).strip()


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
        "embeddings": bool(embed_model(s)),
    }


def base_url(s: dict[str, object]) -> str:
    if s["ai_connection"] != "local":
        return OPENROUTER_URL
    address = str(s["ai_address"]).strip().rstrip("/")
    return address if "//" in address else f"http://{address}"


Messages = list[
    dict[str, str]
]  # [{"role": "system" | "user" | "assistant", "content": ...}]


def _post(
    s: dict[str, object], path: str, payload: dict[str, object]
) -> urllib.request.Request:
    headers = {"Content-Type": "application/json"}
    if key := config.ai_key():
        headers["Authorization"] = f"Bearer {key}"
    return urllib.request.Request(
        base_url(s) + path, json.dumps(payload).encode(), headers
    )


def _request(
    s: dict[str, object], messages: Messages, stream: bool = False
) -> urllib.request.Request:
    payload: dict[str, object] = {"model": model(s), "messages": messages}
    if stream:
        payload["stream"] = True
    return _post(s, "/chat/completions", payload)


def _one(system: str, user: str) -> Messages:
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


@contextmanager
def _mapped() -> Iterator[None]:
    """Turn what a provider call can raise into an AIError that says why."""
    try:
        yield
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


def _chat(
    s: dict[str, object], system: str, user: str, timeout: int | None = None
) -> str:
    with (
        _mapped(),
        urllib.request.urlopen(
            _request(s, _one(system, user)), timeout=timeout or TIMEOUT
        ) as response,
    ):
        answer = json.load(response)["choices"][0]["message"]["content"]
    if not isinstance(answer, str):
        raise AIError("failed", "unexpected reply from the provider")
    return answer.strip()


def stream(
    s: dict[str, object], system: str, user: str, timeout: int | None = None
) -> Iterator[str]:
    """`stream_messages` for one system and one user message."""
    return stream_messages(s, _one(system, user), timeout)


def stream_messages(
    s: dict[str, object], messages: Messages, timeout: int | None = None
) -> Iterator[str]:
    """The answer in pieces, as the model writes it (server-sent events). `timeout` is the longest
    silence, not the length of the whole answer. A server that ignores `stream` and sends one JSON
    answer still works: it arrives as a single piece. Raises AIError; makes no call when AI is off or
    unconfigured. Closing the generator closes the connection."""
    ready(s)
    other: list[str] = []  # lines that are not events: a plain (non-streamed) answer
    got = False
    with (
        _mapped(),
        urllib.request.urlopen(
            _request(s, messages, True), timeout=timeout or TIMEOUT
        ) as response,
    ):
        for raw in response:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                other.append(line)  # also ": keep-alive" comments, harmless
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            piece = json.loads(data)["choices"][0]["delta"].get("content")
            if isinstance(piece, str) and piece:
                got = True
                yield piece
        if not got and other:
            answer = json.loads("".join(other))["choices"][0]["message"]["content"]
            if isinstance(answer, str) and answer:
                yield answer


def embed(s: dict[str, object], texts: list[str]) -> list[list[float]]:
    """One vector per text, in order, from the embedding model of the chosen connection (OpenAI-compatible
    `/embeddings`). Raises AIError; makes no call when AI is off, unconfigured, or no embedding model is set."""
    ready(s)
    name = embed_model(s)
    if not name:
        raise AIError("not_configured", "embedding model")
    if not texts:
        return []
    with (
        _mapped(),
        urllib.request.urlopen(
            _post(s, "/embeddings", {"model": name, "input": texts}), timeout=TIMEOUT
        ) as response,
    ):
        rows = sorted(json.load(response)["data"], key=lambda r: r["index"])
        vectors = [[float(x) for x in r["embedding"]] for r in rows]
    if len(vectors) != len(texts) or not all(vectors):
        raise AIError("failed", "unexpected reply from the provider")
    return vectors


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


def summarize(title: str, body: str, s: dict[str, object]) -> str:
    """A summary and the key points of a note. Raises AIError; makes no call when AI is off or
    unconfigured, or when the note has no text."""
    ready(s)
    if not body.strip():
        return ""
    return _chat(s, SUMMARY, f"# {title}\n\n{body}", SUMMARY_TIMEOUT)


def translate(text: str, s: dict[str, object], to: str) -> str:
    """Translate a note body into `to` ("en" or "pl"). Raises AIError; makes no call when AI is off or
    unconfigured."""
    ready(s)
    if not text.strip():
        return ""
    return _chat(s, translate_prompt(to), text)
