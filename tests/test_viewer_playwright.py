"""Static viewer smoke: build-site → local HTTP → Playwright loads index (opt-in: RUN_BROWSER_TESTS=1)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
LLM_WIKI = SCRIPTS / "llm_wiki.py"


def _env_with_scripts(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ) if base is None else {**base}
    p = str(SCRIPTS)
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = p if not prev else f"{p}{os.pathsep}{prev}"
    return env


def _make_handler(og_dir: Path):
    root = str(og_dir.resolve())

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root, **kwargs)

    return _Handler


@pytest.mark.browser
def test_viewer_index_loads_in_chromium(seeded_vault: Path) -> None:
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    r = subprocess.run(
        [sys.executable, str(LLM_WIKI), "--vault", str(seeded_vault), "build-site"],
        cwd=str(REPO),
        env=_env_with_scripts(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr or r.stdout

    og = seeded_vault / "wiki" / ".og"
    assert (og / "index.html").is_file()
    assert (og / "wiki-data.json").is_file()

    handler = _make_handler(og)
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"Chromium not available for Playwright: {e}")
            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded")
                assert "LLM Wiki" in (page.title() or "")
                assert page.locator(".brand").filter(has_text="LLM Wiki").count() >= 1
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
