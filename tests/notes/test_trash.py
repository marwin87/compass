from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from compass.db import connect
from compass.main import app


def note(
    c: TestClient, title: str, body: str = "", tags: list[str] | None = None
) -> int:
    r = c.post("/api/notes", json={"title": title, "body": body, "tags": tags or []})
    assert r.status_code == 201, r.text
    note_id: int = r.json()["id"]
    return note_id


def titles(c: TestClient, q: str = "") -> list[str]:
    return [n["title"] for n in c.get("/api/notes", params={"q": q}).json()]


def trash(c: TestClient, q: str = "") -> list[dict[str, object]]:
    r = c.get("/api/trash", params={"q": q})
    assert r.status_code == 200
    items: list[dict[str, object]] = r.json()
    return items


def tag_counts(c: TestClient) -> dict[str, int]:
    return {t["name"]: t["count"] for t in c.get("/api/tags").json()}


def age(note_id: int, days: int) -> None:
    """Pretend the note went to the Trash `days` days ago."""
    when = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
    conn = connect()
    try:
        with conn:
            conn.execute(
                "UPDATE notes SET deleted_at = ? WHERE id = ?", (when, note_id)
            )
    finally:
        conn.close()


def test_a_deleted_note_goes_to_the_trash_and_leaves_every_view(
    authed: TestClient,
) -> None:
    gone = note(authed, "Indeks", "drzewo b-tree", ["sql"])
    note(authed, "Transakcje", "izolacja")
    assert authed.delete(f"/api/notes/{gone}").status_code == 204
    assert titles(authed) == ["Transakcje"]
    assert titles(authed, "indeks") == [] and titles(authed, "drzewo") == []
    assert authed.get(f"/api/notes/{gone}").status_code == 404
    assert tag_counts(authed) == {}  # its tag is not counted any more
    (item,) = trash(authed)
    assert item["id"] == gone and item["title"] == "Indeks" and item["tags"] == ["sql"]
    assert (
        item["days_left"] is None and item["deleted_at"]
    )  # by default the Trash is never emptied by itself
    assert authed.get("/api/trash/count").json() == {"count": 1}
    assert (
        authed.delete(f"/api/notes/{gone}").status_code == 404
    )  # already in the Trash


def test_a_restored_note_is_back_with_its_tags_and_searchable(
    authed: TestClient,
) -> None:
    nid = note(authed, "Indeks", "drzewo b-tree", ["sql", "bazy"])
    authed.delete(f"/api/notes/{nid}")
    r = authed.post(f"/api/trash/{nid}/restore")
    assert r.status_code == 200 and r.json()["id"] == nid
    assert r.json()["tags"] == ["bazy", "sql"]
    assert titles(authed, "drzewo") == ["Indeks"]
    assert tag_counts(authed) == {"bazy": 1, "sql": 1}
    assert trash(authed) == [] and authed.get("/api/trash/count").json() == {"count": 0}
    assert (
        authed.post(f"/api/trash/{nid}/restore").status_code == 404
    )  # no longer in the Trash


def test_search_inside_the_trash(authed: TestClient) -> None:
    a = note(authed, "Kot", "mruczy")
    b = note(authed, "Pies", "szczeka")
    authed.delete(f"/api/notes/{a}")
    authed.delete(f"/api/notes/{b}")
    assert [n["title"] for n in trash(authed, "mrucz")] == ["Kot"]
    assert [n["title"] for n in trash(authed, "pies szczeka")] == ["Pies"]
    assert [n["title"] for n in trash(authed)] == [
        "Pies",
        "Kot",
    ]  # latest deletion first


def test_deleting_for_good_and_emptying(authed: TestClient) -> None:
    a, b, live = note(authed, "A"), note(authed, "B"), note(authed, "Live")
    authed.delete(f"/api/notes/{a}")
    authed.delete(f"/api/notes/{b}")
    assert authed.delete(f"/api/trash/{a}").status_code == 204
    assert [n["id"] for n in trash(authed)] == [b]
    assert authed.delete(f"/api/trash/{a}").status_code == 404
    assert (
        authed.delete(f"/api/trash/{live}").status_code == 404
    )  # a live note is not in the Trash
    assert authed.delete("/api/trash").json() == {"deleted": 1}
    assert trash(authed) == [] and titles(authed) == ["Live"]
    assert authed.delete("/api/trash").json() == {"deleted": 0}


def test_the_trash_empties_itself_after_trash_days(authed: TestClient) -> None:
    old, fresh = note(authed, "Old"), note(authed, "Fresh")
    assert authed.put("/api/settings", json={"trash_days": 30}).status_code == 200
    authed.delete(f"/api/notes/{old}")
    authed.delete(f"/api/notes/{fresh}")
    age(old, 40)
    age(fresh, 5)
    assert [n["id"] for n in trash(authed)] == [fresh]  # 40 days > 30: gone
    assert trash(authed)[0]["days_left"] == 25


def test_trash_days_can_be_changed_or_switched_off(authed: TestClient) -> None:
    nid = note(authed, "N")
    authed.delete(f"/api/notes/{nid}")
    age(nid, 1000)
    (item,) = trash(authed)  # the default is 0: never emptied by itself
    assert item["days_left"] is None
    assert authed.put("/api/settings", json={"trash_days": 0}).status_code == 200
    assert len(trash(authed)) == 1
    assert authed.put("/api/settings", json={"trash_days": 7}).status_code == 200
    assert trash(authed) == []
    assert authed.put("/api/settings", json={"trash_days": 366}).status_code == 422


def test_the_trash_is_not_counted_in_categories_and_a_category_can_go_with_it(
    authed: TestClient,
) -> None:
    cid = authed.post("/api/categories", json={"name": "Temp"}).json()["id"]
    nid = authed.post(
        "/api/notes", json={"title": "N", "body": "", "category_id": cid}
    ).json()["id"]

    def counts() -> dict[str, int]:
        return {c["name"]: c["count"] for c in authed.get("/api/categories").json()}

    assert counts()["Temp"] == 1
    authed.delete(f"/api/notes/{nid}")
    assert counts()["Temp"] == 0
    assert (
        authed.delete(f"/api/categories/{cid}").status_code == 204
    )  # only a trashed note was in it
    restored = authed.post(f"/api/trash/{nid}/restore").json()
    default = next(c for c in authed.get("/api/categories").json() if c["default"])
    assert restored["category_id"] == default["id"]


def test_the_trash_is_not_exported_and_an_import_clears_it(authed: TestClient) -> None:
    keep, gone = note(authed, "Keep"), note(authed, "Gone")
    authed.delete(f"/api/notes/{gone}")
    document = authed.get("/api/export").json()
    assert [n["title"] for n in document["notes"]] == ["Keep"]
    assert document["count"] == 1
    assert authed.post("/api/import", json=document).status_code == 200
    assert trash(authed) == [] and titles(authed) == ["Keep"]
    assert keep


def test_a_note_in_the_trash_cannot_be_edited_or_read_through_the_notes_api(
    authed: TestClient,
) -> None:
    nid = note(authed, "N", "body")
    authed.delete(f"/api/notes/{nid}")
    assert (
        authed.put(
            f"/api/notes/{nid}", json={"title": "X", "body": "", "tags": []}
        ).status_code
        == 404
    )
    assert authed.get(f"/api/notes/{nid}").status_code == 404
    assert authed.get(f"/api/notes/{nid}/summary").json() is None


def test_clearing_all_data_empties_the_trash_too(authed: TestClient) -> None:
    nid = note(authed, "N")
    authed.delete(f"/api/notes/{nid}")
    assert authed.delete("/api/data").status_code == 204
    assert trash(authed) == []


def test_the_about_counts_leave_the_trash_out(authed: TestClient) -> None:
    note(authed, "Live")
    gone = note(authed, "Gone")
    authed.delete(f"/api/notes/{gone}")
    assert authed.get("/api/about").json()["notes"] == 1


def test_the_trash_api_needs_a_login() -> None:
    with TestClient(app, follow_redirects=False) as anon:
        assert anon.get("/api/trash").status_code == 401
        assert anon.get("/api/trash/count").status_code == 401
        assert anon.post("/api/trash/1/restore").status_code == 401
        assert anon.delete("/api/trash/1").status_code == 401
        assert anon.delete("/api/trash").status_code == 401
