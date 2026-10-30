"""Tests for tools/review/server.py on invented rows (no private data).

    pytest tools/review
"""
import json
import os
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
    review.answer({"id": "inv|site|1", "verdict": "right", "warning": "fair"})
    assert review.next_item()["id"] == "inv|site|2"
    assert review.stats() == {"total": 2, "answered": 1, "by_verdict": {"right": 1}}
    # a new session over the same files resumes where the last one stopped
    again = server.Review(tmp_path / "queue.jsonl", tmp_path / "answers.jsonl")
    assert again.next_item()["id"] == "inv|site|2"


def test_a_corrected_answer_needs_the_string_and_keeps_the_page_parses(review):
    with pytest.raises(ValueError):
        review.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": "  "})
    rec = review.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": " 123 QUINCEWOOD ST, MIAMI FL 33101 ",
                         "parse": {"key": "k3:old"}, "corrected_parse": {"key": "k3:new"}, "note": " the number twice "})
    assert rec["corrected"] == "123 QUINCEWOOD ST, MIAMI FL 33101"
    assert rec["parse"] == {"key": "k3:old"} and rec["corrected_parse"] == {"key": "k3:new"}
    assert rec["note"] == "the number twice"
    assert rec["input"]["line1"] == "123 456 QUINCEWOOD ST" and rec["cluster"]["size"] == 3


def test_a_right_parse_says_whether_the_warning_was_fair(review):
    # the parse and the warning are separate judgments: both must be given
    for body in ({"id": "inv|site|1", "verdict": "right"}, {"id": "inv|site|1", "verdict": "right", "warning": "maybe"}):
        with pytest.raises(ValueError):
            review.answer(body)
    assert review.answer({"id": "inv|site|1", "verdict": "right", "warning": "fair"})["warning"] == "fair"
    assert review.answer({"id": "inv|site|2", "verdict": "right", "warning": "noise"})["warning"] == "noise"
    # other verdicts carry no warning verdict
    assert "warning" not in review.answer({"id": "inv|site|2", "verdict": "junk", "warning": "noise"})


def test_a_dual_address_is_its_own_verdict(review):
    assert review.answer({"id": "inv|site|1", "verdict": "dual", "note": "street and PO Box"})["verdict"] == "dual"


def test_text_left_in_the_correction_box_is_kept_as_a_draft_under_any_other_verdict(review):
    # "I can't tell" with an attempt in the box: the note and the attempt are both recorded, and it is not a correction
    rec = review.answer({"id": "inv|site|1", "verdict": "unclear", "note": " still bad ", "draft": " 123 QUINCEWOOD ST ",
                         "parse": {"key": "k3:old"}, "draft_parse": {"key": "k3:draft"}})
    assert rec["verdict"] == "unclear" and rec["note"] == "still bad"
    assert rec["draft"] == "123 QUINCEWOOD ST" and rec["draft_parse"] == {"key": "k3:draft"} and "corrected" not in rec
    # a draft equal to the original is not an attempt; nor is blank text; and a draft_parse never arrives alone
    rec = review.answer({"id": "inv|site|2", "verdict": "junk", "draft": "5  OAK AVE, BLDG", "draft_parse": {"key": "k3:x"}})
    assert "draft" not in rec and "draft_parse" not in rec
    assert "draft" not in review.answer({"id": "inv|site|2", "verdict": "skip", "draft": "   "})


def test_a_comparison_verdict_keeps_the_note_and_the_draft(tmp_path):
    q = tmp_path / "q.jsonl"
    row = dict(QUEUE[0], compare={"class": "silent", "differs": [["StreetName", "OccupancyIdentifier", 1]], "usaddress": []})
    q.write_text(json.dumps(row) + "\n")
    r = server.Review(q, tmp_path / "a.jsonl")
    rec = r.answer({"id": "inv|site|1", "verdict": "usaddress_right", "note": "they read the unit", "draft": "123 QUINCEWOOD ST APT 456"})
    assert rec["verdict"] == "usaddress_right" and rec["note"] == "they read the unit"
    assert rec["draft"] == "123 QUINCEWOOD ST APT 456" and "corrected" not in rec


def test_usaddress_right_can_carry_a_correction(tmp_path):
    q = tmp_path / "q.jsonl"
    row = dict(QUEUE[0], compare={"class": "silent", "differs": [["StreetName", "OccupancyIdentifier", 1]], "usaddress": []})
    q.write_text(json.dumps(row) + "\n")
    r = server.Review(q, tmp_path / "a.jsonl")
    # the unchanged original is not a correction
    with pytest.raises(ValueError):
        r.answer({"id": "inv|site|1", "verdict": "usaddress_right", "corrected": "123 456 QUINCEWOOD ST, MIAMI, FL 33101"})
    rec = r.answer({"id": "inv|site|1", "verdict": "usaddress_right", "corrected": "123 QUINCEWOOD ST APT 456", "draft": "ignored",
                    "corrected_parse": {"key": "k3:x"}})
    assert rec["verdict"] == "usaddress_right" and rec["corrected"] == "123 QUINCEWOOD ST APT 456"
    assert "draft" not in rec and rec["corrected_parse"] == {"key": "k3:x"}


def test_a_correction_verdict_ignores_a_draft_field(review):
    rec = review.answer({"id": "inv|site|1", "verdict": "corrected", "corrected": "123 QUINCEWOOD ST", "draft": "something else"})
    assert rec["corrected"] == "123 QUINCEWOOD ST" and "draft" not in rec


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
    j = json.load(post(http + "/api/answer", {"id": "inv|site|1", "verdict": "right", "warning": "noise"}))
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


def test_a_parser_build_older_than_the_source_is_stale(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "lib.rs").write_text("// invented")
    wasm = tmp_path / "doorplate.wasm"
    wasm.write_bytes(b"\0asm")
    os.utime(src / "lib.rs", (1_000_000, 1_000_000))
    os.utime(wasm, (2_000_000, 2_000_000))
    ok = server.wasm_status(wasm, sources=(src,))
    assert not ok["stale"] and ok["message"] == ""
    os.utime(src / "lib.rs", (3_000_000, 3_000_000))  # the source changed after the build
    old = server.wasm_status(wasm, sources=(src,))
    assert old["stale"] and "Rebuild it" in old["message"] and server.BUILD_WASM in old["message"]
    assert not server.wasm_status(wasm, sources=(tmp_path / "missing",))["stale"]  # no source to compare with


def test_strict_refuses_to_start_with_a_stale_build(tmp_path, monkeypatch, capsys):
    q = tmp_path / "queue.jsonl"
    q.write_text(json.dumps(QUEUE[0]) + "\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.rs").write_text("// invented")
    wasm = tmp_path / "doorplate.wasm"
    wasm.write_bytes(b"\0asm")
    os.utime(wasm, (1_000_000, 1_000_000))
    monkeypatch.setattr(server, "SOURCES", (src,))
    monkeypatch.setattr(server.wasm_status, "__defaults__", ((src,),))
    with pytest.raises(SystemExit) as e:
        server.main([str(q), "--answers", str(tmp_path / "a.jsonl"), "--wasm", str(wasm), "--strict"])
    assert "strict" in str(e.value)
    assert "WARNING" in capsys.readouterr().err


def test_the_status_endpoint_reports_a_fresh_build(http):
    j = json.load(get(http + "/api/status"))
    assert "stale" in j and "message" in j


def test_not_enough_for_a_door_is_its_own_verdict(review):
    rec = review.answer({"id": "inv|site|1", "verdict": "insufficient", "note": "map shows a different street"})
    assert rec["verdict"] == "insufficient" and rec["note"] == "map shows a different street"
