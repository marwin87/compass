"""Facts about this installation for the Settings page (read only)."""

from importlib.metadata import PackageNotFoundError, version

from compass.db import connect, db_path


def app_version() -> str:
    try:
        return version("compass")
    except PackageNotFoundError:
        return "dev"


def about() -> dict[str, object]:
    conn = connect()
    try:
        counts = {
            name: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for name, table in (
                ("notes", "notes"),
                ("categories", "categories"),
                ("tags", "tags"),
            )
        }
    finally:
        conn.close()
    path = db_path()
    return {
        "version": app_version(),
        **counts,
        "db_size_bytes": path.stat().st_size if path.exists() else 0,
        "db_path": str(path),
    }
