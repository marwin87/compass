import json
from pathlib import Path

from fastapi.testclient import TestClient

from compass.notes.transfer import parse_export

DEMO = Path(__file__).resolve().parent.parent / "demo" / "compass-demo.json"


def test_the_demo_file_is_a_valid_export() -> None:
    document = json.loads(DEMO.read_text(encoding="utf-8"))
    parsed = parse_export(document)  # the same checks the import runs
    assert len(parsed.notes) == document["count"] >= 15


def test_the_demo_file_imports_and_searches_well(authed: TestClient) -> None:
    body = DEMO.read_text(encoding="utf-8")
    first = authed.post(
        "/api/import", content=body, headers={"content-type": "application/json"}
    )
    assert first.status_code == 200
    count = first.json()["imported"]
    again = authed.post(
        "/api/import", content=body, headers={"content-type": "application/json"}
    )
    assert again.json() == {
        "imported": count
    }  # safe to repeat: same state, no duplicates
    assert authed.get("/api/export").json()["count"] == count

    def titles(q: str) -> list[str]:
        return [n["title"] for n in authed.get("/api/notes", params={"q": q}).json()]

    assert titles("zlozonosc")[0].startswith("Złożoność")
    assert titles("indkes")[0] == "Indeks w bazie danych"
    assert (
        titles("sql")[0] != "Szybkie notatki o SQL"
    )  # notes tagged sql come before a title-only hit


def test_the_demo_fills_several_categories_and_has_no_version() -> None:
    document = json.loads(DEMO.read_text(encoding="utf-8"))
    assert "version" not in document
    names = {n["category"] for n in document["notes"]}
    assert (
        None not in names and len(names) >= 5
    )  # every demo note is in a real category
