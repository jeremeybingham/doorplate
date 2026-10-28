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
