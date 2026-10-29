#!/usr/bin/env python3
"""The review server: shows one hard address at a time and records what a person says (#122).

    python tools/review/server.py [QUEUE.jsonl] [--answers local-data/review/answers.jsonl]
                                  [--wasm PATH] [--port 8765]

Run `tools/review/sample.py` first. Open the printed address (127.0.0.1 only) in a browser.
For each row the page shows the parse and the warnings, and you choose a verdict:

- `right`: the parse is correct. A second answer says whether the warning was `fair` (it
  rightly flags something doubtful, such as a true range of house numbers) or `noise` (the
  parse is fine and there is nothing to flag);
- `corrected`: wrong, and here is a string that should parse to the same door (typed in the
  box, which starts as the original joined into one line, and re-parsed as you type);
- `unclear`: wrong, and I can't tell what it should be;
- `junk`: not an address (a name, a placeholder, a phone number);
- `dual`: the row holds a dual or multiple address (a street and a PO Box, or several), which is not the same signal as `junk`;
- `noise`: the source cut it off or mangled it;
- `skip`: not now;
- `labeled`: the parts of the one-line string, marked by the person (`labels`: `[{start, end, component}]` over
  `labeled_text`), a more exact answer than a rewrite when the parse is wrong in a few places.

Whatever the verdict, text left in the correction box that differs from the original is kept as `draft` (with
`draft_parse`): an attempt at a fix on a row you could not fix ("I can't tell"), or on a row where you judged
usaddress right but had typed a better string. It is not a correction and is never scored as one; the note is
always kept.

A correction whose string is the unchanged one-line original is refused (it almost always means "the
parse is right"; send `unchanged_ok` to keep it). The page asks first.

A comparison queue (`tools/review/compare_sample.py`, issue #132) shows doorplate's parse beside
usaddress's, and the verdicts are `doorplate_right`, `usaddress_right`, `both_right` (a different
convention, both fine), `both_wrong` (with a corrected string, as for `corrected`), and the
`unclear`, `junk`, `dual`, `noise` and `skip` above. `usaddress_right` can also carry a corrected string (the button
"usaddress right + save correction", key `0`): usaddress's reading was right and there is a better string for doorplate; it is kept as
`corrected` and the verdict is still scored as `usaddress_right`.

Every answer is appended to the answers file, one JSON object per line; an undo appends a
marker, so the file is never rewritten. Answers already given are not shown again, so a session
can stop and resume. The parser is the doorplate WebAssembly build (`cargo build -p doorplate-wasm
--target wasm32-unknown-unknown --release`), run by the page: the server needs only the standard
library and sends nothing anywhere.

The queue and the answers hold real addresses and stay in `local-data/` (docs/data-policy.md).
`tools/review/export.py` writes the shape-only version that may be shared.
This library formats and parses; it does not validate that an address exists or can receive mail.
"""
import argparse
import json
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # `python -I` leaves the script folder off the path

from oneline import one_line  # noqa: E402
ROOT = HERE.parents[1]
DEFAULT_QUEUE = ROOT / "local-data" / "review" / "queue.jsonl"
DEFAULT_ANSWERS = ROOT / "local-data" / "review" / "answers.jsonl"
DEFAULT_WASM = ROOT / "target" / "wasm32-unknown-unknown" / "release" / "doorplate_wasm.wasm"
BUILD_WASM = "cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release"
# What the WebAssembly build is made from: a file here newer than the build means the page parses with an older parser (#246).
SOURCES = (ROOT / "crates" / "doorplate" / "src", ROOT / "crates" / "doorplate" / "data", ROOT / "crates" / "doorplate-wasm" / "src",
           ROOT / "crates" / "doorplate" / "Cargo.toml", ROOT / "crates" / "doorplate-wasm" / "Cargo.toml")
VERDICTS = ("right", "corrected", "unclear", "junk", "dual", "noise", "skip", "labeled")
COMPONENTS = ("StreetNumber", "StreetDirPrefix", "StreetName", "StreetSuffix", "StreetDirSuffix", "Highway", "UnitType",
              "UnitNumber", "SecondUnitType", "SecondUnitNumber", "PoBox", "RuralRoute", "GeneralDelivery", "Military",
              "MilitaryPostOffice", "Attention", "Building", "City", "State", "Zip5", "Zip4", "Unparsed")  # the page's names
MAX_LABELS = 200
COMPARE_VERDICTS = ("doorplate_right", "usaddress_right", "both_right", "both_wrong")  # for a comparison row
WARNING_VERDICTS = ("fair", "noise")  # for a `right` parse: was the warning justified?
MAX_BODY = 64 * 1024
INPUT_KEYS = ("line1", "line2", "city", "state", "zip", "last_line", "provider")


def read_jsonl(path):
    if not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def load_answers(path):
    """The standing answers, by queue id, in the order given. An undo marker removes the latest
    answer for its id."""
    answers = {}
    for a in read_jsonl(path):
        if a.get("undo"):
            answers.pop(a["undo"], None)
        else:
            answers.pop(a["id"], None)
            answers[a["id"]] = a
    return answers


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def wasm_status(wasm_path, sources=SOURCES):
    """Is the parser build older than the source it is built from? (#246: the page once ran a build five days and many
    rules behind, and nothing said so.) By modification time: the newest file under `sources` against the build."""
    built = Path(wasm_path).stat().st_mtime
    newest, newest_file = 0.0, None
    for src in sources:
        for f in ([src] if src.is_file() else src.rglob("*") if src.is_dir() else []):
            if f.is_file() and f.stat().st_mtime > newest:
                newest, newest_file = f.stat().st_mtime, f
    stale = newest > built
    return {"stale": stale, "wasm_built": _iso(built), "source_newest": _iso(newest) if newest_file else None,
            "build": BUILD_WASM,
            "message": (f"The parser on this page was built {_iso(built)}, before the source changed ({_iso(newest)}). "
                        f"Rebuild it: {BUILD_WASM}") if stale else ""}


class Review:
    """The queue, the answers file and the rules for one answer. No HTTP in here, so it is testable."""

    def __init__(self, queue, answers_path):
        self.queue = read_jsonl(queue)
        self.answers_path = Path(answers_path)
        self.lock = threading.Lock()

    def stats(self):
        answered = load_answers(self.answers_path)
        by = {}
        for a in answered.values():
            by[a["verdict"]] = by.get(a["verdict"], 0) + 1
        ids = {e["id"] for e in self.queue}
        done = sum(1 for i in answered if i in ids)
        return {"total": len(self.queue), "answered": done, "by_verdict": by}

    def next_item(self):
        answered = load_answers(self.answers_path)
        for e in self.queue:
            if e["id"] not in answered:
                return e
        return None

    def answer(self, body):
        """Validate and append one answer. Raises ValueError on a bad request."""
        by_id = {e["id"]: e for e in self.queue}
        item = by_id.get(body.get("id"))
        if item is None:
            raise ValueError("unknown id")
        verdict = body.get("verdict")
        if verdict in COMPARE_VERDICTS:
            if "compare" not in item:
                raise ValueError("that verdict is for a comparison row")
        elif verdict not in VERDICTS or (verdict in ("right", "corrected") and "compare" in item):
            raise ValueError("unknown verdict")
        warning = body.get("warning")
        if verdict == "right" and warning not in WARNING_VERDICTS:
            raise ValueError("a right parse needs a warning verdict: fair or noise")
        corrected = (body.get("corrected") or "").strip()
        # usaddress was right and there is also a better string for doorplate: the verdict stays `usaddress_right`
        # (so it is scored as before) and the correction is kept as for the verdicts that are corrections.
        with_corr = verdict == "usaddress_right" and bool(corrected)
        if verdict in ("corrected", "both_wrong") and not corrected:
            raise ValueError("a corrected answer needs the corrected string")
        if (verdict in ("corrected", "both_wrong") or with_corr) and not body.get("unchanged_ok") and \
                " ".join(corrected.split()) == " ".join(one_line(item).split()):
            raise ValueError("the correction is the unchanged original: if the parse is right, answer that; "
                             "otherwise confirm with unchanged_ok")
        labels = None
        if verdict == "labeled":
            labels = self._labels(body)
        rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "id": item["id"],
               "seq": item["seq"], "source": item["source"], "role": item["role"],
               "input": {k: item[k] for k in INPUT_KEYS if k in item}, "cluster": item.get("cluster"),
               "verdict": verdict, "note": (body.get("note") or "").strip()[:2000]}
        if verdict == "right":
            rec["warning"] = warning
        if "compare" in item:
            rec["compare"] = item["compare"]
        if verdict in ("corrected", "both_wrong") or with_corr:
            rec["corrected"] = corrected[:1000]
        if labels is not None:
            rec["labeled_text"], rec["labels"] = labels
        draft = body.get("draft")
        draft = draft.strip() if isinstance(draft, str) else ""
        if verdict not in ("corrected", "both_wrong") and not with_corr and draft and \
                " ".join(draft.split()) != " ".join(one_line(item).split()):
            rec["draft"] = draft[:1000]  # an attempted fix under a verdict that is not a correction
        for k in ("parse", "corrected_parse", "draft_parse"):  # summaries the page computed with the same parser
            v = body.get(k)
            if isinstance(v, dict) and len(json.dumps(v)) <= 20000 and (k != "draft_parse" or "draft" in rec):
                rec[k] = v
        self._append(rec)
        return rec

    @staticmethod
    def _labels(body):
        """(text, labels) from a `labeled` answer, checked: spans inside the text, in order, not overlapping."""
        text = body.get("labeled_text")
        labels = body.get("labels")
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise ValueError("a labeled answer needs labeled_text")
        if not isinstance(labels, list) or not labels or len(labels) > MAX_LABELS:
            raise ValueError("a labeled answer needs labels")
        out, end = [], 0
        for lab in labels:
            if not isinstance(lab, dict):
                raise ValueError("a label is {start, end, component}")
            s, e, c = lab.get("start"), lab.get("end"), lab.get("component")
            if not (isinstance(s, int) and isinstance(e, int) and not isinstance(s, bool) and not isinstance(e, bool)):
                raise ValueError("a label start and end are integers")
            if c not in COMPONENTS:
                raise ValueError(f"unknown component {c!r}")
            if not (end <= s < e <= len(text)):
                raise ValueError("labels must lie inside the text, in order, without overlapping")
            out.append({"start": s, "end": e, "component": c})
            end = e
        return text, out

    def undo(self):
        """Take back the latest standing answer. Returns its id, or None."""
        with self.lock:
            answered = load_answers(self.answers_path)
            if not answered:
                return None
            last = list(answered)[-1]
            self._write({"undo": last, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")})
            return last

    def _append(self, rec):
        with self.lock:
            self._write(rec)

    def _write(self, rec):
        self.answers_path.parent.mkdir(parents=True, exist_ok=True)
        with self.answers_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def make_handler(review, wasm_path):
    page = (HERE / "page.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        server_version = "doorplate-review"

        def log_message(self, *a):  # no request log: paths and bodies hold addresses
            pass

        def _send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _local(self):
            # Only a page loaded from this machine may talk to the server (DNS rebinding).
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            if host not in ("127.0.0.1", "localhost", "::1"):
                self._send(403, {"error": "forbidden"})
                return False
            return True

        def do_GET(self):
            if not self._local():
                return
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            elif path == "/helpers.js":
                self._send(200, (HERE / "helpers.js").read_bytes(), "text/javascript; charset=utf-8")
            elif path == "/doorplate.wasm":
                if not Path(wasm_path).exists():
                    self._send(404, {"error": f"build the parser first: {BUILD_WASM}"})
                else:
                    self._send(200, Path(wasm_path).read_bytes(), "application/wasm")
            elif path == "/api/next":
                self._send(200, {"item": review.next_item(), "stats": review.stats()})
            elif path == "/api/stats":
                self._send(200, review.stats())
            elif path == "/api/status":
                self._send(200, wasm_status(wasm_path) if Path(wasm_path).exists() else {"stale": True, "message": f"Build the parser: {BUILD_WASM}"})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._local():
                return
            path = self.path.split("?")[0]
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    raise ValueError("body too large")
                body = json.loads(self.rfile.read(n) or b"{}")
                if path == "/api/answer":
                    review.answer(body)
                    self._send(200, {"ok": True, "stats": review.stats()})
                elif path == "/api/undo":
                    self._send(200, {"undone": review.undo(), "stats": review.stats()})
                else:
                    self._send(404, {"error": "not found"})
            except (ValueError, json.JSONDecodeError) as e:
                self._send(400, {"error": str(e)})

    return Handler


def serve(review, wasm_path, port):
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(review, wasm_path))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("queue", nargs="?", type=Path, default=DEFAULT_QUEUE)
    ap.add_argument("--answers", type=Path, default=DEFAULT_ANSWERS)
    ap.add_argument("--wasm", type=Path, default=DEFAULT_WASM)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="open the page in the default browser")
    ap.add_argument("--strict", action="store_true", help="refuse to start when the parser build is older than the source")
    args = ap.parse_args(argv)
    if not args.queue.exists():
        sys.exit(f"no queue at {args.queue}; build one with tools/review/sample.py RUN --confirm")
    if not args.wasm.exists():
        sys.exit(f"{args.wasm} is missing; build the parser first:\n  {BUILD_WASM}")
    status = wasm_status(args.wasm)
    if status["stale"]:
        print(f"WARNING: {status['message']}", file=sys.stderr)
        if args.strict:
            sys.exit("refusing to start with --strict")
    review = Review(args.queue, args.answers)
    s = review.stats()
    httpd = serve(review, args.wasm, args.port)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"{s['answered']} of {s['total']} answered; answers go to {args.answers}")
    print(f"open {url}   (Ctrl-C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
