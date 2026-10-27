"""Tests for the comparison mode (#132): compare_sample.py, the new verdicts and the export table. Invented rows.

    pytest tools/review
"""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("doorplate")
pytest.importorskip("duckdb")
pytest.importorskip("usaddress")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compare_sample as cs  # noqa: E402
import doorplate  # noqa: E402
import duckdb  # noqa: E402
import export  # noqa: E402
import server  # noqa: E402
import usaddress  # noqa: E402

LOCAL = cs.ROOT / "local-data"


def test_one_line_joins_like_the_harness():
    r = {"line1": "123  Oak St", "line2": "Apt 4", "city": "Miami", "state": "FL", "zip": "33101"}
    assert cs.one_line(r) == "123 Oak St, Apt 4, Miami, FL 33101"
    assert cs.one_line({"line1": "5 Elm Ave", "last_line": "Tampa FL 33601", "city": "x"}) == "5 Elm Ave, Tampa FL 33601"
    assert cs.one_line({"line1": "5 Elm Ave", "city": "Tampa"}) == "5 Elm Ave, Tampa"


def test_agreeing_strings_are_not_queued_and_a_disagreement_has_a_class_and_labels():
    assert cs.compare_string("123 N Main St Apt 4, Miami FL 33101", doorplate, usaddress) is None
    assert cs.compare_string("", doorplate, usaddress) is None
    r = cs.compare_string("ONE QUINCEWOOD PLAZA, Miami FL 33101", doorplate, usaddress)
    assert r["class"] in ("silent", "giveup", "control") and r["differs"]
    assert all(len(d) == 3 and isinstance(d[2], int) for d in r["differs"])
    assert [t for t, _ in r["theirs"]][:2] == ["ONE", "QUINCEWOOD"]
    # labels doorplate does not model are not scored: a recipient-only difference does not queue
    assert all(d[1] not in cs.cu.OUT_OF_SCOPE for d in r["differs"])


def found(cls, sig, rid):
    return {"class": cls, "sig": sig, "rid": rid}


def test_choose_fills_quotas_biggest_group_first_and_gives_spare_to_other_classes():
    rows = [found("silent", "A / B", i) for i in range(5)] + [found("silent", "C / D", 9)]
    rows += [found("giveup", "E / F", 20), found("control", "G / H", 30)]
    got = cs.choose(rows, limit=10, per_group=2, shares=(0.7, 0.2))
    assert [r["class"] for r in got] == ["silent"] * 3 + ["giveup", "control"]  # only that many rows exist
    assert [r["rid"] for r in got[:3]] == [0, 9, 1]  # the first row of each group, then the second of the big one
    assert got[0]["size"] == 5 and got[3]["size"] == 1
    # too few giveups: the spare quota goes to silent
    got = cs.choose([found("silent", f"S{i}", i) for i in range(20)], limit=10, per_group=1, shares=(0.5, 0.3))
    assert len(got) == 10 and {r["class"] for r in got} == {"silent"}


@pytest.fixture
def records(tmp_path):
    p = tmp_path / "records.parquet"
    con = duckdb.connect()
    con.execute("create table t (record_id varchar, source varchar, role varchar, provider varchar, line1 varchar, "
                "line2 varchar, city varchar, state varchar, zip varchar)")
    rows = [("ONE QUINCEWOOD PLAZA", None, "MIAMI", "FL", "33101")] * 2  # a repeat: queued once
    rows += [(f"{i} Oak St", None, "Miami", "FL", "33101") for i in range(10, 20)]
    rows += [("ONE ZEPHYRMILL PLAZA", None, "MIAMI", "FL", "33101")]
    con.executemany("insert into t values (?,?,?,?,?,?,?,?,?)", [(str(i), "inv", "site", "p", *r) for i, r in enumerate(rows)])
    con.execute(f"copy t to '{p}' (format parquet)")
    return p


def test_the_queue_is_written_under_local_data_with_the_comparison(records, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cs, "ROOT", tmp_path)
    out = tmp_path / "local-data" / "review" / "q.jsonl"
    assert cs.main([str(records), "--out", str(out)]) == 0
    assert "plan only" in capsys.readouterr().out and not out.exists()
    assert cs.main([str(records), "--out", str(out), "--confirm", "--limit", "5"]) == 0
    q = [json.loads(l) for l in out.read_text().splitlines()]
    assert q and all(e["id"].startswith("cmp|inv|site|") for e in q)
    inputs = [e["line1"] for e in q]
    assert len(inputs) == len(set(inputs))  # the repeated input once
    e = q[0]
    assert e["compare"]["class"] in ("silent", "giveup", "control") and e["compare"]["usaddress"]
    assert e["cluster"]["shape"] and e["cluster"]["size"] >= 1
    # the training exclusion drops a string
    ex = tmp_path / "train.txt"
    ex.write_text("one quincewood plaza, miami, fl 33101\n")
    out2 = tmp_path / "local-data" / "q2.jsonl"
    cs.main([str(records), "--out", str(out2), "--confirm", "--exclude-training", str(ex)])
    assert all("QUINCEWOOD" not in l for l in out2.read_text().splitlines())


def test_out_must_be_under_local_data_and_benchmarks_are_refused(records, tmp_path):
    with pytest.raises(SystemExit):
        cs.main([str(records), "--out", str(tmp_path / "q.jsonl")])
    bench = tmp_path / "benchsuite"
    bench.mkdir()
    (bench / "records.parquet").write_bytes(records.read_bytes())
    with pytest.raises(SystemExit) as e:
        cs.main([str(bench / "records.parquet"), "--out", str(LOCAL / "x.jsonl")])
    assert "real sources only" in str(e.value)


CQ = [{"seq": 1, "id": "cmp|inv|site|1", "source": "inv", "role": "site", "record_id": "1", "line1": "ONE QUINCEWOOD PLAZA",
       "city": "MIAMI", "state": "FL", "zip": "33101", "cluster": {"shape": "StreetName / BuildingName", "warnings": "", "size": 3},
       "compare": {"class": "silent", "differs": [["StreetName", "BuildingName", 2]],
                   "usaddress": [["ONE", "BuildingName"], ["QUINCEWOOD", "BuildingName"], ["PLAZA", "BuildingName"]]}},
      {"seq": 2, "id": "inv|site|2", "source": "inv", "role": "site", "record_id": "2", "line1": "5 OAK AVE",
       "cluster": {"shape": "9 a a", "warnings": "missing_zip", "size": 1}}]


def review_of(tmp_path):
    q = tmp_path / "queue.jsonl"
    q.write_text("".join(json.dumps(e) + "\n" for e in CQ))
    return server.Review(q, tmp_path / "answers.jsonl")


def test_comparison_verdicts_only_on_comparison_rows(tmp_path):
    r = review_of(tmp_path)
    rec = r.answer({"id": "cmp|inv|site|1", "verdict": "usaddress_right", "note": "n"})
    assert rec["verdict"] == "usaddress_right" and rec["compare"]["class"] == "silent"
    r.answer({"id": "cmp|inv|site|1", "verdict": "both_right"})
    with pytest.raises(ValueError):
        r.answer({"id": "cmp|inv|site|1", "verdict": "both_wrong"})  # needs the corrected string
    assert r.answer({"id": "cmp|inv|site|1", "verdict": "both_wrong", "corrected": "1 Quincewood Plaza"})["corrected"]
    with pytest.raises(ValueError):
        r.answer({"id": "cmp|inv|site|1", "verdict": "right", "warning": "fair"})  # a v1 verdict on a comparison row
    with pytest.raises(ValueError):
        r.answer({"id": "inv|site|2", "verdict": "usaddress_right"})  # a comparison verdict on a v1 row
    r.answer({"id": "cmp|inv|site|1", "verdict": "unclear"})  # the shared verdicts work on both


def test_export_keeps_labels_and_counts_never_values(tmp_path):
    r = review_of(tmp_path)
    r.answer({"id": "cmp|inv|site|1", "verdict": "usaddress_right", "note": "John Smith's plaza"})
    a = list(server.load_answers(tmp_path / "answers.jsonl").values())[0]
    out = export.safe(a)
    text = json.dumps(out)
    for s in ("QUINCEWOOD", "PLAZA", "MIAMI", "33101", "John", "Smith"):
        assert s not in text, s
    assert out["compare"] == {"class": "silent", "differs": [["StreetName", "BuildingName", 2]],
                              "usaddress_labels": ["BuildingName"] * 3}
    # a hand-edited answer cannot smuggle a value through the compare fields
    a["compare"]["differs"] = [["QUINCEWOOD ST", "x", 1]]
    a["compare"]["usaddress"] = [["a", "12 Oak St"]]
    assert export.safe(a)["compare"]["differs"] == [] and export.safe(a)["compare"]["usaddress_labels"] == []


def test_the_table_counts_who_was_right_by_label_pair(tmp_path):
    r = review_of(tmp_path)
    for v in ("usaddress_right", "both_right"):
        r.answer({"id": "cmp|inv|site|1", "verdict": v})
        a = list(server.load_answers(tmp_path / "answers.jsonl").values())
    text = export.compare_table(a)
    assert "| silent | StreetName / BuildingName | 1 |" in text
    assert "QUINCEWOOD" not in text
    assert export.compare_table([]) == "No comparison answers.\n"
