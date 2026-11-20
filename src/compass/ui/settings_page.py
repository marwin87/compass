"""The Settings page (served at `/settings`): appearance, data, keyboard shortcuts, about.

Same rules as the notes page (see docs/STYLE_GUIDE.md): DOM calls only, no external requests, every
string in both languages. Each control applies at once and is saved through `saveSettings`
(core.py); when a save fails the control goes back to its previous value. Adding a setting means a
key in `settings.SPEC`, a control here, an i18n label and a test.
"""

from collections.abc import Mapping

from compass.ui import asset, core
from compass.ui.page import COMMON_CSS, FAVICON_LINK, fill

SETTINGS_CSS = asset("settings.css")
SETTINGS_JS = asset("settings.js")

AI_TAG = ' <span class="aitag"><span class="ic" data-icon="spark" data-size="10"></span>AI</span>'

_SECTIONS = (
    ("appearance", "settings_nav_appearance", "sun"),
    ("categories", "categories_h", "layers"),
    ("tags", "settings_nav_tags", "tag"),
    ("load", "load_h", "upload"),
    ("shortcuts", "settings_nav_shortcuts", "zap"),
    ("ai", "ai_h", "spark"),
    ("backup", "data_backup_h", "database"),
    ("danger", "data_danger_h", "alert"),
    ("about", "settings_nav_about", "info"),
)

_NAV = "".join(
    f'      <a href="#{sid}" data-sec="{sid}"{" data-ai hidden" if sid == "load" else ""}><span class="ic" data-icon="{ic}" data-size="16"></span>[[{key}]]{AI_TAG if sid == "load" else ""}</a>\n'
    for sid, key, ic in _SECTIONS
)

SETTINGS_HTML = (
    asset("settings.html")
    .replace("<!--FAVICON-->", FAVICON_LINK)
    .replace("/*CSS*/", COMMON_CSS + SETTINGS_CSS)
    .replace("<!--NAV-->", _NAV)
    .replace("/*CORE*/", core.CORE_JS)
    .replace("/*SETTINGS_JS*/", SETTINGS_JS)
)


def render_settings(lang: str, settings: Mapping[str, object] | None = None) -> str:
    return core.inject(fill(SETTINGS_HTML, lang), lang, settings)
