# ruff: noqa: F811  (the `fake` fixture is imported from test_translate)
import io
import json
import zipfile
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


def post(c: TestClient, raw: bytes) -> object:
    return c.post("/api/import/word", content=raw)


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


def model(
    monkeypatch: pytest.MonkeyPatch, written: object, missing: object
) -> list[str]:
    """Replace the model: the 'write notes' call gets `written`, the 'check' call gets `missing`."""
    calls: list[str] = []

    def ask(
        s: dict[str, object], system: str, user: str, timeout: int | None = None
    ) -> str:
        calls.append(user)
        return json.dumps(missing if system == importer.CHECK else written)

    monkeypatch.setattr(ai, "ask", ask)
    return calls


def events(c: TestClient, raw: bytes, parts: str = "") -> list[dict[str, Any]]:
    r = c.post("/api/import/word", content=raw, params={"parts": parts})
    assert r.status_code == 200
    return [json.loads(line) for line in r.text.splitlines()]


def two_parts() -> bytes:
    """Two sections, each too big to share a part."""
    return make_docx(
        para("Alfa", "Heading1"),
        para("a" * 5000),
        para("Beta", "Heading1"),
        para("b" * 5000),
    )


def test_run_streams_notes_and_reports_what_is_missing(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    calls = model(
        monkeypatch,
        [{"title": "Docker", "body": "## Obrazy\n\n- pull"}],
        ["krok z rebase"],
    )
    start, part, done = events(authed, WITH_HEADINGS)
    assert (
        start["type"] == "start"
        and start["total"] == 1
        and start["labels"] == ["Docker"]
    )
    assert part["notes"] == [{"title": "Docker", "body": "## Obrazy\n\n- pull"}]
    assert part["omitted"] == ["krok z rebase"] and part["unchecked"] is False
    assert part["unmatched"] == ["8080"]  # the number is in the file, in no note
    assert done == {"type": "done"}
    assert len(calls) == 2 and "# Docker" in calls[0]  # write, then check
    assert rows() == []  # nothing saved


def test_nothing_missing_gives_empty_reports(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    model(monkeypatch, [{"title": "T", "body": "Docker 8080 Git Rebase"}], [])
    part = events(authed, WITH_HEADINGS)[1]
    assert part["omitted"] == [] and part["unmatched"] == []


def test_a_failed_part_does_not_stop_the_others_and_can_be_run_again(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    broken = {"on": True}

    def ask(
        s: dict[str, object], system: str, user: str, timeout: int | None = None
    ) -> str:
        if system == importer.CHECK:
            return "[]"
        if "aaaa" in user and broken["on"]:
            raise ai.AIError("failed", "HTTP 429: rate limited")
        return json.dumps([{"title": "N", "body": user[:20]}])

    monkeypatch.setattr(ai, "ask", ask)
    start, first, second, done = events(authed, two_parts())
    assert start["total"] == 2 and start["labels"] == ["Alfa", "Beta"]
    assert first == {
        "type": "error",
        "index": 0,
        "code": "failed",
        "detail": "HTTP 429: rate limited",
    }
    assert second["type"] == "part" and second["index"] == 1 and done["type"] == "done"
    broken["on"] = False
    again = events(authed, two_parts(), parts="0")  # only part 0 is run again
    assert [e["type"] for e in again] == ["start", "part", "done"]
    assert again[0]["parts"] == [0] and again[1]["index"] == 0


def test_failed_check_keeps_the_notes_and_says_it_is_unchecked(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)

    def ask(
        s: dict[str, object], system: str, user: str, timeout: int | None = None
    ) -> str:
        if system == importer.CHECK:
            raise ai.AIError("timeout")
        return json.dumps([{"title": "N", "body": "b"}])

    monkeypatch.setattr(ai, "ask", ask)
    part = events(authed, WITH_HEADINGS)[1]
    assert part["type"] == "part" and part["unchecked"] is True and part["notes"]


def test_unusable_model_reply_is_retried_once_and_explained(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.reply = "no json here"
    error = events(authed, WITH_HEADINGS)[1]
    assert error["type"] == "error" and error["code"] == "failed"
    assert "usable list" in error["detail"]
    assert len(fake.requests) == 2 and rows() == []


def test_provider_status_is_reported_as_the_reason(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    fake.status = 401
    error = events(authed, WITH_HEADINGS)[1]
    assert error["code"] == "failed" and error["detail"] == "HTTP 401"


def test_no_notes_from_the_model_is_an_empty_part(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    model(monkeypatch, [], [])
    part = events(authed, WITH_HEADINGS)[1]
    assert part["type"] == "part" and part["notes"] == []


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
