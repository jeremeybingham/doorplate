"""Tests for tools/review/changed_queue.py on invented dumps and records (no private data).

pytest tools/review
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

duckdb = pytest.importorskip("duckdb")
pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

import changed_queue


def write_dump(d, name, keys, warns, units, records):
    d.mkdir(parents=True, exist_ok=True)
    n = len(keys)
    cols = {
        "rn": list(range(n)),
        "role": ["mailing"] * n,
        "record_id": [f"r{i}" for i in range(n)],
        "key": keys,
        "warnings": warns,
    }
    if units is not None:
        cols["key_unit"] = units
    pq.write_table(pa.table(cols), d / f"{name}.parquet")
    (d / f"{name}.json").write_text(
        json.dumps({"source": name, "records": str(records)})
    )


def records(path, n):
    pq.write_table(
        pa.table(
            {
                "line1": [f"{i} OAK ST" for i in range(n)],
                "line2": [""] * n,
                "city": ["MIAMI"] * n,
                "state": ["FL"] * n,
                "zip": ["33101"] * n,
            }
        ),
        path,
    )


def setup(tmp_path, unit=True):
    rec = tmp_path / "rec.parquet"
    records(rec, 6)
    keys = ["k0", "k1", "k2", "k3", "k4", "k5"]
    b, a = tmp_path / "before", tmp_path / "after"
    u = ["u0", "u1", "u2", "u3", "u4", "u5"] if unit else None
    write_dump(b, "src", keys, ["", "", "", "", "", ""], u, rec)
    # row 1: key changes, row 2: only the unit key, row 3: only warnings, rows 0, 4, 5 unchanged
    a_u = ["u0", "u1x", "u2x", "u3", "u4", "u5"] if unit else None
    write_dump(
        a,
        "src",
        ["k0", "k1x", "k2", "k3", "k4", "k5"],
        ["", "", "", "W", "", ""],
        a_u,
        rec,
    )
    return b, a


def test_changed_rows_are_classified_by_the_first_difference(tmp_path):
    b, a = setup(tmp_path)
    rows, _ = changed_queue.changed_rows(b, a)
    assert sorted((r[2], r[3]) for r in rows) == [
        (1, "key"),
        (2, "unit"),
        (3, "warnings"),
    ]


def test_without_unit_columns_a_unit_only_change_is_not_seen(tmp_path):
    b, a = setup(tmp_path, unit=False)
    rows, _ = changed_queue.changed_rows(b, a)
    assert sorted((r[2], r[3]) for r in rows) == [(1, "key"), (3, "warnings")]


def test_draw_is_seeded_capped_and_in_turns():
    rows = [("big", "m", i, "key") for i in range(30)] + [
        ("small", "m", i, "warnings") for i in range(5)
    ]
    got = changed_queue.draw(rows, 10, 0.5, seed=2)
    assert len(got) == 10 and got == changed_queue.draw(rows, 10, 0.5, seed=2)
    assert sum(r[0] == "big" for r in got) == 5
    assert sorted(r[2] for r in changed_queue.draw(rows[:2], 10, 0.5, seed=1)) == [0, 1]


def test_main_writes_cards_with_fields_and_the_earlier_reading(
    tmp_path, monkeypatch, capsys
):
    b, a = setup(tmp_path)
    monkeypatch.setattr(changed_queue, "ROOT", tmp_path)
    out = tmp_path / "local-data" / "q"
    args = [
        str(b),
        str(a),
        "--name",
        "t",
        "--label",
        "v1",
        "--n",
        "5",
        "--max-source-share",
        "1.0",
        "--out-dir",
        str(out),
    ]
    assert changed_queue.main(args) == 0
    assert not out.exists()  # dry run
    assert changed_queue.main([*args, "--confirm"]) == 0
    cards = [
        json.loads(line) for line in (out / "queue-t.jsonl").read_text().splitlines()
    ]
    assert len(cards) == 3
    c = next(c for c in cards if c["record_id"] == "1")
    assert (
        c["line1"] == "1 OAK ST"
        and c["alt"]["key"] == "k1"
        and c["alt"]["label"] == "v1"
    )
    assert (
        c["cluster"]["shape"] == "changed since v1: key" and c["cluster"]["size"] == 3
    )
    printed = capsys.readouterr().out
    assert "OAK" not in printed  # counts only


def test_out_dir_outside_local_data_is_refused(tmp_path, monkeypatch):
    b, a = setup(tmp_path)
    monkeypatch.setattr(changed_queue, "ROOT", tmp_path)
    with pytest.raises(SystemExit):
        changed_queue.main(
            [str(b), str(a), "--name", "t", "--out-dir", str(tmp_path / "elsewhere")]
        )
