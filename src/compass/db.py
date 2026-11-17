import os
import sqlite3
from pathlib import Path


def db_path() -> Path:
    return Path(os.environ.get("COMPASS_DB_PATH", "data/compass.db"))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn
