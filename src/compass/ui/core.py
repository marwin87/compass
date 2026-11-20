"""JavaScript shared by the notes page and the Settings page, and the server-side embedding of
the language strings and the settings into a page.

`CORE_JS` holds the generic helpers (`tr`, `$`, `h`, icons, `toast`, `api`, the category error
table, `saveSettings`). It is inserted where a page has the `/*CORE*/` marker and, like the reader
code, contains only DOM calls (never HTML strings) and makes no external request.
"""

import json
from collections.abc import Mapping

from compass import ai
from compass import settings as store
from compass.ui import asset
from compass.ui.i18n import STRINGS

CORE_JS = asset("core.js")


def inject(page: str, lang: str, settings: Mapping[str, object] | None = None) -> str:
    """Fill the I18N and SETTINGS constants and the theme of an already `fill`ed page."""
    values = dict(store.defaults() if settings is None else settings)
    callouts = {  # both languages: a translation preview names its callouts in the language it is in
        code: {
            k: v
            for k, v in table.items()
            if k.startswith("callout_") or k == "toc_title"
        }
        for code, table in STRINGS.items()
    }
    payload = json.dumps(
        {"lang": lang, "strings": STRINGS[lang], "callouts": callouts},
        ensure_ascii=False,
    )
    blob = json.dumps(values, ensure_ascii=False)
    state = ai.status({**store.defaults(), **values})
    ready = bool(
        state["enabled"] and state["configured"]
    )  # the one rule for every AI component
    script = (
        "const I18N = "
        + payload.replace("</", "<\\/")
        + ";\nconst SETTINGS = "
        + blob.replace("</", "<\\/")
        + ";\nconst AI_READY = "
        + ("true" if ready else "false")
        + ";"
    )
    theme = values.get("theme")
    theme = (
        theme if theme in ("dark", "light") else "dark"
    )  # never put anything else in an attribute
    return page.replace("/*I18N*/", script).replace(
        'data-theme="dark"', f'data-theme="{theme}"', 1
    )
