# ruff: noqa: F811  (the `fake` fixture is imported from test_translate)
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass.importing import importer, textfile
from compass.importing.docx import BadFile, Block
from tests.ai.test_translate import (
    Fake,
    fake,  # noqa: F401  (the fixture, for pytest)
    rows,
    setup_ai,
)
from tests.importing.test_import_word import events, of, patch_model, post

MD = (
    "# Docker\n\nObrazy i kontenery.\n- pull\n- run\n\n"
    "```sh\ndocker run x\n\n# not a heading\ndocker ps\n```\n\n"
    "## Git\n\nRebase.\n"
)


def test_markdown_becomes_headings_paragraphs_and_one_code_block() -> None:
    blocks = textfile.extract(MD.encode())
    assert [(b.heading, b.text) for b in blocks] == [
        (1, "Docker"),
        (0, "Obrazy i kontenery.\n- pull\n- run"),
        (0, "```sh\ndocker run x\n\n# not a heading\ndocker ps\n```"),
        (2, "Git"),
        (0, "Rebase."),
    ]


def test_plain_text_is_paragraphs_without_headings() -> None:
    blocks = textfile.extract(b"one\ntwo\n\n\nthree\n")
    assert blocks == [Block(0, "one\ntwo"), Block(0, "three")]


def test_macos_files_line_endings_and_decomposed_letters() -> None:
    import unicodedata

    assert textfile.extract(b"# T\rone\r\rtwo\r") == [
        Block(1, "T"),
        Block(0, "one"),
        Block(0, "two"),
    ]  # classic Mac: CR only
    composed = "Zażółć gęślą"
    decomposed = unicodedata.normalize("NFD", composed).encode()
    assert textfile.extract(decomposed) == [Block(0, composed)]


def test_encodings_and_refused_input() -> None:
    assert textfile.extract("﻿Zażółć gęślą".encode()) == [Block(0, "Zażółć gęślą")]
    assert textfile.extract("Zażółć gęślą".encode("cp1250")) == [
        Block(0, "Zażółć gęślą")
    ]  # an old Windows file
    for raw, code in [(b"\x00\x01binary", "not_text"), (b"  \n\n", "empty")]:
        with pytest.raises(BadFile) as problem:
            textfile.extract(raw)
        assert problem.value.code == code


def test_a_markdown_file_flows_through_the_same_import(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    note = {"title": "Docker", "body": "- pull"}
    calls = patch_model(monkeypatch, lambda s, u: json.dumps([note]))
    found: list[dict[str, Any]] = events(authed, MD.encode(), name="notes.MD")
    assert found[0]["labels"] == ["Docker"]  # headings give the parts their labels
    assert len(of(found, "note")) == 1 and of(found, "check")
    assert "# Docker" in calls[0][2] and "docker ps" in calls[0][2]
    assert rows() == []  # nothing saved


def test_a_plain_text_file_works_too(
    authed: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup_ai(authed, fake)
    patch_model(monkeypatch, lambda s, u: json.dumps([{"title": "T", "body": "b"}]))
    found = events(authed, b"just some text\n\nmore text", name="a.txt")
    assert len(of(found, "note")) == 1


def test_unsupported_and_unreadable_files_are_refused_before_any_call(
    authed: TestClient, fake: Fake
) -> None:
    setup_ai(authed, fake)
    r = post(authed, b"x", name="sheet.xlsx")
    assert r.status_code == 422 and r.json()["detail"] == {"code": "unsupported"}  # type: ignore[attr-defined]
    r = post(authed, b"x", name="")
    assert r.json()["detail"] == {"code": "unsupported"}  # type: ignore[attr-defined]
    r = post(authed, b"\x00\x01", name="a.txt")
    assert r.json()["detail"] == {"code": "not_text"}  # type: ignore[attr-defined]
    r = post(authed, b"   ", name="a.md")
    assert r.json()["detail"] == {"code": "empty"}  # type: ignore[attr-defined]
    assert fake.requests == []


def test_long_text_without_headings_is_cut_into_parts() -> None:
    blocks = textfile.extract((("x" * 3000 + "\n\n") * 6).encode())
    assert len(importer.windows(blocks)) == 3  # about 8000 characters each
