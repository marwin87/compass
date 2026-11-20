# ruff: noqa: F811
import pytest

from compass import ai
from tests.ai.test_translate import Fake, fake  # noqa: F401


def s(**extra: object) -> dict[str, object]:
    return {
        "ai_enabled": True,
        "ai_connection": "local",
        "ai_address": "",
        "ai_model_local": "m1",
        "ai_embed_model_local": "emb",
        "ai_vision_model_local": "",
        **extra,
    }


def test_status_says_whether_embeddings_are_set() -> None:
    assert ai.status(s())["embeddings"] is True
    assert ai.status(s(ai_embed_model_local=""))["embeddings"] is False


def test_status_says_whether_a_vision_model_is_set() -> None:
    assert ai.status(s())["vision"] is False
    assert ai.status(s(ai_vision_model_local="v"))["vision"] is True


def test_embed_returns_one_vector_per_text_in_order(fake: Fake) -> None:
    fake.raw = {
        "data": [
            {"index": 1, "embedding": [0, 1]},
            {"index": 0, "embedding": [1, 0]},
        ]
    }
    assert ai.embed(s(ai_address=fake.url), ["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
    request = fake.requests[0]
    assert request["path"] == "/embeddings"
    assert request["body"] == {"model": "emb", "input": ["a", "b"]}


def test_embed_makes_no_call_when_off_or_without_a_model(fake: Fake) -> None:
    with pytest.raises(ai.AIError) as off:
        ai.embed(s(ai_enabled=False, ai_address=fake.url), ["a"])
    assert off.value.code == "not_enabled"
    with pytest.raises(ai.AIError) as none:
        ai.embed(s(ai_embed_model_local="", ai_address=fake.url), ["a"])
    assert none.value.code == "not_configured"
    assert fake.requests == []


def test_embed_of_nothing_is_nothing(fake: Fake) -> None:
    assert ai.embed(s(ai_address=fake.url), []) == []
    assert fake.requests == []


def test_embed_maps_a_provider_failure(fake: Fake) -> None:
    fake.status = 500
    with pytest.raises(ai.AIError) as err:
        ai.embed(s(ai_address=fake.url), ["a"])
    assert err.value.code == "failed"
