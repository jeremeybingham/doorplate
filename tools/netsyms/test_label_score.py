"""Tests for tools/netsyms/label_score.py on invented rows (no private data).

    pytest tools/netsyms
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
    assert c["unit: labeled"] == 2 and c["unit: differ"] == 1
    assert c["number: labeled"] == 2 and c["number: differ"] == 0
    assert res.pairs[("t", "site", "predirectional")][("N", "")] == 1
    assert res.states[("t", "site", "unit")]["FL"] == 1


def test_pair_score_uses_the_other_files_labels(tmp_path):
    cur, snap = tmp_path / "cur.parquet", tmp_path / "snap.parquet"
    write(cur, [
        ("a", "cur", "site", "12 W MAIN ST", None, "MIAMI", "FL", "33101", "p1", None, None, None, None, None, None),
        ("b", "cur", "site", "9 BAY DR", None, "MIAMI", "FL", "33101", "p2", None, None, None, None, None, None),
        # Two rows with the same pair id on one side: left out.
        ("c", "cur", "site", "1 A ST", None, "MIAMI", "FL", "33101", "p3", None, None, None, None, None, None),
        ("d", "cur", "site", "2 A ST", None, "MIAMI", "FL", "33101", "p3", None, None, None, None, None, None),
        ("e", "cur", "site", "7 MAIN ST", None, "MIAMI", "FL", "33101", "p4", None, None, None, None, None, None),
    ], COLS)
    write(snap, [
        ("a", "snap", "site", None, None, None, None, "33101", "p1", "12", "W", "MAIN", "ST", None, None),
        ("b", "snap", "site", None, None, None, None, "33101", "p2", "9", "S", "BAY", "DR", None, None),
        ("c", "snap", "site", None, None, None, None, "33101", "p3", "1", None, "A", "ST", None, None),
        # A voter who moved: same id, another ZIP. Dropped unless --any-zip.
        ("e", "snap", "site", None, None, None, None, "90210", "p4", "5", "N", "FAR", "WAY", None, None),
    ], COLS)
    res, _ = scored(str(cur), "--labels", str(snap))
    c = res.c[("cur", "site")]
    assert c["rows"] == 2  # p3 is not unique in cur
    assert c["predirectional: labeled"] == 2 and c["predirectional: differ"] == 1
    assert c["name: labeled"] == 2 and c["name: differ"] == 0
    assert res.pairs_seen[("cur", "site")] == 3 and res.dropped[("cur", "site")] == 1
    res, _ = scored(str(cur), "--labels", str(snap), "--any-zip")
    assert res.c[("cur", "site")]["rows"] == 3


def test_shape_collapses_runs():
    assert ls.shape("12B") == "9a" and ls.shape("APT 4") == "a 9" and ls.shape("1/2") == "9/9"


def test_unknown_field_is_refused(tmp_path):
    f = tmp_path / "r.parquet"
    write(f, [("1", "t", "site", "1 A ST", None, None, None, None, None, "1", None, "A", "ST", None, None)], COLS)
    with pytest.raises(SystemExit):
        scored(str(f), "--fields", "bogus")
