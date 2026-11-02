"""Tests for tools/review/probe_queue.py on invented rows (no private data).

pytest tools/review
"""

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tools" / "harness"))

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
pytest.importorskip("doorplate")
pytest.importorskip("usaddress")

import probe_queue
import probe_scan


def records(path, source, n, prefix):
    duckdb.sql(
        f"copy (select '{prefix}' || i::varchar as record_id, '{source}' as source, 'a' as role, "
        "(100 + i)::varchar || ' NO ' || chr(cast(65 + (i % 20) as integer)) || 'ELM AVE' as line1, "
        "NULL as line2, 'MIAMI' as city, 'FL' as state, '33101' as zip "
        f"from range(1, {n + 1}) t(i)) to '{path}' (format parquet)"
    )


@pytest.fixture
def scan(tmp_path):
    records(tmp_path / "big.parquet", "big", 200, "b")
    records(tmp_path / "small.parquet", "small", 12, "s")
    lst = tmp_path / "inputs.txt"
    lst.write_text(f"{tmp_path / 'big.parquet'}\n{tmp_path / 'small.parquet'}\n")
    argv = [str(lst), "--out-root", str(tmp_path), "--run-id", "scan", "--chunk-rows", "50", "--workers", "2",
            "--skip-coverage", "--min-free-gb", "0", "--confirm"]
    assert probe_scan.main(argv) == 0
    return tmp_path / "scan", lst


def test_pick_alternates_sources_caps_the_share_then_fills():
    cands = [(0, "big", "a", str(i), i / 100, False) for i in range(30)] + [(1, "small", "a", str(i), i / 100, False) for i in range(3)]
    got = probe_queue.pick(cands, 10, 0.4)
    assert len(got) == 33 and len({id(c) for c in got}) == 33
    assert [c[1] for c in got[:7]] == ["big", "small", "big", "small", "big", "small", "big"]
    assert [c[4] for c in got[7:]] == sorted(c[4] for c in got[7:])


def test_a_queue_holds_matches_from_each_source_with_text_read_back(scan, tmp_path):
    run, lst = scan
    out = tmp_path / "q"
    argv = [str(run), str(lst), "--probe", "no-for-north", "--n", "10", "--out-dir", str(out),
            "--exclude-answers", str(tmp_path / "none*.jsonl"), "--confirm"]
    assert probe_queue.main(argv) == 0
    cards = [json.loads(line) for line in (out / "queue-no-for-north.jsonl").read_text().splitlines()]
    assert len(cards) == 10 and len({c["id"] for c in cards}) == 10
    assert {c["source"] for c in cards} == {"big", "small"}
    assert sum(1 for c in cards if c["source"] == "small") >= 4
    assert all(" NO " in c["line1"] and c["cluster"]["shape"] == "probe no-for-north" for c in cards)
    assert all("compare" in c and "usaddress" in c["compare"] for c in cards)
    assert cards[0]["cluster"]["size"] == 212


def test_answered_ids_are_skipped_and_a_dry_run_writes_nothing(scan, tmp_path, capsys):
    run, lst = scan
    out = tmp_path / "q"
    assert probe_queue.main([str(run), str(lst), "--probe", "no-for-north", "--out-dir", str(out)]) == 0
    assert "Dry run" in capsys.readouterr().out and not out.exists()
    first = tmp_path / "answers-x.jsonl"
    argv = [str(run), str(lst), "--probe", "no-for-north", "--n", "5", "--out-dir", str(out), "--exclude-answers", str(first), "--confirm"]
    first.write_text("")
    assert probe_queue.main(argv) == 0
    ids = {json.loads(line)["id"] for line in (out / "queue-no-for-north.jsonl").read_text().splitlines()}
    first.write_text("".join(json.dumps({"id": i}) + "\n" for i in ids))
    assert probe_queue.main(argv) == 0
    again = {json.loads(line)["id"] for line in (out / "queue-no-for-north.jsonl").read_text().splitlines()}
    assert again and not again & ids


def test_an_unknown_probe_is_refused(scan):
    run, lst = scan
    with pytest.raises(SystemExit):
        probe_queue.main([str(run), str(lst), "--probe", "no-such-probe"])
