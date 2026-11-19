"""Fixtures for the browser tests: a real server, a clean state for every test, a logged-in page.

Run them with `uv run pytest -m e2e` (add `--headed --slowmo 300` to watch). They need the browser
installed once (`uv run playwright install chromium`) and are never part of a plain `pytest` run.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Page

PASSWORD = "e2e-password"
DEFAULT_SETTINGS = {"theme": "dark", "reader_size": 17, "reader_width": 1, "sort": ""}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Everything under tests/e2e carries the e2e marker, so `-m "not e2e"` (the default) skips it."""
    here = Path(__file__).parent
    for item in items:
        if here in Path(str(item.path)).parents:
            item.add_marker(pytest.mark.e2e)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.fixture(scope="session")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """The app on a free port with its own temporary database; yields the base URL."""
    port = _free_port()
    folder = tmp_path_factory.mktemp("e2e")
    log = (folder / "server.log").open("w")
    env = {
        **os.environ,
        # Set explicitly: a developer's real .env must never leak into the tests.
        "COMPASS_PASSWORD": PASSWORD,
        "COMPASS_SECRET_KEY": "e2e-secret-key-0123456789abcdef0",
        "COMPASS_DB_PATH": str(folder / "compass.db"),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "compass.main:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            process.kill()
        if process.poll() is not None:
            raise RuntimeError(
                "the e2e server did not start:\n" + (folder / "server.log").read_text()
            )
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


@pytest.fixture(scope="session")
def base_url(server: str) -> str:
    """Overrides the plugin's option: relative URLs in `page.goto()` resolve against our server."""
    return server


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 800},
        "locale": "pl-PL",  # the interface follows Accept-Language: Polish by default
        "reduced_motion": "reduce",  # no transitions to wait for
        "permissions": ["clipboard-read", "clipboard-write"],
    }


def api_client(base_url: str) -> httpx.Client:
    """A logged-in HTTP client for preparing and checking data without the UI."""
    client = httpx.Client(base_url=base_url, follow_redirects=False)
    assert client.post("/login", data={"password": PASSWORD}).status_code == 303
    return client


@pytest.fixture
def api(base_url: str) -> Iterator[httpx.Client]:
    client = api_client(base_url)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(autouse=True)
def clean(base_url: str) -> None:
    """Every test starts from an empty database and the default settings (no restart needed)."""
    client = api_client(base_url)
    try:
        assert client.delete("/api/data").status_code == 204
        assert client.put("/api/settings", json=DEFAULT_SETTINGS).status_code == 200
    finally:
        client.close()


@pytest.fixture
def app(page: Page, base_url: str) -> Page:
    """A page that is already logged in and sitting on the notes page."""
    page.goto("/login")
    page.get_by_placeholder("Hasło").fill(PASSWORD)
    page.get_by_role("button", name="Zaloguj").click()
    page.wait_for_url(f"{base_url}/")
    return page
