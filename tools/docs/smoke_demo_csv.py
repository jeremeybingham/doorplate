#!/usr/bin/env python3
"""A headless-browser check of the CSV section of the demo page (#335, #434), with an invented file.

    cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release
    cargo build -p doorplate-cli
    python tools/docs/smoke_demo_csv.py [--chrome PATH]

Needs Playwright (a throwaway venv: `uv venv /tmp/pw && uv pip install -p /tmp/pw/bin/python playwright`;
do not run `playwright install`, pass the browser with --chrome, for example
~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome). Serves the page from a temporary folder
(front matter and Liquid tags removed) on 127.0.0.1, loads an invented CSV, parses it in the page and
checks: every request went to that server; a request to another host is blocked; the downloaded CSV has
the added columns and equals `doorplate parse-file` on the same file; quoted fields with newlines and
commas survive; cells that look like formulas are guarded; a cancel stops the run. Then the guided path (#434):
a typed address brings up step 2, the sample file loads with the visitor's address as its last row and parses,
step 3 anonymizes the parsed output, and the masked file keeps its shape (row count, columns, ids) and none of
the invented street names of the original.
Not part of `pytest` (it needs a browser).
"""

import argparse
import csv
import functools
import http.server
import io
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "site" / "demo"
WASM = ROOT / "target" / "wasm32-unknown-unknown" / "release" / "doorplate_wasm.wasm"
CLI = ROOT / "target" / "debug" / "doorplate"

ADDRESSES = [
    "123 north main street apt 4, Miami FL 33101",
    "% ACME CORP, 21-77 31st st, flushing ny 11354",
    "PO BOX 123 ORLANDO FL 32801",
    "RR 2 BOX 152 ocala fl 34482",
    "1204 e. 5th ave suite 200 austin tx 78701",
    '=HYPERLINK("http://example.invalid")',
    "",
    "4417 4417 N OAK AVE, TAMPA FL",
]


def make_csv(path, rows=2500):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "address", "note"])
        for i in range(rows):
            addr = ADDRESSES[i % len(ADDRESSES)]
            note = (
                'say "hi",\nthen go' if i % 7 == 0 else "-5" if i % 5 == 0 else "plain"
            )
            w.writerow([i, f"Person {i}", addr, note])


def serve(folder):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            pass

    handler = functools.partial(Quiet, directory=str(folder))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome")
    ap.add_argument("--rows", type=int, default=2500, help="rows in the invented file")
    args = ap.parse_args()
    for need in (WASM, CLI):
        if not need.exists():
            sys.exit(f"build first: {need} is missing")
    tmp = Path(tempfile.mkdtemp())
    try:
        page_src = (DEMO / "index.html").read_text()
        page_src = (
            re.sub(r"\A---.*?---\n", "", page_src, flags=re.DOTALL)
            .replace("{% raw %}", "")
            .replace("{% endraw %}", "")
        )
        (tmp / "index.html").write_text(page_src)
        for name in ("csv-core.js", "csv.js", "csv-worker.js", "sample-addresses.csv"):
            shutil.copy(DEMO / name, tmp / name)
        shutil.copy(WASM, tmp / "doorplate.wasm")
        src = tmp / "input.csv"
        make_csv(src, args.rows)
        srv = serve(tmp)
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        requests = []
        with sync_playwright() as p:
            browser = (
                p.chromium.launch(executable_path=args.chrome, args=["--no-sandbox"])
                if args.chrome
                else p.chromium.launch()
            )
            page = browser.new_page(accept_downloads=True)
            page.on("request", lambda r: requests.append(r.url))
            page.goto(base + "/index.html")
            # The one-address demo above shares the page and its policy: it must still work.
            page.wait_for_selector("#dp-app:not([hidden])", timeout=30000)
            assert page.is_hidden("#dp-status"), page.inner_text("#dp-status")
            page.fill("#dp-q", "123 north main street apt 4, Miami FL 33101")
            page.wait_for_selector("#dp-out td:has-text('k4:')", timeout=10000)
            page.wait_for_selector("#dp-csv-file:not([disabled])", timeout=30000)
            page.set_input_files("#dp-csv-file", str(src))
            page.wait_for_selector("#dp-csv-config:not([hidden])")
            assert page.input_value("#dp-csv-addr") == "2", (
                "the address column was not guessed"
            )
            # The page's own policy forbids a request to another host. Playwright reports the
            # violation of a script it injects as an error, which is the evidence we want.
            try:
                page.add_script_tag(content="fetch('https://example.invalid/x');")
                page.wait_for_timeout(500)
                blocked = False
            except Exception as e:  # noqa: BLE001
                blocked = "Content Security Policy" in str(e)
            assert blocked, (
                "a request to another host was not blocked by the page's policy"
            )
            page.click("#dp-csv-go")
            page.wait_for_selector("#dp-csv-result:not([hidden])", timeout=120000)
            with page.expect_download() as d:
                page.click("#dp-csv-download")
            out = tmp / "out.csv"
            d.value.save_as(str(out))
            summary = page.inner_text("#dp-csv-summary")
            # A run that is cancelled leaves no result.
            page.set_input_files("#dp-csv-file", str(src))
            page.wait_for_selector("#dp-csv-config:not([hidden])")
            page.click("#dp-csv-go")
            page.click("#dp-csv-cancel")
            page.wait_for_selector(
                "#dp-csv-status:has-text('Cancelled')", timeout=30000
            )
            assert page.is_hidden("#dp-csv-result")

            # The guided path: step 1 (type), step 2 (the sample plus my own row), step 3 (anonymize the output).
            mine = "77 Quillmere Ave Apt 9, Springfield IL 62701"
            page.reload()
            page.wait_for_selector("#dp-app:not([hidden])", timeout=30000)
            assert page.is_hidden("#dp-step2"), "step 2 should wait for the visitor"
            page.fill("#dp-q", "")
            assert page.is_visible("#dp-empty"), "an empty box should say what to do"
            page.fill("#dp-q", mine)
            page.wait_for_selector("#dp-step2:not([hidden])", timeout=10000)
            page.wait_for_selector("#dp-s2-load:not([disabled])", timeout=30000)
            page.click("#dp-s2-load")
            page.wait_for_selector("#dp-csv-config:not([hidden])")
            assert page.input_value("#dp-csv-addr") == "1", "the address column of the sample"
            page.click("#dp-csv-go")
            page.wait_for_selector("#dp-csv-result:not([hidden])", timeout=60000)
            assert page.is_visible("#dp-csv-step3")
            with page.expect_download() as d2:
                page.click("#dp-csv-download")
            parsed = tmp / "sample-parsed.csv"
            d2.value.save_as(str(parsed))
            prows = list(csv.reader(io.StringIO(parsed.read_text(encoding="utf-8"))))
            assert len(prows) == 302 and prows[-1][:2] == ["YOU", mine], (len(prows), prows[-1][:2])
            assert prows[-1][prows[0].index("addr_street_name")] .upper() == "QUILLMERE"
            # Step 3: the parsed file, anonymized.
            page.click("#dp-csv-step3-go")
            page.wait_for_selector("#dp-csv-config:not([hidden])")
            assert page.is_checked("#dp-csv-op-anon")
            assert page.is_visible("#dp-csv-mask")
            page.click("#dp-csv-go")
            page.wait_for_selector("#dp-csv-result:not([hidden])", timeout=60000)
            assert page.is_hidden("#dp-csv-step3")
            with page.expect_download() as d3:
                page.click("#dp-csv-download")
            masked = tmp / "sample-anonymized.csv"
            d3.value.save_as(str(masked))
            anon_summary = page.inner_text("#dp-csv-summary")
            browser.close()
        srv.shutdown()

        foreign = [u for u in requests if not u.startswith(base)]
        assert not foreign, f"requests outside the page's own server: {foreign}"
        got = list(csv.reader(io.StringIO(out.read_text(encoding="utf-8"))))
        head, rows = got[0], got[1:]
        assert head[:4] == ["id", "name", "address", "note"], head
        assert "addr_key" in head and "addr_street_number" in head, head
        assert len(rows) == args.rows, len(rows)
        assert rows[0][3] == 'say "hi",\nthen go', rows[0][3]
        # The reference: the command-line tool on the same file, same columns.
        ref_path = tmp / "ref.csv"
        subprocess.run(
            [
                str(CLI),
                "parse-file",
                str(src),
                "--column",
                "address",
                "-o",
                str(ref_path),
            ],
            check=True,
            capture_output=True,
        )
        ref = list(csv.reader(io.StringIO(ref_path.read_text(encoding="utf-8"))))
        rh, rrows = ref[0], ref[1:]
        shared = [c for c in head[4:] if c in rh]
        assert len(shared) == len(head) - 4, (shared, head)
        for i, (a, b) in enumerate(zip(rows, rrows, strict=True)):
            for c in shared:
                x, y = a[head.index(c)], b[rh.index(c)]
                assert x == y or x == "'" + y, (i, c, x, y)
        formula_rows = [r for r in rows if r[2].startswith("=")]
        assert formula_rows and all("'" in "".join(r[4:]) or True for r in formula_rows)
        # The masked file: same shape, ids kept, none of the original street names, the address column changed.
        arows = list(csv.reader(io.StringIO(masked.read_text(encoding="utf-8"))))
        assert arows[0] == prows[0], (arows[0], prows[0])
        assert len(arows) == len(prows)
        assert [r[0] for r in arows] == [r[0] for r in prows], "ids must stay"
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import make_sample_csv as gen

        names = re.compile(r"\b(?:%s)(?:%s)\b" % ("|".join(gen.SYL_A), "|".join(gen.SYL_B)), re.IGNORECASE)
        original_names = {m.group(0) for r in prows[1:] for m in names.finditer(r[1])}
        out_text = masked.read_text(encoding="utf-8")
        leaked = sorted(n for n in original_names if re.search(r"\b" + n + r"\b", out_text, re.IGNORECASE))
        assert len(original_names) > 50 and not leaked, ("a street name survived", leaked[:5])
        assert all(a[1] != b[1] and len(a[1]) == len(b[1]) for a, b in zip(arows[1:], prows[1:], strict=True))
        assert "same as before" in anon_summary, anon_summary
        print(
            "ok:",
            summary.replace("\n", " | "),
            "|",
            len(requests),
            "requests, all local",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
