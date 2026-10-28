"""Tests for tools/review/full.py and `export.py --full` on invented rows (no private data).

    pytest tools/review
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import export  # noqa: E402
import full  # noqa: E402

INPUT = {"line1": "ACME HOLDINGS LLC 123 SMITH ST", "line2": "% JOHN SMITH", "city": "MIAMI", "state": "FL", "zip": "33101"}
ANSWER = {
    "ts": "2026-10-22T10:11:12+00:00", "id": "irs-eo-bmf|organization|1", "seq": 1, "source": "irs-eo-bmf", "role": "organization",
    "input": INPUT, "cluster": {"shape": "a a a 9 a a | % a a", "warnings": "missing_street_number", "size": 41},
    "verdict": "corrected", "corrected": "123 SMITH ST, % JOHN SMITH, MIAMI FL 33101", "note": "John Smith is the contact; delete ACME",
    "parse": {"key": "k3:S||ACME HOLDINGS LLC 123 SMITH|ST||FL|33101", "warnings": ["missing_street_number"], "unparsed": None,
              "components": {"street_name": "ACME HOLDINGS LLC 123 SMITH", "attention": "% JOHN SMITH", "city": "MIAMI"}},
    "corrected_parse": {"key": "k3:S|123||SMITH|ST||FL|33101", "warnings": [], "unparsed": None,
                        "components": {"street_number": "123", "street_name": "SMITH", "attention": "% JOHN SMITH"}},
}


def test_allowlist_parses_masks_comments_and_rejects_typos(tmp_path):
    f = tmp_path / "full-ok.txt"
    f.write_text("# cleared\nirs-eo-bmf  mask=line2   # care-of names\nfmcsa-census\nx mask=line2,city\n")
    assert full.load_allowlist(f) == {"irs-eo-bmf": {"line2"}, "fmcsa-census": set(), "x": {"line2", "city"}}
    assert full.load_allowlist(tmp_path / "missing.txt") == {}
    f.write_text("a mask=street\n")
    with pytest.raises(ValueError):
        full.load_allowlist(f)
    f.write_text("a hide=line2\n")
    with pytest.raises(ValueError):
        full.load_allowlist(f)


def test_masking_hides_names_but_keeps_street_words_and_structure():
    words = full.masked_words(INPUT, {"line2"})
    assert words == {"JOHN"}  # SMITH is also in the unmasked street line, so it stays readable
    assert full.mask_text("% JOHN SMITH", words) == "% a SMITH"
    assert full.mask_text("C/O JOHN, ATTN JOHN", words) == "C/O a, ATTN a"
    # words from a masked field that are address structure are never hidden
    assert "APT" not in full.masked_words({"line2": "C/O APT 4 ACME"}, {"line2"})
    assert "ACME" in full.masked_words({"line2": "C/O APT 4 ACME"}, {"line2"})


def test_edit_summary_describes_the_change_in_words():
    assert full.edit_summary("ACME LLC 123 MAIN ST, MIAMI", "123 MAIN ST, MIAMI") == ['deleted leading "ACME LLC"']
    assert full.edit_summary("123 MAIN ST, MIAMI", "123 MAIN ST, MIAMI") == ["no change"]
    assert full.edit_summary("123 MAIN ST MIAMI", "123 MAIN ST, MIAMI") == ["punctuation changed"]
    assert full.edit_summary("123 MAIN ST", "123 MAIN ST APT 4") == ['inserted "APT 4"']
    assert full.edit_summary("123 MAIN ST X", "123 MAIN ST Y") == ['replaced trailing "X" with "Y"']


def test_one_line_matches_the_review_page():
    assert full.one_line(INPUT) == "ACME HOLDINGS LLC 123 SMITH ST, % JOHN SMITH, MIAMI, FL 33101"
    assert full.one_line({"line1": "1 A ST", "last_line": "MIAMI FL 33101"}) == "1 A ST, MIAMI FL 33101"


def test_the_entry_shows_street_text_and_the_note_but_not_the_masked_name():
    text = full.entry(1, ANSWER, {"line2"})
    assert "ACME HOLDINGS LLC 123 SMITH ST" in text            # line 1 in full
    assert 'deleted leading "ACME HOLDINGS LLC"' in text       # the edit, in words
    assert "delete ACME" in text                               # the note, verbatim
    assert "john" not in text.lower() and "% a SMITH" in text  # the care-of name is a shape everywhere, even in the note
    assert "clean: yes; same key as the original parse: no" in text


def test_a_right_parse_shows_its_warning_verdict_and_old_answers_say_not_recorded():
    right = dict(ANSWER, verdict="right", warning="fair")
    assert "## 1. right (warning fair)" in full.entry(1, right, set())
    assert "(warning not recorded)" in full.entry(1, dict(right, warning=None), set())


def test_a_draft_is_shown_and_labelled_as_not_a_correction():
    a = dict(ANSWER, verdict="unclear", draft="123 SMITH ST, MIAMI FL 33101",
             draft_parse={"key": "k3:S|123||SMITH|ST||FL|33101", "warnings": [], "unparsed": None, "components": {"street_number": "123"}})
    a.pop("corrected"); a.pop("corrected_parse")
    text = full.entry(1, a, {"line2"})
    assert "## 1. unclear" in text and "- draft (an attempt, not saved as a correction): '123 SMITH ST, MIAMI FL 33101'" in text
    assert "- draft parse:" in text and "- corrected:" not in text and "delete ACME" in text
    assert "draft" not in full.entry(1, ANSWER, {"line2"})


def test_only_allowlisted_sources_are_written():
    other = dict(ANSWER, source="privatesource", id="privatesource|r|2")
    text, counts, skipped = full.build([ANSWER, other], {"irs-eo-bmf": {"line2"}})
    assert counts == {"irs-eo-bmf": 1} and skipped == {"privatesource"}
    assert "privatesource" not in text and "irs-eo-bmf" in text


def test_the_command_refuses_without_an_allowlist_and_outside_local_data(tmp_path):
    answers = tmp_path / "local-data" / "review" / "answers.jsonl"
    answers.parent.mkdir(parents=True)
    answers.write_text(json.dumps(ANSWER) + "\n")
    out = answers.parent / "answers-full.md"
    with pytest.raises(SystemExit) as e:
        # an explicit missing allowlist: the default one is the maintainer's real file in local-data/
        export.main([str(answers), "--full", "--out", str(out), "--allow", str(answers.parent / "full-ok.txt")])
    assert "no source is cleared" in str(e.value)
    (answers.parent / "full-ok.txt").write_text("irs-eo-bmf mask=line2\n")
    with pytest.raises(SystemExit) as e:
        export.main([str(answers), "--full", "--out", str(tmp_path / "answers-full.md"),
                     "--allow", str(answers.parent / "full-ok.txt")])
    assert "outside local-data" in str(e.value)
    assert export.main([str(answers), "--full", "--out", str(out), "--allow", str(answers.parent / "full-ok.txt")]) == 0
    assert "JOHN" not in out.read_text() and "ACME HOLDINGS LLC 123 SMITH ST" in out.read_text()
