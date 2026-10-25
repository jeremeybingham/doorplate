"""The examples in `examples/` run and give sensible output, so they stay
current. Each test skips when its library (pandas, Polars, nbclient) is not
installed."""
import runpy
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


def run_script(name):
    return runpy.run_path(str(EXAMPLES / name), run_name="example")["main"]()


def test_pandas_pipeline(capsys):
    pytest.importorskip("pandas")
    df = run_script("pandas_pipeline.py")
    assert len(df) == 12
    assert df.loc[0, "addr_street_name"] == "HARBOR"
    assert df["addr_key"].isna().sum() == 1  # the row with no address text
    out = capsys.readouterr().out
    assert "row(s) with warnings" in out
    assert "412 N Harbor St Apt 3B, Tampa FL 33602" in out  # to_display, via parse_fields_many


def test_polars_pipeline(capsys):
    pytest.importorskip("polars")
    df = run_script("polars_pipeline.py")
    assert df.height == 12
    assert df["addr_street_name"][0] == "HARBOR"
    assert df["addr_key"].null_count() == 1
    out = capsys.readouterr().out
    assert "row(s) with warnings" in out
    assert "412 N Harbor St Apt 3B, Tampa FL 33602" in out  # to_display, via parse_fields_many


def test_duckdb_pipeline(capsys):
    pytest.importorskip("duckdb")
    pytest.importorskip("pyarrow")
    rows = run_script("duckdb_pipeline.py")
    assert len(rows) == 12
    out = capsys.readouterr().out
    assert "k3:S|412|N|HARBOR|ST||FL|33602" in out
    assert "row(s) with warnings" in out
    assert [r[0] for r in rows].count(None) == 0  # the id column is kept


def test_notebook_executes():
    pytest.importorskip("pandas")
    pytest.importorskip("polars")
    pytest.importorskip("duckdb")
    pytest.importorskip("pyarrow")
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    pytest.importorskip("ipykernel")
    nb = nbformat.read(EXAMPLES / "quickstart.ipynb", as_version=4)
    nbclient.NotebookClient(
        nb, timeout=120, resources={"metadata": {"path": str(EXAMPLES)}}
    ).execute()
    text = "".join(
        o.get("text", "") for c in nb.cells if c.cell_type == "code" for o in c.outputs
    )
    assert "k3:S|123|N|MAIN|ST||FL|33101" in text
    assert "intersection_detected" in text
    assert "123 N Main St Apt 4" in text  # to_display
    assert "123 North Main Street Apartment 4" in text  # to_long
    assert "100 Northeast 5th Avenue Southwest" in text
    assert "k3:R|RR|2|152|MO|65801" in text  # rare shapes
    assert "PENSACOLA" in text  # place data, from a ZIP
    assert "k3:S|412|N|HARBOR|ST||FL|33602" in text  # Polars, DuckDB and pandas sections
    assert "'StreetNamePostType'" in text  # usaddress-style labels
    assert "parse_fields_many" in "".join(
        "".join(c.source) for c in nb.cells if c.cell_type == "code"
    )


@pytest.mark.parametrize("name", ["addresses_oneline.csv", "addresses_split.csv", "addresses_messy.txt"])
def test_data_files_exist(name):
    assert (EXAMPLES / "data" / name).stat().st_size > 0
