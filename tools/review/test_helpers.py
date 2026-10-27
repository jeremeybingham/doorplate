"""Tests for the review page's helpers (#222): tools/review/helpers.js under Node, the server rules for the
new answers, and their exports. Invented rows. The JS tests are skipped when Node is not installed.

    pytest tools/review
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import export  # noqa: E402
import full  # noqa: E402
import server  # noqa: E402
from oneline import one_line  # noqa: E402

node = pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")

ROWS = [
    {"line1": "ZEPHYR HOLDINGS LLC 20 OAK ST", "line2": "% PAT QUINCE", "city": "MIAMI", "state": "FL", "zip": "33101"},
    {"line1": "ZEPHYR HOLDINGS LLC 20 OAK ST", "city": "MIAMI", "state": "FL", "zip": "33101"},
    {"line1": "ZEPHYR HOLDINGS LLC 20 OAK ST", "line2": "STE 4", "city": "MIAMI", "state": "FL", "zip": "33101"},
    {"line1": "5 ELM AVE", "line2": "BLDG 2", "last_line": "TAMPA FL 33601"},
    {"line1": "ONLY", "city": "MIAMI"},
]


def js(expr):
    code = ("const H = require(%s); console.log(JSON.stringify(%s));" % (json.dumps(str(HERE / "helpers.js")), expr))
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@node
def test_one_line_matches_the_python_one():
    for r in ROWS:
        assert js(f"H.oneLine({json.dumps(r)})") == one_line(r)


@node
def test_moving_words_to_the_care_of_line():
    r0, r1, r2 = ROWS[0], ROWS[1], ROWS[2]
    # a care-of line exists: the words are appended to it
    assert js(f"H.moveWords({json.dumps(r0)}, 3)") == "20 OAK ST, % PAT QUINCE ZEPHYR HOLDINGS LLC, MIAMI, FL 33101"
    # none: a new `% WORDS` line after line 1
    assert js(f"H.moveWords({json.dumps(r1)}, 3)") == "20 OAK ST, % ZEPHYR HOLDINGS LLC, MIAMI, FL 33101"
    # line 2 is a unit: the care-of part goes between line 1 and it
    assert js(f"H.moveWords({json.dumps(r2)}, 3)") == "20 OAK ST, % ZEPHYR HOLDINGS LLC, STE 4, MIAMI, FL 33101"
    # zero words changes nothing; too many keeps one word on line 1; a one-word line has nothing to move
    assert js(f"H.moveWords({json.dumps(r1)}, 0)") == one_line(r1)
    assert js(f"H.moveWords({json.dumps(r1)}, 99)") == "ST, % ZEPHYR HOLDINGS LLC 20 OAK, MIAMI, FL 33101"
    assert js(f"H.moveWords({json.dumps(ROWS[4])}, 2)") == "ONLY, MIAMI"


@node
def test_unchanged_ignores_spacing_only():
    r = ROWS[0]
    assert js(f"H.unchanged({json.dumps(r)}, {json.dumps(one_line(r) + '  ')})") is True
    assert js(f"H.unchanged({json.dumps(r)}, {json.dumps(one_line(r).replace(', ', ',  '))})") is True
    assert js(f"H.unchanged({json.dumps(r)}, 'something else')") is False


@node
def test_tokens_runs_and_labels_from_spans():
    assert js("H.tokens('20 OAK ST, MIAMI')") == [
        {"start": 0, "end": 2, "text": "20"}, {"start": 3, "end": 6, "text": "OAK"},
        {"start": 7, "end": 10, "text": "ST,"}, {"start": 11, "end": 16, "text": "MIAMI"}]
    spans = [{"start": 0, "end": 2, "component": "StreetNumber"}, {"start": 3, "end": 10, "component": "StreetName"}]
    labs = js(f"H.labelsFromSpans('20 OAK ST, MIAMI', {json.dumps(spans)})")
    assert [l["component"] for l in labs] == ["StreetNumber", "StreetName", "StreetName", "Unparsed"]
    runs = js(f"H.runs(H.labelsFromSpans('20 OAK ST, MIAMI', {json.dumps(spans)}))")
    assert runs == [{"start": 0, "end": 2, "component": "StreetNumber"}, {"start": 3, "end": 10, "component": "StreetName"},
                    {"start": 11, "end": 16, "component": "Unparsed"}]


QUEUE = [{"seq": 1, "id": "inv|site|1", "source": "inv", "role": "site", "record_id": "1", **ROWS[0],
          "cluster": {"shape": "a a a 9 a a", "warnings": "missing_street_number", "size": 3}}]


def review_of(tmp_path):
    q = tmp_path / "q.jsonl"
    q.write_text("".join(json.dumps(e) + "\n" for e in QUEUE))
    return server.Review(q, tmp_path / "a.jsonl")


def test_an_unchanged_correction_is_refused_unless_confirmed(tmp_path):
    r = review_of(tmp_path)
    same = one_line(ROWS[0])
    with pytest.raises(ValueError, match="unchanged"):
        r.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": same})
    with pytest.raises(ValueError, match="unchanged"):
        r.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": "  " + same.replace(", ", ",  ")})
    rec = r.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": same, "unchanged_ok": True})
    assert rec["corrected"] == same
    r.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": "20 OAK ST, % PAT QUINCE ZEPHYR HOLDINGS LLC, MIAMI, FL 33101"})


GOOD = {"id": "inv|site|1", "verdict": "labeled", "labeled_text": "20 OAK ST",
        "labels": [{"start": 0, "end": 2, "component": "StreetNumber"}, {"start": 3, "end": 6, "component": "StreetName"},
                   {"start": 7, "end": 9, "component": "StreetSuffix"}]}


def test_a_labeled_answer_is_checked_and_recorded(tmp_path):
    r = review_of(tmp_path)
    rec = r.answer(dict(GOOD, note="n"))
    assert rec["verdict"] == "labeled" and rec["labeled_text"] == "20 OAK ST" and len(rec["labels"]) == 3
    bad = [dict(GOOD, labels=[]), dict(GOOD, labeled_text=""), dict(GOOD, labels=[{"start": 0, "end": 99, "component": "City"}]),
           dict(GOOD, labels=[{"start": 3, "end": 6, "component": "City"}, {"start": 0, "end": 2, "component": "City"}]),
           dict(GOOD, labels=[{"start": 0, "end": 4, "component": "City"}, {"start": 3, "end": 6, "component": "City"}]),
           dict(GOOD, labels=[{"start": 0, "end": 2, "component": "NotAPart"}]),
           dict(GOOD, labels=[{"start": "0", "end": 2, "component": "City"}]), dict(GOOD, labels=["x"])]
    for b in bad:
        with pytest.raises(ValueError):
            r.answer(b)


def test_the_labeled_answer_exports_parts_and_shapes_never_words(tmp_path):
    r = review_of(tmp_path)
    r.answer(dict(GOOD, labeled_text="20 OAK ST"))
    a = list(server.load_answers(tmp_path / "a.jsonl").values())[0]
    out = export.safe(a)
    assert out["labels"] == [["StreetNumber", "9"], ["StreetName", "a"], ["StreetSuffix", "a"]]
    assert "OAK" not in json.dumps(out)
    # a hand-edited answer cannot put a word through the component name: only the page's parts pass
    for word in ("OAK", "12 Oak St"):
        a["labels"][0]["component"] = word
        assert len(export.safe(a)["labels"]) == 2 and word not in json.dumps(export.safe(a))


def test_the_full_text_export_shows_the_labels_with_masking(tmp_path):
    r = review_of(tmp_path)
    r.answer(dict(GOOD, labeled_text="20 OAK ST"))
    a = list(server.load_answers(tmp_path / "a.jsonl").values())[0]
    text = full.entry(1, a, set())
    assert "labeled: StreetNumber='20'; StreetName='OAK'; StreetSuffix='ST'" in text


def test_the_server_serves_the_helpers(tmp_path):
    import threading
    import urllib.request

    httpd = server.serve(review_of(tmp_path), tmp_path / "x.wasm", 0)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/helpers.js").read().decode()
        assert "moveWords" in body
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert '<script src="/helpers.js">' in page
    finally:
        httpd.shutdown()
