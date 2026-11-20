# ruff: noqa: F811  (the `fake` fixture is imported from test_translate)
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter

from compass import api
from compass.importing import importer, pdf
from compass.importing.docx import BadFile
from tests.ai.test_translate import (
    Fake,
    fake,  # noqa: F401  (the fixture, for pytest)
    rows,
    setup_ai,
)
from tests.importing.test_import_word import events, of, patch_model, post

NOTE = json.dumps([{"title": "T", "body": "b"}])


def make_pdf(pages: list[str]) -> bytes:
    """A tiny PDF with one line of Helvetica text per line of `pages` (pypdf rebuilds a wrong xref)."""
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, text in enumerate(pages):
        body = (
            "BT /F1 12 Tf 14 TL 50 700 Td "
            + " T* ".join(f"({line}) Tj" for line in text.split("\n"))
            + " ET"
        )
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        objs.append(f"<< /Length {len(body)} >>\nstream\n{body}\nendstream".encode())
    out = b"%PDF-1.4\n"
    for n, obj in enumerate(objs, 1):
        out += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    return (
        out
        + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n0\n%%EOF".encode()
    )


def blank(encrypt: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    if encrypt:
        writer.encrypt("pw", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_pages_become_blocks_in_order() -> None:
    blocks = pdf.extract(make_pdf(["First page\nsecond line", "Page two"]), 10_000)
    assert [b.text for b in blocks] == ["First page\nsecond line", "Page two"]
    assert all(b.heading == 0 for b in blocks)


def test_lines_repeated_on_most_pages_are_dropped() -> None:
    bodies = ["alpha topic", "beta topic", "gamma topic", "delta topic"]
    pages = [f"ACME report\nPage {n} of 4\n{bodies[n - 1]}" for n in range(1, 5)]
    text = "\n".join(b.text for b in pdf.extract(make_pdf(pages), 10_000))
    assert "ACME" not in text and "Page" not in text
    assert "gamma topic" in text
    two = pdf.extract(
        make_pdf(["Same\nA", "Same\nB"]), 10_000
    )  # too few pages to call it a header
    assert "Same" in two[0].text


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (blank(), "empty"),  # no text: a scan looks like this
        (blank(encrypt=True), "encrypted"),
        (b"", "not_pdf"),
        (b"just text, no pdf here", "not_pdf"),
        (b"%PDF-1.4\ngarbage", "not_pdf"),
    ],
)
def test_unreadable_pdfs_say_why(raw: bytes, code: str) -> None:
    with pytest.raises(BadFile) as problem:
        pdf.extract(raw, 10_000)
    assert problem.value.code == code


def test_extraction_stops_when_the_text_is_over_the_limit() -> None:
    with pytest.raises(BadFile) as problem:
        pdf.extract(make_pdf(["x" * 60] * 10), 100)
    assert problem.value.code == "too_large"


def test_a_pdf_flows_through_the_same_import(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    calls = patch_model(monkeypatch, lambda s, u: NOTE)
    found = events(authed, make_pdf(["Docker basics", "Git rebase"]), name="Notes.PDF")
    assert len(of(found, "note")) == 1 and of(found, "check")
    assert calls[0][2].index("Docker basics") < calls[0][2].index("Git rebase")
    assert rows() == []  # nothing saved


def test_refused_pdfs_make_no_model_call(authed: TestClient, fake: Fake) -> None:
    setup_ai(authed, fake)
    for raw, code in [
        (blank(), "empty"),
        (blank(encrypt=True), "encrypted"),
        (b"x", "not_pdf"),
    ]:
        r = post(authed, raw, name="a.pdf")
        assert r.status_code == 422 and r.json()["detail"] == {"code": code}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_too_much_text_is_too_large(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    monkeypatch.setattr(importer, "MAX_TEXT", 50)
    r = post(authed, make_pdf(["x" * 80]), name="a.pdf")
    assert r.status_code == 413 and r.json()["detail"] == {"code": "too_large"}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_a_pdf_has_its_own_size_limit(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    monkeypatch.setattr(api, "MAX_WORD_BYTES", 100)
    monkeypatch.setattr(api, "MAX_PDF_BYTES", 100_000)
    patch_model(monkeypatch, lambda s, u: NOTE)
    pdf_bytes = make_pdf(["hello"])
    assert len(pdf_bytes) > 100
    assert post(authed, pdf_bytes, name="a.pdf").status_code == 200  # type: ignore[attr-defined]
    assert post(authed, pdf_bytes, name="a.txt").status_code == 413  # type: ignore[attr-defined]
    monkeypatch.setattr(api, "MAX_PDF_BYTES", 50)
    assert post(authed, pdf_bytes, name="a.pdf").status_code == 413  # type: ignore[attr-defined]


def scan(sizes: list[tuple[int, int]]) -> bytes:
    """A PDF whose pages are only pictures (a scan): one white picture of each size per page."""
    pictures = [Image.new("RGB", size, "white") for size in sizes]
    out = io.BytesIO()
    pictures[0].save(out, "PDF", save_all=True, append_images=pictures[1:])
    return out.getvalue()


def joined(*parts: bytes) -> bytes:
    """The pages of several PDFs, one after the other."""
    writer = PdfWriter()
    for part in parts:
        writer.append(PdfReader(io.BytesIO(part)))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def reader(replies: list[str]) -> tuple[pdf.Read, list[tuple[int, str]]]:
    """A stand-in for the vision model: answers from `replies` in turn, notes the size and type it got."""
    seen: list[tuple[int, str]] = []

    def read(image: bytes, mime: str) -> str:
        seen.append((Image.open(io.BytesIO(image)).width, mime))
        return replies[len(seen) - 1]

    return read, seen


def test_a_scan_is_read_picture_by_picture_in_page_order() -> None:
    read, seen = reader(["first scanned page", "second scanned page"])
    blocks = pdf.extract(scan([(400, 400), (500, 300)]), 10_000, read)
    assert [b.text for b in blocks] == ["first scanned page", "second scanned page"]
    assert sorted(seen) == [(400, "image/jpeg"), (500, "image/jpeg")]


def test_a_big_picture_is_scaled_down_and_tiny_ones_are_not_read() -> None:
    read, seen = reader(["text"])
    pdf.extract(scan([(3000, 1000)]), 10_000, read)
    assert seen[0][0] == pdf.MAX_SIDE
    read, seen = reader([])
    with pytest.raises(BadFile):
        pdf.extract(scan([(50, 50)]), 10_000, read)  # an icon: nothing to read, no call
    assert seen == []


def test_pictures_on_a_page_that_has_text_are_not_read() -> None:
    page = joined(
        make_pdf(["A page with enough text on it to be a text page."]),
        scan([(400, 400)]),
    )
    read, seen = reader(["scanned"])
    blocks = pdf.extract(page, 10_000, read)
    assert [b.text for b in blocks] == [
        "A page with enough text on it to be a text page.",
        "scanned",
    ]
    assert len(seen) == 1  # only the picture-only page


def test_a_scan_without_a_vision_model_and_too_many_pictures() -> None:
    with pytest.raises(BadFile) as problem:
        pdf.extract(scan([(400, 400)]), 10_000, None)
    assert problem.value.code == "no_vision"
    read, seen = reader([])
    with pytest.raises(BadFile) as problem:
        pdf.extract(scan([(400, 400)] * (pdf.MAX_PICTURES + 1)), 10_000, read)
    assert (
        problem.value.code == "too_many_images" and seen == []
    )  # refused before any call
    with pytest.raises(BadFile) as problem:
        pdf.extract(scan([(400, 400)]), 10_000, lambda image, mime: "")  # no text on it
    assert problem.value.code == "empty"


def vision_calls(f: Fake) -> list[dict[str, object]]:
    return [r["body"] for r in f.requests if r["path"] == "/chat/completions"]


def test_a_scanned_pdf_is_read_by_the_vision_model_through_the_import(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake, ai_vision_model_local="v1")
    fake.reply = "Scanned: Docker basics"
    calls = patch_model(monkeypatch, lambda s, u: NOTE)
    found = events(authed, scan([(400, 400)]), name="scan.pdf")
    assert len(of(found, "note")) == 1
    (body,) = vision_calls(fake)
    assert body["model"] == "v1"
    assert "Scanned: Docker basics" in calls[0][2]  # what the notes are written from
    assert rows() == []


def test_a_scan_without_a_vision_model_says_to_set_one(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    r = post(authed, scan([(400, 400)]), name="scan.pdf")
    assert r.status_code == 422 and r.json()["detail"] == {"code": "no_vision"}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_a_text_pdf_never_calls_the_vision_model(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake, ai_vision_model_local="v1")
    patch_model(monkeypatch, lambda s, u: NOTE)
    events(
        authed, make_pdf(["Docker basics, a text page with real text."]), name="a.pdf"
    )
    assert vision_calls(fake) == []
