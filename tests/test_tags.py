from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient


def add(c: TestClient, title: str, tags: list[str], body: str = "") -> int:
    r = c.post("/api/notes", json={"title": title, "body": body, "tags": tags})
    assert r.status_code == 201
    note_id: int = r.json()["id"]
    return note_id


def tag_counts(c: TestClient) -> dict[str, int]:
    return {t["name"]: t["count"] for t in c.get("/api/tags").json()}


def tags_of(c: TestClient, note_id: int) -> list[str]:
    result: list[str] = c.get(f"/api/notes/{note_id}").json()["tags"]
    return result


def rename(c: TestClient, old: str, new: str) -> Any:
    return c.put(f"/api/tags/{quote(old, safe='')}", json={"name": new})


def delete(c: TestClient, name: str) -> Any:
    return c.delete(f"/api/tags/{quote(name, safe='')}")


def found(c: TestClient, q: str = "", **params: Any) -> list[str]:
    r = c.get("/api/notes", params={"q": q, **params})
    return [n["title"] for n in r.json()]


# --- rename


def test_a_rename_changes_the_tag_on_every_note(authed: TestClient) -> None:
    a = add(authed, "a", ["sql", "teoria"])
    b = add(authed, "b", ["sql"])
    add(authed, "c", ["inne"])
    r = rename(authed, "sql", "bazy")
    assert r.status_code == 200
    assert r.json() == {"name": "bazy", "count": 2, "merged": False, "notes": 2}
    assert tags_of(authed, a) == ["bazy", "teoria"] and tags_of(authed, b) == ["bazy"]
    assert tag_counts(authed) == {"bazy": 2, "inne": 1, "teoria": 1}


def test_the_new_name_is_cleaned_like_any_tag(authed: TestClient) -> None:
    add(authed, "a", ["x"])
    r = rename(authed, "x", "  Soft   SKILLS ")
    assert r.status_code == 200 and r.json()["name"] == "soft skills"
    assert "soft skills" in tag_counts(authed)


def test_the_old_name_is_matched_ignoring_case_and_spacing(authed: TestClient) -> None:
    add(authed, "a", ["soft skills"])
    assert rename(authed, " Soft  Skills", "miękkie").status_code == 200


def test_renaming_a_tag_to_itself_changes_nothing(authed: TestClient) -> None:
    add(authed, "a", ["x"])
    r = rename(authed, "x", " X ")
    assert r.status_code == 200 and r.json() == {
        "name": "x",
        "count": 1,
        "merged": False,
        "notes": 0,
    }


def test_a_rename_updates_the_search_index(authed: TestClient) -> None:
    add(authed, "Notatka", ["rozmowa"])
    add(authed, "Inna", [], body="rozmowa wspomniana w treści")
    assert found(authed, "rozmowa")[0] == "Notatka"  # the tag is the strongest hit
    rename(authed, "rozmowa", "wywiad")
    assert found(authed, "wywiad") == ["Notatka"]
    assert found(authed, "rozmowa") == ["Inna"]  # only the body mention is left
    assert found(authed, "", tag="wywiad") == ["Notatka"]
    assert found(authed, "", tag="rozmowa") == []


def test_unusual_names_work_in_the_url(authed: TestClient) -> None:
    for name in ("c++", "a/b", "łódź", "what? yes", "a#b", "100%"):
        add(authed, "t", [name])
        r = rename(authed, name, name + "2")
        assert r.status_code == 200 and r.json()["name"] == name + "2", name


# --- merge


def test_renaming_onto_an_existing_tag_merges_them(authed: TestClient) -> None:
    only_old = add(authed, "a", ["stary"])
    both = add(authed, "b", ["stary", "nowy"])
    only_new = add(authed, "c", ["nowy"])
    r = rename(authed, "stary", "nowy")
    assert r.status_code == 200
    assert r.json() == {"name": "nowy", "count": 3, "merged": True, "notes": 2}
    assert tags_of(authed, only_old) == ["nowy"]
    assert tags_of(authed, both) == ["nowy"]  # no duplicate on a note that had both
    assert tags_of(authed, only_new) == ["nowy"]
    assert tag_counts(authed) == {"nowy": 3}
    assert rename(authed, "stary", "x").status_code == 404  # the old tag is gone


def test_a_merge_updates_the_search_index_and_the_filter(authed: TestClient) -> None:
    add(authed, "Pierwsza", ["a"])
    add(authed, "Druga", ["b"])
    rename(authed, "a", "b")
    assert sorted(found(authed, "", tag="b")) == ["Druga", "Pierwsza"]
    assert found(authed, "", tag="a") == []
    assert sorted(found(authed, "b")) == ["Druga", "Pierwsza"]


def test_a_merge_never_exceeds_the_ten_tag_limit(authed: TestClient) -> None:
    names = [f"t{i}" for i in range(10)]
    note = add(authed, "full", names)
    add(authed, "other", ["extra"])
    assert rename(authed, "t0", "extra").status_code == 200  # a note with t0 gets extra
    assert len(tags_of(authed, note)) == 10
    rename(authed, "t1", "t2")  # both on the same note: it ends with one tag fewer
    assert len(tags_of(authed, note)) == 9


# --- delete


def test_deleting_a_tag_removes_it_from_every_note_and_keeps_the_notes(
    authed: TestClient,
) -> None:
    a = add(authed, "a", ["sql", "teoria"])
    b = add(authed, "b", ["sql"])
    r = delete(authed, "sql")
    assert r.status_code == 200 and r.json() == {"name": "sql", "notes": 2}
    assert tags_of(authed, a) == ["teoria"] and tags_of(authed, b) == []
    assert tag_counts(authed) == {"teoria": 1}
    assert (
        found(authed, "") and len(found(authed, "")) == 2
    )  # both notes are still there


def test_a_delete_updates_the_search_index(authed: TestClient) -> None:
    add(authed, "Notatka", ["unikalnytag"])
    assert found(authed, "unikalnytag") == ["Notatka"]
    delete(authed, "unikalnytag")
    assert found(authed, "unikalnytag") == []
    assert found(authed, "notatka") == ["Notatka"]


def test_the_export_reflects_renamed_and_deleted_tags(authed: TestClient) -> None:
    add(authed, "a", ["x", "y"])
    rename(authed, "x", "z")
    delete(authed, "y")
    exported = authed.get("/api/export").json()["notes"]
    assert [n["tags"] for n in exported] == [["z"]]


# --- errors


@pytest.mark.parametrize("bad", ["", "   ", "a,b", "x" * 31])
def test_an_invalid_new_name_is_refused_and_changes_nothing(
    authed: TestClient, bad: str
) -> None:
    add(authed, "a", ["x"])
    r = rename(authed, "x", bad)
    assert r.status_code == 422
    assert (
        r.json()["detail"]["code"] == "name_invalid" and r.json()["detail"]["max"] == 30
    )
    assert tag_counts(authed) == {"x": 1}


def test_an_unknown_tag_is_404(authed: TestClient) -> None:
    assert rename(authed, "nie ma", "x").status_code == 404
    assert rename(authed, "nie ma", "x").json()["detail"] == {"code": "not_found"}
    assert delete(authed, "nie ma").status_code == 404


def test_thirty_characters_is_the_longest_name(authed: TestClient) -> None:
    add(authed, "a", ["x"])
    assert rename(authed, "x", "y" * 30).status_code == 200


def test_tag_management_needs_login() -> None:
    from compass.main import app

    with TestClient(app, follow_redirects=False) as anon:
        assert anon.put("/api/tags/x", json={"name": "y"}).status_code == 401
        assert anon.delete("/api/tags/x").status_code == 401
