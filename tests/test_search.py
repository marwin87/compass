import pytest

from compass.search import (
    BODY,
    EXACT,
    FUZZY,
    PREFIX,
    TAG,
    TITLE,
    edit_distance,
    fold,
    fuzzy_terms,
    rank_key,
    words,
)


@pytest.mark.parametrize(
    ("raw", "folded"),
    [
        ("złożoność", "zlozonosc"),
        ("ŻÓŁĆ", "zolc"),
        ("Zażółć gęślą jaźń", "zazolc gesla jazn"),
        ("Łódź", "lodz"),
        ("Straße", "strasse"),
        ("plain ascii", "plain ascii"),
        ("", ""),
    ],
)
def test_fold(raw: str, folded: str) -> None:
    assert fold(raw) == folded


def test_words_split_like_the_index_does() -> None:
    assert words("Big-O: foo_bar, 42 ŁÓDŹ!") == ["big", "o", "foo", "bar", "42", "lodz"]
    assert words("  ... ") == []


def key(
    query: str,
    title: str = "",
    body: str = "",
    tags: tuple[str, ...] = (),
    fuzzy: dict[str, set[str]] | None = None,
) -> tuple[int, int, int]:
    return rank_key(words(query), title, body, tags, fuzzy or {})


def test_rank_key_tiers_and_exactness() -> None:
    assert key("sql", tags=("sql",)) == (1, TAG, EXACT)
    assert key("sql", title="SQL basics") == (1, TITLE, EXACT)
    assert key("sql", title="SQLite") == (1, TITLE, PREFIX)
    assert key("sql", body="o sql") == (1, BODY, EXACT)
    assert key("soft", tags=("soft skills",)) == (1, BODY, EXACT)  # not an exact tag
    assert key("soft skills", tags=("soft skills",)) == (2, TAG, EXACT)
    assert key("indeks", title="Indkes", fuzzy={"indeks": {"indkes"}}) == (
        1,
        TITLE,
        FUZZY,
    )
    assert key("indeks", title="Kuchnia") == (0, 0, 0)


def test_rank_key_orders_the_way_the_plan_says() -> None:
    assert key("sql", tags=("sql",), title="x") > key("sql", title="SQL")
    assert key("sql", title="SQL") > key("sql", body="sql")
    assert key("a b", body="a b") > key("a b", title="a")  # more words first
    assert key("indeks", title="Indeks") > key("indeks", title="Indeksy")
    assert key("indeks", title="Indeksy") > key(
        "indeks", title="Indkes", fuzzy={"indeks": {"indkes"}}
    )


@pytest.mark.parametrize(
    ("a", "b", "limit", "expected"),
    [
        ("indeks", "indeks", 1, 0),
        ("indeks", "indekt", 1, 1),  # substitution
        ("indeks", "indek", 1, 1),  # deletion
        ("indeks", "indeksy", 1, 1),  # insertion
        ("indeks", "indkes", 1, 1),  # adjacent swap is ONE edit
        ("indeks", "idnkes", 1, None),  # two swaps
        ("indeks", "idnkes", 2, 2),
        ("abc", "abcdef", 2, None),  # length gap alone is too big
    ],
)
def test_edit_distance(a: str, b: str, limit: int, expected: int | None) -> None:
    assert edit_distance(a, b, limit) == expected


def test_fuzzy_terms_follow_the_length_rules() -> None:
    vocab = ["indeks", "indekt", "indkes", "indeksy", "kuchnia", "sqr", "sql", "api"]
    assert fuzzy_terms("indeks", vocab) == {
        "indekt",
        "indkes",
        "indeksy",
    }  # 1 edit, not itself
    assert fuzzy_terms("sql", vocab) == set()  # under 4 letters: never corrected
    assert fuzzy_terms("api", vocab) == set()
    # 8+ letters tolerate two edits, 4-7 only one
    assert fuzzy_terms("zlozonosc", ["zlozonosc", "zlozonsoc", "zlzonoc"]) == {
        "zlozonsoc",
        "zlzonoc",
    }
    assert fuzzy_terms("abcdef", ["abxxef"]) == set()


def test_fuzzy_terms_are_capped_and_closest_first() -> None:
    letters = "xyzwuv"
    two_edits = [
        f"abcdef{a}{b}" for a in letters for b in letters
    ]  # 36 terms, distance 2
    one_edit = "zbcdefgh"  # distance 1, but sorts last alphabetically
    found = fuzzy_terms("abcdefgh", [*two_edits, one_edit])
    assert len(found) == 25
    assert (
        one_edit in found
    )  # the cap keeps the closest terms, not the alphabetical first
