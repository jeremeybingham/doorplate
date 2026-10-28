"""graphic.html -> graphic.png (1080 x 1350). Needs playwright and a Chromium:

    uv venv /tmp/pw && uv pip install -p /tmp/pw/bin/python playwright
    /tmp/pw/bin/python render.py [path/to/chrome]
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

here = pathlib.Path(__file__).resolve().parent
chrome = sys.argv[1] if len(sys.argv) > 1 else str(
    pathlib.Path.home() / ".cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome)
    page = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
    page.goto((here / "graphic.html").as_uri())
    print("content height", page.evaluate("document.documentElement.scrollHeight"),
          "body", page.evaluate("document.body.scrollHeight"))
    page.screenshot(path=str(here / "graphic.png"))
    b.close()
