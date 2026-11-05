"""Tests for tools/review/rule_queue.py on invented rows (no private data, no example binary).

pytest tools/review
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rule_queue


def test_the_example_output_is_read_into_key_warnings_and_unparsed():
    got = rule_queue.parse_output(["k4:S|1||A|ST||FL|33101\tMissingStreetNumber|PossiblyTruncated\tX", "k4:S|2||B|ST||FL|33101\t\t", "error"])
    assert got == [("k4:S|1||A|ST||FL|33101", ["MissingStreetNumber", "PossiblyTruncated"], "X"), ("k4:S|2||B|ST||FL|33101", [], ""), ("error", [], "")]
    assert rule_queue.snake("MissingStreetNumber") == "missing_street_number"


def test_changed_rows_are_the_ones_whose_reading_differs():
    base = [("k1", [], ""), ("k2", ["W"], ""), ("k3", [], "")]
    off = [("k1", [], ""), ("k2", [], ""), ("k3x", [], "u")]
    assert rule_queue.changed(base, off) == [1, 2]


def test_draw_alternates_sources_caps_the_share_and_is_seeded():
    sources = ["big"] * 40 + ["small"] * 5
    idx = list(range(45))
    got = rule_queue.draw(idx, sources, 10, 0.5, seed=3)
    assert len(got) == 10 and len(set(got)) == 10
    assert sum(sources[i] == "big" for i in got) <= 5 and sum(sources[i] == "small" for i in got) == 5
    assert got == rule_queue.draw(idx, sources, 10, 0.5, seed=3)
    # fewer changed rows than asked: all of them, once
    assert sorted(rule_queue.draw([1, 2], ["a", "a", "b"], 10, 0.4, seed=1)) == [1, 2]


def test_cards_carry_the_fields_the_group_and_the_other_reading():
    sample = [("src", ["12 OAK ST", "", "MIAMI", "FL", "33101"]), ("src", ["12 OAK ST", "", "MIAMI", "FL", "33101"]),
              ("other", ["5 ELM AVE", "STE 2", "TAMPA", "FL", "33601"])]
    base = [("a", [], "")] * 3
    off = [("b", ["MissingZip"], "")] * 3
    cards, total, per = rule_queue.build(sample, base, off, "att", "attention lines", ["rules.rs:1"], 3, 1, 1.0)
    assert total == 3 and per == {"src": 2, "other": 1}
    assert len(cards) == 2  # the repeated string is taken once
    c = next(x for x in cards if x["source"] == "other")
    assert c["line2"] == "STE 2" and "line1" in c and c["cluster"]["size"] == 3
    assert c["alt"]["key"] == "b" and c["alt"]["warnings"] == ["missing_zip"] and c["alt"]["changed_by_source"] == {"src": 2, "other": 1}
    assert c["id"].startswith("rule|att|other|")


def test_scoring_weights_the_wrong_share_by_source():
    queue = [{"id": "r1", "alt": {"changed_by_source": {"a": 90, "b": 10}}}, {"id": "r2", "alt": {"changed_by_source": {"a": 90, "b": 10}}},
             {"id": "r3", "alt": {"changed_by_source": {"a": 90, "b": 10}}}]
    answers = [{"id": "r1", "source": "a", "verdict": "rule_off_right"}, {"id": "r2", "source": "a", "verdict": "rule_right"},
               {"id": "r3", "source": "b", "verdict": "rule_off_right"}]
    counts, share, total = rule_queue.score(answers, queue)
    assert counts == {"rule_off_right": 2, "rule_right": 1} and total == 100
    assert abs(share - (90 * 0.5 + 10 * 1.0) / 100) < 1e-9
