"""Tests for tools/review/export.py: nothing but shapes may come out (invented rows).

    pytest tools/review
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import export  # noqa: E402

SECRETS = ("QUINCEWOOD", "SMITH", "JOHN", "MIAMI", "33101", "10:11", "12+00", "inv")

ANSWER = {
    "ts": "2026-10-22T10:11:12+00:00", "id": "inv|site|1", "seq": 1, "source": "privatesource", "role": "site",
    "input": {"line1": "123 456 QUINCEWOOD ST", "line2": "% JOHN SMITH", "city": "MIAMI", "state": "FL", "zip": "33101"},
    "cluster": {"shape": "9 9 a a | % a a", "warnings": "multiple_addresses,unparsed_remainder", "size": 41},
    "verdict": "corrected", "corrected": "123 QUINCEWOOD ST, MIAMI FL 33101", "note": "John Smith is a name",
    "parse": {"key": "k4:S|123||QUINCEWOOD|ST||FL|33101", "warnings": ["multiple_addresses", "unparsed_remainder"],
              "unparsed": "456", "components": {"street_number": "123", "street_name": "QUINCEWOOD", "city": "MIAMI"},
              "library_version": "0.3.0"},
    "corrected_parse": {"key": "k4:S|123||QUINCEWOOD|ST||FL|33101", "warnings": [], "unparsed": None,
                        "components": {"street_number": "123", "street_name": "QUINCEWOOD"}, "library_version": "0.3.0"},
}


def test_only_shapes_survive():
    out = export.safe(ANSWER)
    text = json.dumps(out, ensure_ascii=False)
    for s in SECRETS:
        assert s not in text, s
    assert "privatesource" not in text and "inv|site" not in text
    assert out["input"] == "9 9 a a | % a a | a | a | 9"
    assert out["corrected"] == "9 a a, a a 9"
    assert out["components"]["street_name"] == "a" and out["key"] == "a9:a|9||a|a||a|9"
    assert out["note"] == "a a a a a"
    assert (out["same_key"], out["corrected_clean"]) == (True, True)
    assert out["day"] == "2026-10-22"  # the day only, never a time


def test_every_string_is_a_shape_a_code_or_a_name():
    out = export.safe(ANSWER)

    def strings(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for k, x in v.items():
                yield k
                yield from strings(x)
        elif isinstance(v, list):
            for x in v:
                yield from strings(x)

    # a code, a component name or a version, or only the shape letters `a` and `9` and punctuation
    name = re.compile(r"^[a-z][a-z0-9_]*$|^[0-9]+\.[0-9]+\.[0-9]+$")
    shaped = re.compile(r"^[a9\W_]*$")
    for s in strings({k: v for k, v in out.items() if k != "day"}):
        assert name.match(s) or shaped.match(s), s


def test_a_right_parse_keeps_its_warning_verdict():
    a = dict(ANSWER, verdict="right", warning="fair")
    out = export.safe(a)
    assert out["verdict"] == "right" and out["warning"] == "fair" and "corrected" not in out
    assert export.safe(dict(a, warning="JOHN SMITH"))["warning"] is None
    assert "warning" not in export.safe(ANSWER)


def test_a_draft_is_shared_as_a_shape_with_its_checks():
    a = dict(ANSWER, verdict="unclear", draft="123 QUINCEWOOD ST, MIAMI FL 33101",
             draft_parse={"key": "k4:S|123||QUINCEWOOD|ST||FL|33101", "warnings": [], "unparsed": None,
                          "components": {"street_number": "123", "street_name": "QUINCEWOOD"}})
    a.pop("corrected"); a.pop("corrected_parse")
    out = export.safe(a)
    assert out["verdict"] == "unclear" and "corrected" not in out
    assert out["draft"] == "9 a a, a a 9" and out["draft_clean"] is True and out["draft_same_key"] is True
    assert "QUINCEWOOD" not in json.dumps(out) and "33101" not in json.dumps(out)
    assert "draft" not in export.safe(ANSWER)


def test_free_text_cannot_pass_as_a_warning_code():
    a = dict(ANSWER, parse=dict(ANSWER["parse"], warnings=["JOHN SMITH", "missing_zip"]))
    assert export.safe(a)["warnings"] == ["missing_zip"]


def test_source_only_with_the_flag_and_undone_answers_are_dropped(tmp_path):
    answers = tmp_path / "a.jsonl"
    other = dict(ANSWER, id="inv|site|2", verdict="right")
    answers.write_text("".join(json.dumps(x) + "\n" for x in (ANSWER, other, {"undo": "inv|site|2", "ts": "x"})))
    out = tmp_path / "s.jsonl"
    assert export.main([str(answers), "--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == 1 and "source" not in rows[0]
    export.main([str(answers), "--out", str(out), "--with-source"])
    assert json.loads(out.read_text().splitlines()[0])["source"] == "privatesource"
