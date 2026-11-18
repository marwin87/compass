"""Flow 8: export, import and "clear all data" (Settings -> Backup and Danger zone)."""

import json
import re
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect

from tests.e2e.pages import T, open_settings, seed, unique

DEMO = Path(__file__).parents[2] / "demo" / "compass-demo.json"


def notes_in_db(api: httpx.Client) -> list[str]:
    return sorted(n["title"] for n in api.get("/api/notes").json())


def export_file(title: str, body: str = "tresc") -> dict[str, object]:
    return {
        "format": "compass-export",
        "exported_at": "2026-11-17T18:00:00+00:00",
        "count": 1,
        "categories": ["Z pliku"],
        "notes": [{"id": 1, "title": title, "body": body, "tags": ["importowany"], "category": "Z pliku",
                   "created_at": "2026-11-01T10:00:00+00:00"}],
    }  # fmt: skip


def pick_file(
    page: Page, tmp_path: Path, content: str, name: str = "dane.json"
) -> None:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    page.locator("#importfile").set_input_files(str(path))


def test_export_downloads_a_file_with_everything(app: Page, api: httpx.Client) -> None:
    api.post("/api/categories", json={"name": "Praca"})
    title = unique("Eksport")
    seed(api, {"title": title, "body": "tresc", "tags": ["a", "b"]})
    open_settings(app, "backup")
    with app.expect_download() as download:
        app.get_by_role("link", name=T["export"]).click()
    assert re.fullmatch(r"compass-export-.*\.json", download.value.suggested_filename)
    data = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert data["format"] == "compass-export"
    assert data["count"] == 1
    assert data["notes"][0]["title"] == title
    assert data["notes"][0]["tags"] == ["a", "b"]
    assert "Praca" in data["categories"]
    expect(app.locator("#toast")).to_have_text(T["export_started"])


def test_import_asks_first_and_cancelling_changes_nothing(
    app: Page, api: httpx.Client, tmp_path: Path
) -> None:
    keep = unique("Zostaje")
    seed(api, {"title": keep})
    open_settings(app, "backup")
    pick_file(app, tmp_path, json.dumps(export_file("Z pliku")))
    dialog = app.get_by_role("dialog", name=T["import_confirm_title"])
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text(T["import_ask"])
    expect(dialog).to_contain_text("dane.json")
    dialog.get_by_role("button", name=T["cancel"]).click()
    expect(dialog).to_be_hidden()
    assert notes_in_db(api) == [keep]

    pick_file(app, tmp_path, json.dumps(export_file("Z pliku")))  # and so does Escape
    expect(dialog).to_be_visible()
    app.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    assert notes_in_db(api) == [keep]


def test_confirming_the_import_replaces_everything_and_reports_it(
    app: Page, api: httpx.Client, tmp_path: Path
) -> None:
    api.post("/api/categories", json={"name": "Stara"})
    seed(api, {"title": unique("Stara notatka"), "tags": ["stary"]})
    open_settings(app, "backup")
    pick_file(app, tmp_path, json.dumps(export_file("Z pliku")))
    app.get_by_role("dialog").get_by_role("button", name=T["import_replace"]).click()

    expect(app.locator("#toast")).to_have_text(T["import_done"].format(n=1))
    assert notes_in_db(api) == [
        "Z pliku"
    ]  # the old note is gone: a 1:1 copy of the file
    assert [t["name"] for t in api.get("/api/tags").json()] == ["importowany"]
    names = [c["name"] for c in api.get("/api/categories").json()]
    assert "Z pliku" in names
    assert "Stara" not in names


def test_importing_the_demo_file_brings_its_notes_and_categories(
    app: Page, api: httpx.Client
) -> None:
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    open_settings(app, "backup")
    app.locator("#importfile").set_input_files(str(DEMO))
    app.get_by_role("dialog").get_by_role("button", name=T["import_replace"]).click()
    expect(app.locator("#toast")).to_have_text(T["import_done"].format(n=demo["count"]))
    assert (
        api.get("/api/export").json()["count"] == demo["count"]
    )  # /api/notes lists at most 50
    names = {c["name"] for c in api.get("/api/categories").json()}
    assert set(demo["categories"]) <= names


def test_a_broken_file_shows_the_translated_error_and_keeps_the_data(
    app: Page, api: httpx.Client, tmp_path: Path
) -> None:
    keep = unique("Zostaje")
    seed(api, {"title": keep})
    open_settings(app, "backup")
    for content, message in (
        ("to nie jest json", T["import_err_not_json"]),
        (json.dumps({"hello": "world"}), T["import_err_not_an_export"]),
    ):
        pick_file(app, tmp_path, content)
        app.get_by_role("dialog").get_by_role(
            "button", name=T["import_replace"]
        ).click()
        expect(app.locator("#toast")).to_have_text(message)
        assert notes_in_db(api) == [keep]


def test_clear_all_data_asks_first_and_cancel_keeps_everything(
    app: Page, api: httpx.Client
) -> None:
    keep = unique("Zostaje")
    seed(api, {"title": keep})
    open_settings(app, "danger")
    app.get_by_role("button", name=T["data_clear"]).click()
    dialog = app.get_by_role("dialog", name=T["clear_title"])
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name=T["cancel"]).click()
    expect(dialog).to_be_hidden()
    assert notes_in_db(api) == [keep]


def test_confirming_clear_all_empties_notes_tags_and_categories(
    app: Page, api: httpx.Client
) -> None:
    api.post("/api/categories", json={"name": "Praca"})
    seed(api, {"title": unique("a"), "tags": ["x"]}, {"title": unique("b")})
    open_settings(app, "danger")
    app.get_by_role("button", name=T["data_clear"]).click()
    app.get_by_role("dialog").get_by_role("button", name=T["clear_yes"]).click()
    expect(app.locator("#toast")).to_have_text(T["data_cleared"])
    assert api.get("/api/notes").json() == []
    assert api.get("/api/tags").json() == []
    assert [c["name"] for c in api.get("/api/categories").json()] == [
        ""
    ]  # only the default category is left
    app.goto("/")
    expect(app.get_by_text(T["empty_none"])).to_be_visible()
