"""graphic.html -> graphic.png (1080 x 1350, LinkedIn) and chart.html -> chart.png (1080 x 420, the post). Needs playwright and a Chromium:

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
    for name, h in (("graphic", 1350), ("chart", 420)):
        page = b.new_page(viewport={"width": 1080, "height": h}, device_scale_factor=1)
        page.goto((here / f"{name}.html").as_uri())
        print(name, "content height", page.evaluate("document.documentElement.scrollHeight"),
              "body", page.evaluate("document.body.scrollHeight"))
        page.screenshot(path=str(here / f"{name}.png"))
    b.close()
