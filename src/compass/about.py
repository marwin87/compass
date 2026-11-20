"""Facts about this installation for the Settings page (read only)."""

from importlib.metadata import PackageNotFoundError, version

from compass.db import db_path, session


def app_version() -> str:
    try:
        return version("compass")
    except PackageNotFoundError:
        return "dev"


def about() -> dict[str, object]:
    with session() as conn:
        counts = {
            name: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for name, table in (
                ("notes", "notes"),
                ("categories", "categories"),
                ("tags", "tags"),
            )
        }
    path = db_path()
    return {
        "version": app_version(),
        **counts,
        "db_size_bytes": path.stat().st_size if path.exists() else 0,
        "db_path": str(path),
    }
