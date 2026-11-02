"""Tests for the Try page's sample CSV (#434): `tools/docs/make_sample_csv.py` writes `site/demo/sample-addresses.csv`.

    pytest tools/docs/test_sample_csv.py

The rows are invented. The check that no row is in a real source runs against what the repository holds (the golden corpus and
the benchmark suite's inputs, which are public or built from public data) and, when `local-data/` exists on the machine, a count
over the private record files too (counts only, never rows). See `docs/data-policy.md`.
"""

import csv
import gzip
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "site" / "demo" / "sample-addresses.csv"


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def sample_rows():
    with open(SAMPLE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_the_committed_file_is_what_the_generator_writes():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "make_sample_csv", ROOT / "tools/docs/make_sample_csv.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert SAMPLE.read_text(encoding="utf-8") == mod.render()
    assert (
        mod.render() == mod.render()
    )  # a second call (a fresh seeded generator) gives the same file


def test_shape_of_the_file():
    rows = sample_rows()
    assert list(rows[0]) == ["id", "address"]
    assert 200 <= len(rows) <= 500
    assert len({r["id"] for r in rows}) == len(rows)
    assert len({norm(r["address"]) for r in rows}) == len(rows)
    assert all(r["address"].strip() for r in rows)
    text = " ".join(r["address"] for r in rows)
    for needle in ("PO Box", "RR ", "APO", "Apt", "Unit", "Highway", "-"):
        assert needle.lower() in text.lower(), needle


def corpus_addresses():
    out = set()
    for p in (ROOT / "tests" / "corpus").glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            f = rec.get("fields") or {}
            if rec.get("input"):
                out.add(norm(rec["input"]))
            if f:
                out.add(
                    norm(
                        " ".join(
                            str(f.get(k) or "")
                            for k in ("line1", "line2", "city", "state", "zip")
                        )
                    )
                )
    for p in (ROOT / "benchmarks" / "suite" / "v1").glob("*.jsonl.gz"):
        with gzip.open(p, "rt", encoding="utf-8") as g:
            for line in g:
                rec = json.loads(line)
                for text in [rec.get("input"), *(rec.get("inputs") or [])]:
                    if text:
                        out.add(norm(text))
    return out


def test_no_row_is_in_the_repositorys_corpora():
    seen = corpus_addresses()
    assert len(seen) > 1000
    hits = [r["id"] for r in sample_rows() if norm(r["address"]) in seen]
    assert not hits, hits


def test_no_street_line_is_in_the_private_sources():
    """A count only. Skipped without the machine's local-data and DuckDB."""
    duckdb = pytest.importorskip("duckdb")
    sources = ROOT / "local-data" / "keycompare" / "sources.txt"
    if not sources.exists():
        pytest.skip("no local-data on this machine")
    streets = {
        norm(r["address"].split(",")[0])
        for r in sample_rows()
        if not re.match(r"(?i)(p\.?o\.?|post office|rr|psc)", r["address"])
    }
    total = 0
    for line in sources.read_text().split():
        path = ROOT / line
        if not path.exists() or path.suffix != ".parquet":
            continue
        try:
            con = duckdb.connect()
            cols = [
                c[0]
                for c in con.execute(
                    f"describe select * from read_parquet('{path}')"
                ).fetchall()
            ]
            col = next((c for c in ("line1", "street", "address") if c in cols), None)
            if col is None:
                continue
            got = con.execute(
                f"select distinct {col} from read_parquet('{path}')"
            ).fetchall()
            total += sum(1 for (v,) in got if v is not None and norm(str(v)) in streets)
        except Exception as e:  # noqa: BLE001  (reader errors can quote rows: say only the type)
            pytest.fail(f"failed: {type(e).__name__}")
    assert total == 0, f"{total} street lines match a private source"
