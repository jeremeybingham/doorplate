"""Tests for tools/ingest/inventory.py on invented folders (no private data)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inventory  # noqa: E402


def make(local):
    (local / "a-2026").mkdir(parents=True)
    (local / "a-2026" / "records.json").write_text(json.dumps({
        "source": "a", "rows": 30, "created_at": "2026-10-20T01:00:00+00:00", "commit": "abc1234",
        "roles": {"site": {"rows": 20}, "mail": {"rows": 10}}}))
    (local / "b-2026").mkdir()
    (local / "b-2026" / "records.json").write_text(json.dumps({"source": "b", "rows": 5, "roles": {"x": {"rows": 5}}}))
    runs = local / "netsyms-runs"
    for rid, started, rows, inp, marker in (
            ("old", "2026-10-19T00:00:00+00:00", 28, "a-2026/records.parquet", "DONE"),
            ("new", "2026-10-20T00:00:00+00:00", 30, "a-2026/records.parquet", "DONE"),
            ("test", "2026-10-20T00:00:00+00:00", 3, "a-2026/records.parquet", "LIMITED")):
        d = runs / rid
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({
            "run_id": rid, "started": started, "schema_version": 5,
            "input": {"path": str(local / inp), "kind": "records"}}))
        (d / marker).write_text(json.dumps({"rows": rows, "flagged": 3}))


def test_latest_complete_run_per_input_and_the_total(tmp_path):
    make(tmp_path)
    text = inventory.build(tmp_path, [])
    assert "| a | a-2026/records.parquet | 30 | site 20, mail 10 |" in text
    assert "**Total: 30 rows** in 1 inputs." in text  # the older run and the limited slice are not counted
    assert "| test | 2026-10-20 | a-2026/records.parquet | 5 | 3 | 100.0% | limited |" in text
    # A record file with no complete run is listed apart, and not counted.
    assert "b-2026/records.parquet (5)" in text


def test_exclude_leaves_a_run_out_of_the_total(tmp_path):
    make(tmp_path)
    text = inventory.build(tmp_path, ["a-2026"])
    assert "**Total: 0 rows** in 0 inputs." in text and "Left out by `--exclude`: a-2026/records.parquet." in text


def test_main_writes_the_file(tmp_path):
    make(tmp_path)
    assert inventory.main(["--local", str(tmp_path)]) == 0
    assert (tmp_path / "INVENTORY.md").read_text().startswith("# Inventory of local-data")
