from pathlib import Path

ASSETS = Path(__file__).parent / "assets"


def asset(name: str) -> str:
    """The text of a file in `ui/assets/` (CSS, JS and HTML kept as real files, read once at import)."""
    return (ASSETS / name).read_text(encoding="utf-8")
