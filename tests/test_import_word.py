# ruff: noqa: F811  (the `fake` fixture is imported from test_translate)
import io
import json
import zipfile
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass import ai, docx, importer, notes
from tests.test_translate import (
    Fake,
    fake,  # noqa: F401  (the fixture, for pytest)
    rows,
    setup_ai,
)

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def para(text: str, style: str = "", bullet: bool = False) -> str:
    ppr = ""
    if style or bullet:
        ppr = "<w:pPr>"
        ppr += f'<w:pStyle w:val="{style}"/>' if style else ""
        ppr += '<w:numPr><w:ilvl w:val="0"/></w:numPr>' if bullet else ""
        ppr += "</w:pPr>"
    return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"


def make_docx(*body: str) -> bytes:
    xml = f"<w:document {NS}><w:body>{''.join(body)}</w:body></w:document>"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("word/document.xml", xml)
    return out.getvalue()


WITH_HEADINGS = make_docx(
    para("Docker", "Heading1"),
    para("Obrazy i kontenery, port 8080."),
    para("pull", bullet=True),
    para("Git", "Heading1"),
    para("Gałęzie.", ""),
    para("Szczegóły", "Heading2"),
    para("Rebase."),
)


def post(c: TestClient, raw: bytes, name: str = "x.docx") -> object:
    return c.post("/api/import/file", content=raw, params={"name": name})


def test_extract_markdown() -> None:
    blocks = docx.extract(WITH_HEADINGS)
    assert [b.heading for b in blocks] == [1, 0, 0, 1, 0, 2, 0]
    assert blocks[2].text == "- pull"


def test_table_becomes_markdown() -> None:
    cell = "<w:tc><w:p><w:r><w:t>{}</w:t></w:r></w:p></w:tc>"
    row = "<w:tr>" + cell + cell + "</w:tr>"
    table = "<w:tbl>" + row.format("a", "b") + row.format("1", "2") + "</w:tbl>"
    (block,) = docx.extract(make_docx(table))
    assert block.text == "| a | b |\n| --- | --- |\n| 1 | 2 |"


def test_windows_cut_at_a_top_heading_and_cut_huge_paragraphs() -> None:
    half = importer.WINDOW // 2
    blocks = [
        docx.Block(1, "A"),
        docx.Block(0, "x" * half),
        docx.Block(1, "B"),
        docx.Block(0, "y"),
    ]
    assert [len(w) for w in importer.windows(blocks)] == [2, 2]
    huge = importer.windows([docx.Block(0, "z" * (importer.WINDOW * 2 + 5))])
    assert len(huge) == 3 and all(len(w) == 1 for w in huge)


def test_a_long_note_is_cut_between_paragraphs() -> None:
    body = "\n\n".join(["x" * 9000] * 5)
    found = importer._fit("Big", body)
    assert len(found) == 3 and found[1].title == "Big (2)"
    assert all(len(p.body) <= notes.MAX_BODY for p in found)


def patch_model(
    monkeypatch: pytest.MonkeyPatch,
    write: Callable[[str, str], str],
    check: Callable[[str], str] = lambda user: "[]",
) -> list[tuple[str, str, str]]:
    """Replace the model. `write(system, user)` is the JSON text the model streams as the notes (in small
    pieces); `check(user)` the JSON list of what is missing. Either may raise AIError. Returns the calls."""
    calls: list[tuple[str, str, str]] = []

    def stream(
        s: dict[str, object], system: str, user: str, timeout: int | None = None
    ) -> Iterator[str]:
        calls.append(("write", system, user))
        text = write(system, user)
        for i in range(0, len(text), 7):
            yield text[i : i + 7]

    def ask(
        s: dict[str, object], system: str, user: str, timeout: int | None = None
    ) -> str:
        calls.append(("check", system, user))
        return check(user)

    monkeypatch.setattr(ai, "stream", stream)
    monkeypatch.setattr(ai, "ask", ask)
    return calls


def events(
    c: TestClient, raw: bytes, parts: str = "", name: str = "x.docx"
) -> list[dict[str, Any]]:
    r = c.post("/api/import/file", content=raw, params={"parts": parts, "name": name})
    assert r.status_code == 200
    return [json.loads(line) for line in r.text.splitlines()]


def of(found: list[dict[str, Any]], kind: str, index: int | None = None) -> list[Any]:
    """The events of one type (and one part)."""
    return [
        e for e in found if e["type"] == kind and (index is None or e["index"] == index)
    ]


def two_parts() -> bytes:
    """Two sections, each too big to share a part."""
    return make_docx(
        para("Alfa", "Heading1"),
        para("a" * 5000),
        para("Beta", "Heading1"),
        para("b" * 5000),
    )


NOTE = {"title": "Docker", "body": "## Obrazy\n\n- pull"}


def test_objects_arrive_while_the_array_is_still_being_written() -> None:
    sent: list[str] = []

    def pieces() -> Iterator[str]:
        for piece in ['Sure: [{"a": 1}, ', '{"b"', ": 2}", " ]"]:
            sent.append(piece)
            yield piece

    got = importer._objects(pieces())
    assert next(got) == {"a": 1} and len(sent) == 1  # before the rest was even written
    assert next(got) == {"b": 2} and len(sent) == 3
    assert next(got) is importer.END
    assert list(importer._objects(iter(["no array here"]))) == []


def test_run_streams_each_note_then_the_check(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    calls = patch_model(
        monkeypatch, lambda s, u: json.dumps([NOTE]), lambda u: '["krok z rebase"]'
    )
    found = events(authed, WITH_HEADINGS)
    assert [e["type"] for e in found] == ["start", "note", "written", "check", "done"]
    assert found[0]["total"] == 1 and found[0]["labels"] == ["Docker"]
    assert found[1]["note"] == {**NOTE, "category": None, "tags": []}
    assert found[2]["unmatched"] == ["8080"]  # the number is in the file, in no note
    assert found[3]["omitted"] == ["krok z rebase"] and found[3]["unchecked"] is False
    assert [c[0] for c in calls] == ["write", "check"] and "# Docker" in calls[0][2]
    assert rows() == []  # nothing saved


def test_nothing_missing_gives_empty_reports(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    body = "Docker 8080 Git Rebase"
    patch_model(monkeypatch, lambda s, u: json.dumps([{"title": "T", "body": body}]))
    found = events(authed, WITH_HEADINGS)
    assert of(found, "check")[0]["omitted"] == []
    assert of(found, "written")[0]["unmatched"] == []


def test_a_failed_part_does_not_stop_the_others_and_can_be_run_again(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    broken = {"on": True}

    def write(system: str, user: str) -> str:
        if "aaaa" in user and broken["on"]:
            raise ai.AIError("failed", "HTTP 429: rate limited")
        return json.dumps([{"title": "N", "body": "b"}])

    patch_model(monkeypatch, write)
    found = events(authed, two_parts())
    assert found[0]["total"] == 2 and found[0]["labels"] == ["Alfa", "Beta"]
    assert of(found, "error", 0) == [
        {
            "type": "error",
            "index": 0,
            "code": "failed",
            "detail": "HTTP 429: rate limited",
        }
    ]
    assert len(of(found, "note", 1)) == 1 and len(of(found, "check", 1)) == 1
    assert found[-1] == {"type": "done"}
    broken["on"] = False
    again = events(authed, two_parts(), parts="0")  # only part 0 is run again
    assert again[0]["parts"] == [0] and {e["index"] for e in of(again, "note")} == {0}


def test_failed_check_keeps_the_notes_and_says_it_is_unchecked(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)

    def check(user: str) -> str:
        raise ai.AIError("timeout")

    patch_model(monkeypatch, lambda s, u: json.dumps([NOTE]), check)
    found = events(authed, WITH_HEADINGS)
    assert len(of(found, "note")) == 1 and of(found, "check")[0]["unchecked"] is True


def test_a_real_stream_shows_notes_piece_by_piece(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    text = json.dumps([NOTE, {"title": "Git", "body": "Rebase"}])
    fake.sse = [text[i : i + 5] for i in range(0, len(text), 5)]
    found = events(authed, WITH_HEADINGS)
    assert [n["note"]["title"] for n in of(found, "note")] == ["Docker", "Git"]
    assert fake.requests[0]["body"]["stream"] is True


def test_a_server_that_ignores_stream_still_works(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.reply = json.dumps([NOTE])  # one plain JSON answer, no events
    found = events(authed, WITH_HEADINGS)
    assert len(of(found, "note")) == 1


def test_unusable_model_reply_is_retried_once_and_explained(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.reply = "no json here"
    error = of(events(authed, WITH_HEADINGS), "error")[0]
    assert error["code"] == "failed" and "usable notes" in error["detail"]
    assert len(fake.requests) == 2 and rows() == []


def test_provider_status_is_reported_as_the_reason(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.status = 401
    error = of(events(authed, WITH_HEADINGS), "error")[0]
    assert error["code"] == "failed" and error["detail"] == "HTTP 401"


def test_an_empty_array_is_an_empty_part_not_an_error(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    calls = patch_model(monkeypatch, lambda s, u: "[]")
    found = events(authed, WITH_HEADINGS)
    assert of(found, "note") == [] and of(found, "written")[0]["count"] == 0
    assert of(found, "error") == [] and [c[0] for c in calls] == ["write"]  # no check


def test_ai_off_or_unconfigured_makes_no_call(authed: TestClient, fake: Fake) -> None:
    r = post(authed, WITH_HEADINGS)
    assert r.status_code == 409 and r.json()["detail"] == {"code": "not_enabled"}  # type: ignore[attr-defined]
    setup_ai(authed, fake, ai_model_local="")
    r = post(authed, WITH_HEADINGS)
    assert r.json()["detail"] == {"code": "not_configured"}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_bad_files(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    r = post(authed, b"not a zip")
    assert r.status_code == 422 and r.json()["detail"] == {"code": "not_docx"}  # type: ignore[attr-defined]
    r = post(authed, make_docx())
    assert r.status_code == 422 and r.json()["detail"] == {"code": "empty"}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_bulk_save_is_all_or_none(authed: TestClient) -> None:
    ok = {"title": "A", "body": "x", "tags": ["t"]}
    r = authed.post("/api/notes/bulk", json={"notes": [ok, {**ok, "title": "B"}]})
    assert r.status_code == 201 and r.json() == {"created": 2}
    assert len(rows()) == 2
    bad = authed.post("/api/notes/bulk", json={"notes": [ok, {"title": ""}]})
    assert bad.status_code == 422 and len(rows()) == 2
    assert authed.post("/api/notes/bulk", json={"notes": []}).status_code == 422


def test_suggestions_reuse_existing_categories_and_tags(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    cat = authed.post("/api/categories", json={"name": "DevOps"}).json()["id"]
    authed.post(
        "/api/notes",
        json={"title": "x", "body": "", "tags": ["docker"], "category_id": cat},
    )
    reply = [
        {
            "title": "N",
            "body": "b",
            "category": " devops ",  # same category, other case and spacing
            "tags": ["Docker", "nowy tag", "docker", "a,b", "x" * 31],
        }
    ]
    calls = patch_model(monkeypatch, lambda s, u: json.dumps(reply))
    note = of(events(authed, WITH_HEADINGS), "note")[0]["note"]
    assert note["category"] == "DevOps"  # mapped onto the existing name
    assert note["tags"] == ["docker", "nowy tag"]  # existing reused, bad ones dropped
    assert (
        '"DevOps"' in calls[0][1] and '"docker"' in calls[0][1]
    )  # the model sees them


def test_suggestion_limits_and_reserved_category(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    reply = [
        {
            "title": "N",
            "body": "b",
            "category": "Bez kategorii",
            "tags": ["a", "b", "c", "d", "e", "f", "g"],
        },
        {"title": "M", "body": "b", "category": 5, "tags": "nope"},
    ]
    patch_model(monkeypatch, lambda s, u: json.dumps(reply))
    first, second = (e["note"] for e in of(events(authed, WITH_HEADINGS), "note"))
    assert first["category"] is None and first["tags"] == ["a", "b", "c", "d", "e"]
    assert second["category"] is None and second["tags"] == []


def test_bulk_save_creates_and_reuses_categories_by_name(authed: TestClient) -> None:
    def note(title: str, category: str | None) -> dict[str, object]:
        return {"title": title, "body": "x", "tags": ["t"], "category": category}

    r = authed.post(
        "/api/notes/bulk",
        json={
            "notes": [
                note("A", "Nowa"),
                note("B", "nowa"),  # same category, other case
                note("C", "Bez kategorii"),  # the default
                note("D", None),
            ]
        },
    )
    assert r.status_code == 201 and r.json() == {"created": 4}
    cats = {c["name"]: c["count"] for c in authed.get("/api/categories").json()}
    assert cats["Nowa"] == 2 and len(cats) == 2  # one new category besides the default
    too_long = authed.post("/api/notes/bulk", json={"notes": [note("E", "k" * 41)]})
    assert too_long.status_code == 422 and len(rows()) == 4
