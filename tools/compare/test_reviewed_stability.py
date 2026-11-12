"""Tests for tools/compare/reviewed_stability.py on invented cards. pytest tools/compare/test_reviewed_stability.py"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

doorplate = pytest.importorskip("doorplate")
import reviewed_stability as R


def card(cid, verdict, inp, key=None, ts="2026-11-01T00:00:00", version=None, source="invented"):
    if key is None:
        key = R.current_key(doorplate, inp)
    return {"id": cid, "ts": ts, "verdict": verdict, "source": source, "input": inp,
            "parse": {"key": key, "library_version": version or doorplate.__version__}}  # fmt: skip


def write(tmp_path, *cards, name="answers-a.jsonl"):
    (tmp_path / name).write_text("".join(json.dumps(c) + "\n" for c in cards))


FIELDS = {"line1": "12 Elm St", "city": "Dayton", "state": "OH", "zip": "45402"}


def test_groups_follow_the_verdicts():
    assert R.group_of("both_right") == "right" and R.group_of("rule_right") == "right"
    assert R.group_of("both_wrong") == "wrong" and R.group_of("corrected") == "corrected"
    assert R.group_of("junk") is None and R.group_of(None) is None


def test_an_unchanged_right_card_and_a_tampered_one(tmp_path):
    other = {"line1": "40 Oak Ave", "line2": "Apt 3", "city": "Tampa", "state": "FL", "zip": "33601"}
    write(tmp_path, card("a", "doorplate_right", FIELDS), card("b", "both_right", other, key="k5:S|99||NOPE|ST||FL|33601"))
    out, changed = R.report(doorplate, R.load_cards(tmp_path))
    text = "\n".join(out)
    assert "| right | 2 | 2 | 1 | 1 | 0 | 0 |" in text
    assert changed == ["b"]
    assert "Elm" not in text and "Oak" not in text  # counts only


def test_the_latest_answer_for_an_id_wins_and_unused_verdicts_are_skipped(tmp_path):
    old = card("a", "both_wrong", FIELDS, ts="2026-10-01T00:00:00")
    new = card("a", "both_right", FIELDS, ts="2026-11-02T00:00:00")
    write(tmp_path, old, card("z", "junk", FIELDS), name="answers-1.jsonl")
    write(tmp_path, new, name="answers-2.jsonl")
    cards = R.load_cards(tmp_path)
    assert list(cards) == ["a"] and cards["a"]["verdict"] == "both_right"


def test_a_card_from_another_key_format_is_not_compared(tmp_path):
    write(tmp_path, card("a", "doorplate_right", FIELDS, key="k2:old-format", version="0.3.0"))
    out, changed = R.report(doorplate, R.load_cards(tmp_path))
    assert "| right | 1 | 0 | 0 | 0 | 1 | 0 |" in "\n".join(out) and changed == []


def test_last_line_cards_are_parsed_as_one_line(tmp_path):
    inp = {"line1": "12 Elm St", "last_line": "Dayton OH 45402", "provider": "invented"}
    assert R.one_line(inp) == "12 Elm St, Dayton OH 45402"
    assert R.current_key(doorplate, inp).startswith("k")
    write(tmp_path, card("a", "doorplate_right", inp))
    out, _ = R.report(doorplate, R.load_cards(tmp_path))
    assert "| right | 1 | 1 | 1 | 0 | 0 | 0 |" in "\n".join(out)


def test_the_same_version_check_counts_a_difference(tmp_path):
    write(tmp_path, card("a", "doorplate_right", FIELDS), card("b", "both_right", FIELDS, key="k5:S|1||X|ST||OH|45402"))
    text = "\n".join(R.report(doorplate, R.load_cards(tmp_path))[0])
    assert "Of the 2 cards stored under this same version string, 1 read differently now" in text


def test_main_writes_the_report_and_the_ids(tmp_path):
    write(tmp_path, card("b", "both_right", FIELDS, key="k5:S|1||X|ST||OH|45402"))
    out, ids = tmp_path / "r.md", tmp_path / "ids.txt"
    assert R.main(["--review-dir", str(tmp_path), "--out", str(out), "--ids-out", str(ids)]) == 0
    assert "Reviewed rows" in out.read_text() and ids.read_text() == "b\n"


def test_the_warning_table_counts_flagged_cards_by_group(tmp_path):
    odd = {"line1": "12 Elm St and more words here", "city": "Dayton", "state": "OH", "zip": "45402"}
    flagged = R.current_reading(doorplate, odd)[1]
    write(tmp_path, card("a", "doorplate_right", FIELDS), card("b", "both_wrong", odd))
    text = "\n".join(R.report(doorplate, R.load_cards(tmp_path))[0])
    assert "| right | 1 | 0 | 1 |" in text
    assert f"| wrong | 1 | {int(flagged)} | {1 - int(flagged)} |" in text
