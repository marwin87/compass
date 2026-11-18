"""Regenerates README screenshots: `uv run python scripts/screenshots.py` (writes OUT_DIR/*.png).

=== INSTRUCTIONS FOR CLAUDE: reusing this file in another app ===========================================
This file is self-contained and has no dependency on the app it lives in. To use it elsewhere:
 1. Copy it to <app>/scripts/screenshots.py. Do not change the part marked "GENERIC RUNNER" (bottom).
 2. Read the app first: how it starts, its health/ready URL, how it logs in, what demo data exists,
    which pages are worth showing, and the visible texts/roles of the controls (README, pyproject,
    package.json, the code of the UI). Never guess selectors.
 3. Edit ONLY the three marked sections:
      A. CONFIG   - start command, env, health URL, output dir, viewport, locale, theme.
      B. seed()   - put the app in a good-looking state through its API or CLI (demo data, settings).
                    Return nothing; raise (assert) when something fails. Delete the body if not needed.
      C. steps()  - the screenshots: navigate/click/fill, wait for a visible result, call shot(page, name).
 4. Dependencies: playwright (+ `playwright install chromium` once) and httpx. Add them as dev deps
    (Python: `uv add --dev playwright httpx`). A non-Python app is fine: START_CMD is any command.
 5. Use a TEMPORARY database/data dir in ENV so the real data is never touched.
 6. Selectors: get_by_role / get_by_label / get_by_placeholder / get_by_text first, get_by_test_id only
    if those are ambiguous; never CSS/XPath. Never wait_for_timeout: wait for state with expect(...)
    .to_be_visible(), page.wait_for_url(), page.expect_response(...).
 7. Run it, then LOOK at every PNG (Read tool): no cut-off content, no error toasts, no empty states,
    no real personal data, the interesting part is visible. Fix and re-run until they are right.
 8. Add the images to README.md with a one-line caption each, and a line on how to regenerate them.
 9. Third-party calls (an LLM, payments, mail) must not need real keys: if the app talks to such a
    service, point it at a small local stub (see FakeModel below, an example of an OpenAI-compatible
    one) and say so in a comment. Remove the stub when the app has nothing like it.
Compass-specific bits in this copy (examples to replace): COMPASS_* env, /api/import, the AI stub,
the note titles and the button names in steps().
=========================================================================================================
"""

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# ===== A. CONFIG (edit) ==================================================================================
OUT_DIR = ROOT / "docs" / "screenshots"
VIEWPORT = {"width": 1280, "height": 800}
LOCALE = "en-US"  # the browser language; many apps pick their UI language from it
COLOR_SCHEME = "dark"  # "dark" | "light"; for apps that follow the OS theme
PASSWORD = "screenshots"  # the login used below (steps/seed), set through ENV when the app needs one
HEALTH_PATH = "/health"  # a URL that answers 200 when the app is up ("/" if there is no health route)
START_CMD = [  # {port} is replaced with a free port. Any command works (npm run dev -- --port {port}...)
    sys.executable,
    "-m",
    "uvicorn",
    "compass.main:app",
    "--port",
    "{port}",
    "--log-level",
    "warning",
]


def env(data_dir: str) -> dict[str, str]:
    """Environment for the app: secrets and a TEMPORARY data location (`data_dir` is a fresh temp folder)."""
    return {
        **os.environ,
        "COMPASS_PASSWORD": PASSWORD,
        "COMPASS_SECRET_KEY": "screenshots-secret-key-0123456789abcdef",
        "COMPASS_DB_PATH": f"{data_dir}/compass.db",
    }


# ===== (optional) stub of an external service the app calls; here an OpenAI-compatible model ==========
SUMMARY = (
    "## Podsumowanie\n\nB-drzewo to płytka, zrównoważona struktura, dzięki której baza znajduje wiersze "
    "bez przeglądania całej tabeli. Indeks przyspiesza odczyty kosztem zapisów i miejsca, a `EXPLAIN` "
    "pokazuje, czy zapytanie z niego korzysta.\n\n## Najważniejsze punkty\n\n"
    "- Nawet miliard wierszy to zwykle 3–4 poziomy drzewa.\n"
    "- Węzeł, który się przepełni, dzieli się na dwa, a środkowy klucz idzie wyżej.\n"
    "- W indeksie złożonym kolejność kolumn ma znaczenie.\n"
    "- Funkcja na kolumnie w `WHERE` wyłącza zwykły indeks.\n"
)
TRANSLATION = (
    "## Week 1–2\n\n- Mon: upper body\n- Wed: lower body\n- Fri: cardio, 30 min\n\n"
    "## Week 3–4\n\nThe same, but +1 set in every exercise and a 60-minute walk on Sunday.\n\n"
    "> [!NOTE]\n> The most important thing is not to skip more than 2 days in a row.\n"
)


class FakeModel(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        system = payload["messages"][0]["content"]
        text = SUMMARY if system.startswith("Summarize") else TRANSLATION
        data = json.dumps({"choices": [{"message": {"content": text}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


# ===== B. seed (edit): put the app in a good-looking state ================================================
def seed(url: str, stub_port: int) -> None:
    """Runs once after the app is up and before the browser opens. Use the app's API/CLI, not the UI."""
    api = httpx.Client(base_url=url)
    assert api.post("/login", data={"password": PASSWORD}).status_code == 303
    demo = (ROOT / "demo" / "compass-demo.json").read_bytes()
    r = api.post(
        "/api/import", content=demo, headers={"content-type": "application/json"}
    )
    assert r.status_code == 200, r.text
    settings = {  # switch AI on and point it at the stub
        "theme": "dark",
        "ai_enabled": True,
        "ai_connection": "local",
        "ai_address": f"127.0.0.1:{stub_port}",
        "ai_model_local": "llama3.1",
    }
    assert api.put("/api/settings", json=settings).status_code == 200


# ===== C. steps (edit): the screenshots ====================================================================
def open_note(page: Page, title: str) -> None:
    page.locator("#results").get_by_role(
        "button", name=re.compile(re.escape(title))
    ).click()
    page.locator("#detail").get_by_role("heading", name=title).wait_for()


def steps(page: Page, url: str) -> None:
    """`page` is a fresh browser page. Log in, drive the UI, call shot(page, "name") for each image."""
    page.goto("/login")
    page.get_by_placeholder("Password").fill(PASSWORD)
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url(f"{url}/")
    detail = page.locator("#detail")

    # AI (top priority): summary, then translation of a Polish note
    open_note(page, "B-drzewo od środka (długa notatka)")
    detail.get_by_role("button", name="Summarize", exact=True).click()
    expect(detail.get_by_role("heading", name="Najważniejsze punkty")).to_be_visible()
    shot(page, "ai-summary")

    open_note(page, "Plan treningowy na 4 tygodnie")
    detail.get_by_role("button", name="Translate PL→EN").click()
    expect(detail.get_by_role("heading", name="Week 1–2")).to_be_visible()
    shot(page, "ai-translate")

    # list with the side panel, then typo-tolerant search
    open_note(page, "Cheatsheet: Git i Docker")
    shot(page, "list")
    with page.expect_response(lambda r: "q=indkes" in r.url):
        page.get_by_placeholder("Search…").fill("indkes")
    expect(page.locator("#results").get_by_role("button").first).to_contain_text(
        "B-drzewo"
    )
    shot(page, "search")
    page.get_by_placeholder("Search…").fill("")

    # editor
    open_note(page, "Cheatsheet: Git i Docker")
    detail.get_by_role("button", name="Edit", exact=True).click()
    page.get_by_placeholder("Title").wait_for()
    shot(page, "editor")

    # settings
    page.goto("/settings")
    page.get_by_role("heading", name="Settings", level=1).wait_for()
    shot(page, "settings")
    page.goto("/settings#ai")
    expect(page.locator("#ai-status")).not_to_be_empty()
    page.locator("#ai").scroll_into_view_if_needed()
    shot(page, "ai-settings")


# ===== GENERIC RUNNER (do not edit when reusing) ============================================================
def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def shot(page: Page, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=OUT_DIR / f"{name}.png")
    print("saved", name)


def main() -> None:
    stub = ThreadingHTTPServer(
        ("127.0.0.1", 0), FakeModel
    )  # drop with FakeModel if unused
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [a.replace("{port}", str(port)) for a in START_CMD],
        env=env(tempfile.mkdtemp()),
        cwd=ROOT,
    )
    try:
        for _ in range(150):  # up to ~30 s
            if server.poll() is not None:
                raise RuntimeError("the app exited before it was ready")
            try:
                if httpx.get(url + HEALTH_PATH, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            raise RuntimeError(f"{url}{HEALTH_PATH} never answered 200")
        seed(url, stub.server_address[1])
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                base_url=url,
                viewport=VIEWPORT,
                locale=LOCALE,
                color_scheme=COLOR_SCHEME,
                reduced_motion="reduce",
            )
            steps(context.new_page(), url)
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        stub.shutdown()


if __name__ == "__main__":
    main()
