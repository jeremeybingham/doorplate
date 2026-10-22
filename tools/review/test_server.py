"""Tests for tools/review/server.py on invented rows (no private data).

    pytest tools/review
"""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import server  # noqa: E402

QUEUE = [
    {"seq": 1, "id": "inv|site|1", "source": "inv", "role": "site", "record_id": "1", "line1": "123 456 QUINCEWOOD ST",
     "city": "MIAMI", "state": "FL", "zip": "33101", "cluster": {"shape": "9 9 a a", "warnings": "multiple_addresses", "size": 3}},
    {"seq": 2, "id": "inv|site|2", "source": "inv", "role": "site", "record_id": "2", "line1": "5 OAK AVE", "line2": "BLDG",
     "cluster": {"shape": "9 a a | a", "warnings": "missing_unit_number", "size": 1}},
]


@pytest.fixture
def review(tmp_path):
    q = tmp_path / "queue.jsonl"
    q.write_text("".join(json.dumps(e) + "\n" for e in QUEUE))
    return server.Review(q, tmp_path / "answers.jsonl")


def test_next_stats_and_resume(review, tmp_path):
    assert review.next_item()["id"] == "inv|site|1"
    review.answer({"id": "inv|site|1", "verdict": "right"})
    assert review.next_item()["id"] == "inv|site|2"
    assert review.stats() == {"total": 2, "answered": 1, "by_verdict": {"right": 1}}
    # a new session over the same files resumes where the last one stopped
    again = server.Review(tmp_path / "queue.jsonl", tmp_path / "answers.jsonl")
    assert again.next_item()["id"] == "inv|site|2"


def test_a_corrected_answer_needs_the_string_and_keeps_the_page_parses(review):
    with pytest.raises(ValueError):
        review.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": "  "})
    rec = review.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": " 123 QUINCEWOOD ST, MIAMI FL 33101 ",
                         "parse": {"key": "k2:old"}, "corrected_parse": {"key": "k2:new"}, "note": " the number twice "})
    assert rec["corrected"] == "123 QUINCEWOOD ST, MIAMI FL 33101"
    assert rec["parse"] == {"key": "k2:old"} and rec["corrected_parse"] == {"key": "k2:new"}
    assert rec["note"] == "the number twice"
    assert rec["input"]["line1"] == "123 456 QUINCEWOOD ST" and rec["cluster"]["size"] == 3


def test_bad_requests_are_refused(review):
    for body in ({"id": "nope", "verdict": "right"}, {"id": "inv|site|1", "verdict": "maybe"}, {}):
        with pytest.raises(ValueError):
            review.answer(body)
    assert not review.answers_path.exists()


def test_undo_appends_a_marker_and_never_rewrites(review):
    review.answer({"id": "inv|site|1", "verdict": "junk"})
    review.answer({"id": "inv|site|2", "verdict": "skip"})
    assert review.undo() == "inv|site|2"
    assert review.next_item()["id"] == "inv|site|2"
    lines = review.answers_path.read_text().splitlines()
    assert len(lines) == 3 and json.loads(lines[2])["undo"] == "inv|site|2"
    assert review.stats()["answered"] == 1
    # an answer given again after an undo is the standing one
    review.answer({"id": "inv|site|2", "verdict": "noise"})
    assert server.load_answers(review.answers_path)["inv|site|2"]["verdict"] == "noise"


@pytest.fixture
def http(review, tmp_path):
    wasm = tmp_path / "doorplate.wasm"
    wasm.write_bytes(b"\0asm\1\0\0\0")
    httpd = server.serve(review, wasm, 0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}))


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req)


def test_http_flow(http):
    assert b"doorplate review" in get(http + "/").read()
    assert get(http + "/doorplate.wasm").headers["Content-Type"] == "application/wasm"
    j = json.load(get(http + "/api/next"))
    assert j["item"]["id"] == "inv|site|1" and j["stats"]["total"] == 2
    j = json.load(post(http + "/api/answer", {"id": "inv|site|1", "verdict": "right"}))
    assert j["stats"]["answered"] == 1
    assert json.load(get(http + "/api/next"))["item"]["id"] == "inv|site|2"
    assert json.load(post(http + "/api/undo", {}))["undone"] == "inv|site|1"
    with pytest.raises(urllib.error.HTTPError) as e:
        post(http + "/api/answer", {"id": "inv|site|1", "verdict": "bogus"})
    assert e.value.code == 400


def test_a_request_for_another_host_is_refused(http):
    with pytest.raises(urllib.error.HTTPError) as e:
        get(http + "/api/next", {"Host": "evil.example"})
    assert e.value.code == 403
