"""Server-side settings: a small registry of known keys stored as JSON in the `settings` table.

Adding a setting means adding a key to `SPEC` (default + validator), an i18n label and a test.
A value that is missing (or damaged in the table) reads as its default. An update is validated as
a whole before anything is written, so a bad key changes nothing.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass

from compass import notes
from compass.db import connect


class SettingError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


@dataclass(frozen=True)
class Setting:
    default: object
    valid: Callable[[object], bool]


def _choice(*options: str) -> Callable[[object], bool]:
    return lambda v: isinstance(v, str) and v in options


def _int_between(low: int, high: int) -> Callable[[object], bool]:
    return lambda v: isinstance(v, int) and not isinstance(v, bool) and low <= v <= high


def _bool(v: object) -> bool:
    return isinstance(v, bool)


def _str(maxlen: int) -> Callable[[object], bool]:
    return lambda v: isinstance(v, str) and len(v) <= maxlen


SPEC: dict[str, Setting] = {
    "theme": Setting("dark", _choice("dark", "light")),
    "reader_size": Setting(17, _int_between(15, 22)),  # px, reading mode text size
    "reader_width": Setting(1, _int_between(0, 2)),  # 0 narrow, 1 medium, 2 wide
    "sort": Setting(
        "", _choice("", *notes.SORTS)
    ),  # the list order; "" = relevance / newest
    # AI (the key is never a setting: it lives in the OPENROUTER_API_KEY env var only)
    "ai_enabled": Setting(False, _bool),
    "ai_block_page": Setting(
        False, _bool
    ),  # blur and block the page while an AI job runs (Appearance)
    "ai_connection": Setting("openrouter", _choice("openrouter", "local")),
    "ai_address": Setting("", _str(200)),  # used by the local connection only
    "ai_model_openrouter": Setting(
        "", _str(200)
    ),  # each connection keeps its own model
    "ai_model_local": Setting("", _str(200)),
}


def defaults() -> dict[str, object]:
    return {key: spec.default for key, spec in SPEC.items()}


def current() -> dict[str, object]:
    """Every known setting with its effective value."""
    conn = connect()
    try:
        rows = dict(conn.execute("SELECT key, value FROM settings").fetchall())
    finally:
        conn.close()
    result = defaults()
    for key, spec in SPEC.items():
        if key in rows:
            try:
                value = json.loads(rows[key])
            except ValueError:
                continue
            if spec.valid(value):
                result[key] = value
    return result


def update(patch: dict[str, object]) -> dict[str, object]:
    """Validate the whole patch, then write it in one transaction; returns the new settings."""
    for key, value in patch.items():
        spec = SPEC.get(key)
        if spec is None or not spec.valid(value):
            raise SettingError(key)
    if patch:
        conn = connect()
        try:
            with conn:
                for key, value in patch.items():
                    conn.execute(
                        "INSERT INTO settings(key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, json.dumps(value)),
                    )
        finally:
            conn.close()
    return current()
