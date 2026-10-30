"""`key_diff.py diff` on two tiny invented dumps, counts only (pytest tools/compare)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

SCRIPT = Path(__file__).with_name("key_diff.py")


def dump(tmp_path, name, key):
    d = tmp_path / name
    d.mkdir()
    duckdb.sql(
        f"copy (select 0::bigint as rn, 'r' as role, '1' as record_id, '{key}' as key, '' as warnings) "
        f"to '{d / 'demo.parquet'}' (format parquet)"
    )
    (d / "demo.json").write_text(json.dumps({"source": "demo", "doorplate": name, "rows": 1}))
    return d


def test_diff_counts_a_changed_key_and_prints_only_its_shape(tmp_path):
    a = dump(tmp_path, "a", "k3:S|1||MAIN|ST||FL|33101")
    b = dump(tmp_path, "b", "k3:S|1||MAIN|AVE||FL|33101")
    r = subprocess.run([sys.executable, str(SCRIPT), "diff", str(a), str(b)], capture_output=True, text=True)
    assert r.returncode == 1, r.stderr  # a changed key is a non-zero exit
    assert "key changed        1" in r.stdout
    assert "a9:a|9||aaaa|aa||aa|99999" in r.stdout
    assert "MAIN" not in r.stdout


def test_diff_of_equal_dumps_exits_zero(tmp_path):
    a = dump(tmp_path, "a", "k3:S|1||MAIN|ST||FL|33101")
    b = dump(tmp_path, "b", "k3:S|1||MAIN|ST||FL|33101")
    r = subprocess.run([sys.executable, str(SCRIPT), "diff", str(a), str(b)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "total rows with a changed key: 0" in r.stdout


def test_diff_header_names_each_build_by_version_and_commit(tmp_path):
    a = dump(tmp_path, "a", "k3:S|1||MAIN|ST||FL|33101")
    b = dump(tmp_path, "b", "k3:S|1||MAIN|ST||FL|33101")
    meta = json.loads((b / "demo.json").read_text())
    (b / "demo.json").write_text(json.dumps(dict(meta, commit="abc1234+dirty")))
    r = subprocess.run([sys.executable, str(SCRIPT), "diff", str(a), str(b)], capture_output=True, text=True)
    assert "a (commit unknown) -> b (abc1234+dirty)" in r.stdout  # a dump from before the commit was recorded still compares


def unit_dump(tmp_path, name, key_unit, unit_number, second_unit_number):
    d = tmp_path / name
    d.mkdir()
    sec_type = "NULL" if second_unit_number is None else "'APT'"
    sec = "NULL" if second_unit_number is None else f"'{second_unit_number}'"
    unit = "NULL" if unit_number is None else f"'{unit_number}'"
    duckdb.sql(
        "copy (select 0::bigint as rn, 'r' as role, '1' as record_id, 'k3:S|410||ELM|ST||NC|27601' as key, '' as warnings, "
        f"'{key_unit}' as key_unit, NULL::varchar as unit_type, {unit}::varchar as unit_number, "
        f"{sec_type}::varchar as second_unit_type, {sec}::varchar as second_unit_number) to '{d / 'demo.parquet'}' (format parquet)"
    )
    (d / "demo.json").write_text(json.dumps({"source": "demo", "doorplate": name, "rows": 1}))
    return d


def test_diff_sees_a_unit_that_moves_slots_with_no_property_key_change(tmp_path):
    before = unit_dump(tmp_path, "a", "k3:S|410||ELM|ST||NC|27601||4", None, "4")
    after = unit_dump(tmp_path, "b", "k3:S|410||ELM|ST||NC|27601|4|", "4", None)
    r = subprocess.run([sys.executable, str(SCRIPT), "diff", str(before), str(after)], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr  # the unit-level key changed
    assert "key changed        0" in r.stdout
    assert "unit key changed        1" in r.stdout
    assert "first unit changed        1" in r.stdout and "second unit changed        1" in r.stdout
    assert "ELM" not in r.stdout


def test_diff_of_equal_unit_dumps_exits_zero(tmp_path):
    a = unit_dump(tmp_path, "a", "k3:S|410||ELM|ST||NC|27601|4|", "4", None)
    b = unit_dump(tmp_path, "b", "k3:S|410||ELM|ST||NC|27601|4|", "4", None)
    r = subprocess.run([sys.executable, str(SCRIPT), "diff", str(a), str(b)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unit key changed        0" in r.stdout


def test_a_dump_without_unit_columns_still_diffs(tmp_path):
    a = dump(tmp_path, "a", "k3:S|1||MAIN|ST||FL|33101")
    b = unit_dump(tmp_path, "b", "k3:S|1||MAIN|ST||FL|33101||", None, None)
    r = subprocess.run([sys.executable, str(SCRIPT), "diff", str(a), str(b)], capture_output=True, text=True)
    assert "unit level" not in r.stdout  # one side has no unit columns


def test_dump_all_runs_dump_for_each_listed_file(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPT.parent))
    import key_diff

    sources = tmp_path / "sources.txt"
    sources.write_text("# comment\na/records.parquet\n\nb/records.parquet\n")
    seen = []
    monkeypatch.setattr(key_diff, "dump", lambda args: seen.append((args.records, args.out, args.unit)))
    monkeypatch.setattr(sys, "argv", ["key_diff.py", "dump-all", "--out", "o", "--sources", str(sources), "--unit"])
    key_diff.main()
    assert seen == [("a/records.parquet", "o", True), ("b/records.parquet", "o", True)]
