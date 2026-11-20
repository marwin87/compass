import os
from pathlib import Path

# The CSS, JS and HTML of the pages live in `web/assets/` at the repository root, outside the Python package.
# A checkout finds them by itself; the Docker image sets COMPASS_ASSETS_DIR to where it copied them.
ASSETS = Path(
    os.environ.get("COMPASS_ASSETS_DIR")
    or Path(__file__).resolve().parents[3] / "web" / "assets"
)


def asset(name: str) -> str:
    """The text of a file in `web/assets/` (CSS, JS and HTML kept as real files, read once at import)."""
    return (ASSETS / name).read_text(encoding="utf-8")
