"""UI strings in Polish and English, and the choice of language for a request.

The language comes from the `lang` cookie (set by the PL/EN buttons) and otherwise from the
browser's Accept-Language header; anything else falls back to Polish. Note text, tags and the
machine-readable API messages are not translated.
"""

from typing import Any

LANGS = ("pl", "en")
DEFAULT_LANG = "pl"
COOKIE = "lang"

STRINGS: dict[str, dict[str, Any]] = {
    "pl": {
        # static page text
        "tagline": "Twoja baza wiedzy",
        "new_note": "＋ Nowa notatka",
        "tags_h": "Tagi",
        "how_h": "Jak szukam",
        "legend1": "dokładny tag, potem tytuł, potem treść",
        "legend2": "kilka słów: więcej trafień wyżej",
        "legend3": "literówki i brak polskich liter są wybaczane",
        "theme_title": "Jasny / ciemny",
        "lang_label": "Język",
        "logout": "Wyloguj",
        "search_ph": "Szukaj… np. indeks, zlozonosc, sql",
        "hint_select": "wybór",
        "hint_new": "nowa",
        "hint_clear": "czyść",
        # login page
        "login_title": "Compass - logowanie",
        "login_intro": "Zaloguj się hasłem, żeby zobaczyć swoje notatki.",
        "password_ph": "Hasło",
        "login_btn": "Zaloguj",
        "wrong_pw": "Nieprawidłowe hasło.",
        # results list
        "count": {
            "one": "wynik",
            "few": "wyniki",
            "many": "wyników",
            "other": "wyniku",
        },
        "top50": "pierwsze 50 wyników",
        "no_results": "Brak wyników.",
        "pick_or_add": "Wybierz notatkę z listy albo dodaj nową.",
        # note panel and forms
        "created": "Utworzono",
        "edit": "Edytuj",
        "delete": "Usuń",
        "confirm_delete": "Na pewno usunąć? Tego nie da się cofnąć.",
        "yes_delete": "Tak, usuń",
        "back": "Wróć",
        "save": "Zapisz",
        "cancel": "Anuluj",
        "confirm_save": "Na pewno nadpisać? Poprzednia wersja przepadnie.",
        "yes_overwrite": "Tak, nadpisz",
        "label_title": "Tytuł",
        "label_body": "Treść",
        "label_tags": "Tagi (po przecinku)",
        "new_note_h": "Nowa notatka",
        # messages
        "empty_title": "Podaj tytuł (1–200 znaków).",
        "tag_long": "Tag może mieć najwyżej {n} znaków.",
        "tag_many": "Najwyżej {n} tagów na notatkę.",
        "save_error": "Nie udało się zapisać (tytuł 1–200 znaków, tagi do 30 znaków).",
        "delete_failed": "Nie udało się usunąć.",
        "toast_created": "Notatka zapisana",
        "toast_saved": "Zapisano zmiany",
        "toast_deleted": "Notatka usunięta",
    },
    "en": {
        "tagline": "Your knowledge base",
        "new_note": "＋ New note",
        "tags_h": "Tags",
        "how_h": "How search works",
        "legend1": "exact tag first, then title, then body",
        "legend2": "several words: more matches rank higher",
        "legend3": "typos and missing accents (e.g. Polish letters) are forgiven",
        "theme_title": "Light / dark",
        "lang_label": "Language",
        "logout": "Log out",
        "search_ph": "Search… e.g. index, complexity, sql",
        "hint_select": "select",
        "hint_new": "new",
        "hint_clear": "clear",
        "login_title": "Compass - log in",
        "login_intro": "Log in with your password to see your notes.",
        "password_ph": "Password",
        "login_btn": "Log in",
        "wrong_pw": "Wrong password.",
        "count": {"one": "result", "other": "results"},
        "top50": "first 50 results",
        "no_results": "No results.",
        "pick_or_add": "Pick a note from the list or add a new one.",
        "created": "Created",
        "edit": "Edit",
        "delete": "Delete",
        "confirm_delete": "Delete this note? This cannot be undone.",
        "yes_delete": "Yes, delete",
        "back": "Back",
        "save": "Save",
        "cancel": "Cancel",
        "confirm_save": "Overwrite the note? The previous version will be lost.",
        "yes_overwrite": "Yes, overwrite",
        "label_title": "Title",
        "label_body": "Body",
        "label_tags": "Tags (comma-separated)",
        "new_note_h": "New note",
        "empty_title": "Enter a title (1–200 characters).",
        "tag_long": "A tag can have at most {n} characters.",
        "tag_many": "At most {n} tags per note.",
        "save_error": "Could not save (title 1–200 characters, tags up to 30 characters).",
        "delete_failed": "Could not delete.",
        "toast_created": "Note saved",
        "toast_saved": "Changes saved",
        "toast_deleted": "Note deleted",
    },
}


def pick_lang(cookie: str | None, accept_language: str | None) -> str:
    """The `lang` cookie wins, then the best-weighted supported language in the header."""
    if cookie in LANGS:
        return str(cookie)
    best, best_q = DEFAULT_LANG, -1.0
    for part in (accept_language or "").split(","):
        tag, _, params = part.strip().partition(";")
        code = tag.strip().lower().split("-")[0]
        q = 1.0
        if params.strip().startswith("q="):
            try:
                q = float(params.strip()[2:])
            except ValueError:
                continue
        if code in LANGS and q > best_q:
            best, best_q = code, q
    return best
