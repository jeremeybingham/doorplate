"""Tests for tools/docs/issue_states.py (#237). Invented issues and pages; no `gh`, no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import issue_states as s  # noqa: E402


def issue(state="OPEN", milestone=None, title="an invented issue"):
    return {"state": state, "milestone": milestone, "title": title}


ROAD = """# Roadmap

## Next: 0.4.1

- shipped: #1 and #2 (open work waits in #3)

## After that: 0.5.0, the `k4`

- a rule (#10) and another (#11, done in 0.4.0) and one in code `#99`
- an old one with no marker (#12)
- one in the wrong milestone (#13)

## Waiting, on data or demand

- **Later** (the milestone): #20, #21
- **Tooling** (never shipped): #22
- more shapes: #23
"""
BACKLOG = """| **0.5.0** | the `k4`: #10, #13 |
| **Later** | wanted: #20, #14 |
| **0.4.x** | shipped #1, #2 |
"""


def run(issues, trackers=None, road=ROAD, backlog=BACKLOG):
    return s.check({"roadmap.md": road, "backlog.md": backlog}, issues, trackers or {})


BASE = {
    1: issue("CLOSED", "0.4.x"), 2: issue("CLOSED", "0.4.x"), 3: issue("OPEN", "0.4.x"),
    10: issue("OPEN", "0.5.0"), 11: issue("CLOSED", "0.4.0"), 12: issue("CLOSED", "0.5.0"),
    13: issue("OPEN", "Later"), 14: issue("OPEN", "Later"),
    20: issue("OPEN", "Later"), 21: issue("OPEN", "Later"), 22: issue("OPEN", "Tooling"), 23: issue("OPEN", "Later"),
}


def test_numbers_skip_code_and_anchors():
    assert s.numbers("see #10, `#99` and [a](x.md#12) and a#13 and (#14).") == [10, 14]


def test_a_consistent_set_has_no_problems_except_the_ones_planted():
    p = run(BASE)
    assert any("#12 is closed" in m for m in p), p
    assert any("#13 is in milestone 'Later', listed under '0.5.0'" in m for m in p), p
    assert not any("#11" in m for m in p), "a closed issue on a line that says done is fine"
    assert not any("#99" in m for m in p)
    assert not any("#1 " in m or "#2 " in m for m in p), "the Next part is not a planned list"


def test_the_tooling_and_later_bullets_expect_their_milestone():
    issues = {**BASE, 22: issue("OPEN", "Later"), 20: issue("OPEN", "Tooling")}
    p = run(issues)
    assert any("#22 is in milestone 'Later', listed under 'Tooling'" in m for m in p), p
    assert any("#20 is in milestone 'Tooling', listed under 'Later'" in m for m in p), p


def test_an_open_issue_nobody_mentions_and_an_unknown_number_are_reported():
    issues = {**BASE, 30: issue("OPEN", "Later", "a forgotten one")}
    p = run(issues)
    assert any(m.startswith("#30 is open and neither") for m in p), p
    p = run(BASE, road=ROAD + "\n- gone: #77\n")
    assert any("#77 is not an issue" in m for m in p), p


def test_tracker_boxes_follow_the_issue_state():
    body = "- [x] #10 ticked but open\n- [ ] #1 closed but unticked\n- [x] #1 fine\n- [ ] #10 fine\n"
    p = run(BASE, trackers={200: body})
    assert "tracker #200: #10 is ticked but open" in p
    assert "tracker #200: #1 is closed but not ticked" in p
    assert len([m for m in p if m.startswith("tracker")]) == 2
