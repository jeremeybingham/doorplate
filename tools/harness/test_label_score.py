"""Tests for tools/harness/label_score.py on invented rows (no private data).

    pytest tools/harness
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("doorplate")
pytest.importorskip("duckdb")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb  # noqa: E402
import label_score as ls  # noqa: E402


def write(path, rows, cols):
    con = duckdb.connect()
    con.execute("create table t (" + ", ".join(f"{c} varchar" for c in cols) + ")")
    con.executemany(f"insert into t values ({', '.join('?' for _ in cols)})", rows)
    con.execute(f"copy t to '{path}' (format parquet)")


def scored(*argv):
    res, fields, _ = ls.score(ls.parse_args([*argv, "--confirm"]))
    return res, fields


COLS = ["record_id", "source", "role", "line1", "line2", "city", "state", "zip", "pair_id",
        "label_number", "label_predir", "label_name", "label_type", "label_postdir", "label_unit"]


def test_labels_in_the_same_file(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [
        ("1", "t", "site", "123 N OAK ST", "APT 4", "MIAMI", "FL", "33101", None, "123", "N", "OAK", "ST", None, "4"),
        # A label we do not reproduce: a predirectional NAD has and we do not find.
        ("2", "t", "site", "456 OAK ST", None, "MIAMI", "FL", "33101", None, "456", "N", "OAK", "ST", None, "7"),
        # No labels: not counted.
        ("3", "t", "site", "789 ELM AVE", None, "MIAMI", "FL", "33101", None, None, None, None, None, None, None),
    ], COLS)
    res, fields = scored(str(f))
    c = res.c[("t", "site")]
    assert c["rows"] == 3
    assert c["predirectional: labeled"] == 2 and c["predirectional: differ"] == 1
    assert c["suffix: labeled"] == 2 and c["suffix: differ"] == 0
    assert c["unit: labeled"] == 2 and c["unit: differ"] == 0 and c["unit: not in the text"] == 1  # `7` is not in the text
    assert c["number: labeled"] == 2 and c["number: differ"] == 0
    assert res.pairs[("t", "site", "predirectional")][("N", "")] == 1


def test_pair_score_uses_the_other_files_labels(tmp_path):
    cur, snap = tmp_path / "cur.parquet", tmp_path / "snap.parquet"
    write(cur, [
        ("a", "cur", "site", "12 W MAIN ST", None, "MIAMI", "FL", "33101", "p1", None, None, None, None, None, None),
        ("b", "cur", "site", "9 BAY DR", None, "MIAMI", "FL", "33101", "p2", None, None, None, None, None, None),
        # Two rows with the same pair id on one side: left out.
        ("c", "cur", "site", "1 A ST", None, "MIAMI", "FL", "33101", "p3", None, None, None, None, None, None),
        ("d", "cur", "site", "2 A ST", None, "MIAMI", "FL", "33101", "p3", None, None, None, None, None, None),
        ("e", "cur", "site", "7 MAIN ST", None, "MIAMI", "FL", "33101", "p4", None, None, None, None, None, None),
        # Same ZIP, another house number: a voter who moved down the road.
        ("f", "cur", "site", "8 MAIN ST", None, "MIAMI", "FL", "33101", "p5", None, None, None, None, None, None),
    ], COLS)
    write(snap, [
        ("a", "snap", "site", None, None, None, None, "33101", "p1", "12", "W", "MAIN", "ST", None, None),
        ("b", "snap", "site", None, None, None, None, "33101", "p2", "9", "S", "BAY", "DR", None, None),
        ("c", "snap", "site", None, None, None, None, "33101", "p3", "1", None, "A", "ST", None, None),
        # A voter who moved: same id, another ZIP. Dropped unless --any-zip.
        ("e", "snap", "site", None, None, None, None, "90210", "p4", "5", "N", "FAR", "WAY", None, None),
        ("f", "snap", "site", None, None, None, None, "33101", "p5", "80", "N", "MAIN", "ST", None, None),
    ], COLS)
    res, _ = scored(str(cur), "--labels", str(snap))
    c = res.c[("cur", "site")]
    assert c["rows"] == 3  # p3 is not unique in cur; p5 moved down the road
    assert c["predirectional: labeled"] == 2 and c["predirectional: differ"] == 1  # p5 is skipped
    assert c["number: labeled"] == 3 and c["number: differ"] == 1
    assert res.other_number[("cur", "site")] == 1
    assert c["name: labeled"] == 2 and c["name: differ"] == 0
    assert res.pairs_seen[("cur", "site")] == 4 and res.dropped[("cur", "site")] == 1
    res, _ = scored(str(cur), "--labels", str(snap), "--any-zip")
    assert res.c[("cur", "site")]["rows"] == 4
    res, _ = scored(str(cur), "--labels", str(snap), "--any-number")
    assert res.c[("cur", "site")]["predirectional: labeled"] == 3


def test_shape_collapses_runs():
    assert ls.shape("12B") == "9a" and ls.shape("APT 4") == "a 9" and ls.shape("1/2") == "9/9"


def test_unknown_field_is_refused(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [("1", "t", "site", "1 A ST", None, None, None, None, None, "1", None, "A", "ST", None, None)], COLS)
    with pytest.raises(SystemExit):
        scored(str(f), "--fields", "bogus")


def test_by_warning_counts_each_warning_against_the_labels(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [
        # No warning, labels agree.
        ("1", "t", "site", "123 OAK ST", None, "MIAMI", "FL", "33101", None, "123", None, "OAK", "ST", None, None),
        # `123 A MAIN ST` carries ambiguous_number_letter; the label calls the letter the number's suffix: we differ.
        ("2", "t", "site", "123 A MAIN ST", None, "MIAMI", "FL", "33101", None, "123A", None, "MAIN", "ST", None, None),
        # The same warning where the label agrees with us (an initial in the name).
        ("3", "t", "site", "820 A PHILIP RANDOLPH BLVD", None, "MIAMI", "FL", "33101", None, "820", None,
         "A PHILIP RANDOLPH", "BLVD", None, None),
    ], COLS)
    res, fields = scored(str(f), "--by-warning")
    key = ("t", "site")
    w = res.w[key + ("ambiguous_number_letter",)]
    assert w["rows"] == 2 and w["number: labeled"] == 2 and w["number: differ"] == 1
    assert res.w[key + ("(none)",)]["rows"] == 1 and res.w[key + ("(none)",)]["number: differ"] == 0
    # The per-warning rows add up to the rows (each of these rows has one warning, or none).
    assert sum(v["rows"] for k, v in res.w.items() if k[:2] == key) == res.c[key]["rows"]
    text = ls.render_by_warning(res, fields)
    assert "| `ambiguous_number_letter` | 2 |" in text and "1 / 2 (50.0%)" in text
    assert "A MAIN" not in text and "PHILIP" not in text  # counts only


COLS_EXT = COLS + ["label_postmod"]


def test_a_labels_ext_postmodifier_is_the_suffix(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [
        # The county labels type ST and modifier EXT: we read `MAIN STREET` with suffix EXT. Agree.
        ("1", "t", "site", "100 MAIN ST EXT", None, "MIAMI", "FL", "33101", None, "100", None, "MAIN", "ST", None, None, "EXT"),
        ("2", "t", "site", "200 OAK RD EXT", None, "MIAMI", "FL", "33101", None, "200", None, "OAK", "RD", None, None, "extension"),
        # No modifier: a real disagreement on the suffix stays one.
        ("3", "t", "site", "300 ELM AVE", None, "MIAMI", "FL", "33101", None, "300", None, "ELM", "ST", None, None, None),
        # A modifier that is not EXT does not change the comparison.
        ("4", "t", "site", "400 PINE ST BUS", None, "MIAMI", "FL", "33101", None, "400", None, "PINE", "ST", None, None, "BUS"),
    ], COLS_EXT)
    res, _ = scored(str(f))
    c = res.c[("t", "site")]
    assert c["suffix: labeled"] == 4 and c["suffix: differ"] == 2  # rows 3 and 4 only
    assert c["name: differ"] == 1  # row 4: `PINE ST BUS` is not `PINE`
    assert res.pairs[("t", "site", "suffix")][("ST", "AVE")] == 1


def test_examples_file_holds_ids_and_values_and_is_never_printed(tmp_path, capsys, monkeypatch):
    f = tmp_path / "r.parquet"
    rows = [(str(i), "t", "site", f"{i} OAK DR", None, "MIAMI", "FL", "33101", None, str(i), None, "OAK", "CT", None, None)
            for i in range(1, 9)]
    write(f, rows, COLS)
    local = ls.ROOT / "local-data"
    out = local / f"_test_examples_{tmp_path.name}.tsv"
    try:
        res, _ = scored(str(f), "--examples", str(out), "--examples-max", "3")
        assert len(res.examples) == 3  # 8 disagreements of one pair, capped at 3
        assert ls.write_examples(res, out) == 3
        lines = out.read_text().splitlines()
        assert lines[0].split("\t")[:3] == ["source", "role", "field"]
        assert lines[1].split("\t")[2:] == ["suffix", "1", "", "CT", "DR"]
        # main() writes the file and prints only the count and the path, never a row.
        capsys.readouterr()
        assert ls.main([str(f), "--examples", str(out), "--examples-max", "2", "--confirm"]) == 0
        shown = capsys.readouterr().out
        assert "2 examples written" in shown and "1\tsuffix" not in shown and "OAK DR" not in shown
    finally:
        out.unlink(missing_ok=True)


def test_examples_must_be_under_local_data(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [("1", "t", "site", "1 A ST", None, None, None, None, None, "1", None, "A", "ST", None, None)], COLS)
    with pytest.raises(SystemExit):
        ls.main([str(f), "--examples", str(tmp_path / "x.tsv"), "--confirm"])


def test_a_unit_that_is_not_in_the_text_is_the_sources_not_a_miss(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [
        # We find the unit: agree.
        ("1", "t", "site", "123 OAK ST APT 4", None, "MIAMI", "FL", "33101", None, "123", None, "OAK", "ST", None, "4"),
        # The label has a unit the text does not: not a difference, counted apart.
        ("2", "t", "site", "456 OAK ST", None, "MIAMI", "FL", "33101", None, "456", None, "OAK", "ST", None, "7B"),
        # The unit is in the text and we missed it (a value we do not read): a difference.
        ("3", "t", "site", "789 OAK ST 12 ZZ", None, "MIAMI", "FL", "33101", None, "789", None, "OAK", "ST", None, "ZZ"),
    ], COLS)
    res, fields = scored(str(f))
    c = res.c[("t", "site")]
    assert c["unit: labeled"] == 3 and c["unit: not in the text"] == 1
    assert c["unit: differ"] == 1  # row 3: `ZZ` is in the text and we read no unit
    assert "nowhere in the text" in ls.render(res, fields, 5, "own")


def test_a_suffix_inside_the_label_name_is_the_same_name(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [
        # No type label: the provider wrote the suffix into the name.
        ("1", "t", "site", "123 OAK ST", None, "MIAMI", "FL", "33101", None, "123", None, "OAK ST", None, None, None),
        ("2", "t", "site", "124 OAK STREET", None, "MIAMI", "FL", "33101", None, "124", None, "OAK STREET", None, None, None),
        # A different name stays different.
        ("3", "t", "site", "125 ELM ST", None, "MIAMI", "FL", "33101", None, "125", None, "OAK ST", None, None, None),
    ], COLS)
    res, _ = scored(str(f))
    c = res.c[("t", "site")]
    assert c["name: labeled"] == 3 and c["name: differ"] == 1
