"""Tests for the libpostal provider of tools/compare/compare_usaddress.py on invented addresses (issue 215).

pytest tools/compare/test_libpostal_provider.py
The last test runs the real build when ~/projects/libpostal-senzing (or $LIBPOSTAL_HOME) exists and is skipped otherwise.
"""

import json
import stat
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compare_usaddress as C

STREET = ("StreetNamePreDirectional", "StreetNamePreType", "StreetName", "StreetNamePostType", "StreetNamePostDirectional")


def test_common_folds_street_occupancy_and_box_labels():
    assert {C.common(label) for label in STREET} == {"StreetName"}
    assert C.common("OccupancyType") == C.common("OccupancyIdentifier") == C.common("SubaddressType") == "Occupancy"
    assert C.common("USPSBoxType") == C.common("USPSBoxID") == "USPSBox"
    assert C.common("AddressNumberSuffix") == "AddressNumber"  # the existing SAME rule still applies
    assert C.common("ZipCode") == "ZipCode" and C.common(None) is None


def test_libpostal_pieces_are_cut_into_tokens_with_common_labels():
    parsed = [["123", "house_number"], ["example street", "road"], ["apt 4b", "unit"], ["springfield", "city"], ["il", "state"], ["62701", "postcode"]]
    assert C.libpostal_pairs(parsed) == [
        ("123", "AddressNumber"), ("example", "StreetName"), ("street", "StreetName"), ("apt", "Occupancy"), ("4b", "Occupancy"),
        ("springfield", "PlaceName"), ("il", "StateName"), ("62701", "ZipCode"),
    ]  # fmt: skip
    # a label with no match never agrees with a gold label
    assert C.libpostal_pairs([["near the park", "near"]])[0][1] == "libpostal:near"
    assert C.LIBPOSTAL_MAP["suburb"] == C.LIBPOSTAL_MAP["city"] == "PlaceName"


def test_lowercased_pieces_are_found_in_the_input_ignoring_case():
    s = "123 Example Street APT 4B, Springfield, IL 62701"
    spans = C.libpostal_spans(s, [["123", "house_number"], ["example street", "road"], ["apt 4b", "unit"], ["il", "state"]])
    text = s.encode()
    assert [(text[a:b].decode(), label) for a, b, label in spans] == [
        ("123", "AddressNumber"), ("Example", "StreetName"), ("Street", "StreetName"), ("APT", "Occupancy"), ("4B", "Occupancy"),
        ("IL", "StateName"),
    ]  # fmt: skip


def test_a_piece_that_is_not_in_the_input_is_skipped_not_misplaced():
    assert C.libpostal_spans("12 Elm St", [["12", "house_number"], ["oak", "road"]]) == [(0, 2, "AddressNumber")]
    # a string whose lowercase differs in length falls back to exact matching and does not crash
    assert C.byte_spans_ci("İ 12", ["12"]) == [(3, 5)]


def test_expressible_leaves_out_labels_libpostal_cannot_produce():
    assert C.expressible([("12", "AddressNumber"), ("Elm", "StreetName"), ("St", "StreetNamePostType"), ("4", "OccupancyIdentifier")])
    assert not C.expressible([("RR", "USPSBoxGroupType"), ("2", "USPSBoxGroupID")])
    assert not C.expressible([("John", "Recipient"), ("12", "AddressNumber")])


def test_score_common_counts_scored_tokens_and_ignores_punctuation():
    toks = [("12", "AddressNumber"), ("Elm", "StreetName"), ("St", "StreetNamePostType"), ("-", "StreetName"), ("Apt", "OccupancyType"), ("4", "OccupancyIdentifier")]
    s = "12 Elm St - Apt 4"
    spans = C.byte_spans(s, [t for t, _ in toks])
    pred = C.libpostal_spans(s, [["12", "house_number"], ["elm st", "road"], ["apt 4", "unit"]])
    assert C.score_common(toks, spans, pred) == (5, 5)
    wrong = C.libpostal_spans(s, [["12", "house_number"], ["elm st", "road"], ["apt 4", "po_box"]])
    assert C.score_common(toks, spans, wrong) == (5, 3)


def fake_home(tmp_path, results):
    """A libpostal folder whose Python is a script that prints fixed results (the real worker is not run)."""
    py = tmp_path / "venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/usr/bin/env python3\nimport json, sys\nn = len(json.load(sys.stdin))\n"
                  f"print(json.dumps({{'load_seconds': 0.5, 'parse_seconds': 0.25, 'results': {results!r}[:n] * n}}))\n")
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "LIBPOSTAL_COMMIT.txt").write_text("abc123\n")
    d = tmp_path / "data" / "libpostal"
    d.mkdir(parents=True)
    (d / "parser_model_file_version").write_text("v1.2.0\n")
    return tmp_path


def test_run_passes_the_strings_and_reads_the_answer(tmp_path):
    home = fake_home(tmp_path, [[["12", "house_number"]]])
    out = C.libpostal_run(["12 Elm St"], str(home))
    assert out["results"] == [[["12", "house_number"]]] and out["load_seconds"] == 0.5
    pins = C.libpostal_pins(str(home))
    assert pins["commit"] == "abc123" and pins["parser_model"] == "v1.2.0" and pins["data_checksum"] == "unknown"


def test_a_missing_build_stops_with_a_message(tmp_path):
    with pytest.raises(SystemExit) as e:
        C.libpostal_run(["12 Elm St"], str(tmp_path / "nowhere"))
    assert "no libpostal virtualenv" in str(e.value)


@pytest.mark.skipif(not (Path(C.libpostal_home()) / "venv" / "bin" / "python").exists(), reason="no libpostal build")
def test_the_real_build_parses_an_invented_address():
    out = C.libpostal_run(["123 Example Street Apt 4B, Springfield, IL 62701"])
    labels = {label for _, label in out["results"][0]}
    assert {"house_number", "road", "city", "state", "postcode"} <= labels
    assert json.dumps(out)  # serializable, so the worker's answer round-trips


BENCH_DIR = HERE.parents[1] / "benchmarks"


def test_the_speed_helper_stops_with_a_message_when_there_is_no_build(tmp_path):
    sys.path.insert(0, str(BENCH_DIR))
    import _libpostal

    with pytest.raises(SystemExit) as e:
        _libpostal.bench(["12 Elm St"], home=str(tmp_path / "nowhere"))
    assert "no libpostal virtualenv" in str(e.value)


@pytest.mark.skipif(not (Path(C.libpostal_home()) / "venv" / "bin" / "python").exists(), reason="no libpostal build")
def test_the_speed_helper_times_one_and_two_processes_on_the_real_build():
    sys.path.insert(0, str(BENCH_DIR))
    import _libpostal

    texts = ["123 Example Street Apt 4B, Springfield, IL 62701"] * 200
    one = _libpostal.bench(texts, procs=1, reps=2)
    two = _libpostal.bench(texts, procs=2, reps=2)
    assert one["procs"] == 1 and two["procs"] == 2
    assert one["seconds"] > 0 and two["seconds"] > 0 and one["load_seconds"] > 0
    assert one["rss_after_load_mb"] > 100 and one["rss_peak_mb"] >= one["rss_after_load_mb"]
    assert two["pss_total_mb"] > 0  # the models are loaded in both processes before the timed passes start
