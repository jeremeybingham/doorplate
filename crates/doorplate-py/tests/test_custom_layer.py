"""Custom layers (#3) from Python. Every spelling and address here is invented."""
from pathlib import Path

import pytest

import doorplate

LAYER = 'name = "county"\nversion = "7"\n'
ALIASES = (
    '[[suffix]]\nabbr = "TRL"\nspellings = ["TRAYL"]\nevidence = "invented for the test"\n'
)
TEXT = "123 Oak Trayl, Miami, FL 33101"


@pytest.fixture
def layer_dir(tmp_path):
    (tmp_path / "layer.toml").write_text(LAYER)
    (tmp_path / "aliases.toml").write_text(ALIASES)
    (tmp_path / "places.tsv").write_text(
        "state\tname\tevidence\nFL\tQUINCEWOOD HEIGHTS\tinvented for the test\n"
    )
    return tmp_path


def test_load_layer_describes_itself(layer_dir):
    layer = doorplate.load_layer(layer_dir)
    assert (layer.name, layer.version) == ("county", "7")
    assert len(layer.fingerprint) == 16
    assert layer.counts() == {"suffix spellings": 1, "places": 1}
    assert "county 7" in repr(layer)
    assert doorplate.load_layer(str(layer_dir)) == layer  # the same content is the same layer


def test_a_layer_changes_the_parse_and_is_reported(layer_dir):
    layer = doorplate.load_layer(layer_dir)
    base = doorplate.parse(TEXT)
    assert base.street_suffix is None and base.custom_layer is None
    a = doorplate.parse(TEXT, custom_layer=layer)
    assert a.street_suffix == "TRL"
    assert a.custom_layer == {
        "name": "county",
        "version": "7",
        "fingerprint": layer.fingerprint,
    }
    assert a.to_dict()["provenance"]["custom_layer"] == a.custom_layer
    assert base.to_dict()["provenance"]["custom_layer"] is None
    assert a.key() != base.key()


def test_a_path_works_wherever_a_layer_does(layer_dir):
    assert doorplate.Parser(custom_layer=layer_dir).parse(TEXT).street_suffix == "TRL"
    assert doorplate.parse(TEXT, custom_layer=str(layer_dir)).street_suffix == "TRL"
    assert doorplate.address_type(TEXT, custom_layer=layer_dir) == "street"
    assert "StreetNamePostType" in doorplate.tag(TEXT, custom_layer=layer_dir)[0]
    assert "StreetNamePostType" not in doorplate.tag(TEXT)[0]
    rows = doorplate.parse_many([TEXT, ""], custom_layer=layer_dir)
    assert rows[0].street_suffix == "TRL" and rows[1] is None
    f = doorplate.parse_fields_many(
        line1=["123 Oak Trayl"], city=["Miami"], state=["FL"], custom_layer=layer_dir
    )
    assert f[0].street_suffix == "TRL"
    p = doorplate.parse_fields(line1="123 Oak Trayl", city="Miami", state="FL", custom_layer=layer_dir)
    assert p.street_suffix == "TRL"
    assert doorplate.parse_tokens(TEXT, custom_layer=layer_dir)


def test_default_state_and_a_layer_together(layer_dir):
    p = doorplate.Parser(default_state="FL", custom_layer=layer_dir)
    assert p.parse("123 Oak Trayl, Quincewood Heights").street_suffix == "TRL"


def test_a_bad_layer_raises_layererror_listing_every_problem(tmp_path):
    (tmp_path / "layer.toml").write_text(LAYER)
    (tmp_path / "aliases.toml").write_text(
        '[[suffix]]\nabbr = "TRL"\nspellings = ["ST"]\nevidence = "x"\n'
        '[[unit]]\nabbr = "NOPE"\nspellings = ["AA"]\nevidence = "x"\n'
    )
    with pytest.raises(doorplate.LayerError) as e:
        doorplate.load_layer(tmp_path)
    msg = str(e.value)
    assert msg.startswith("the custom layer has 2 problems")
    assert "already in the shipped tables" in msg and "NOPE" in msg
    assert isinstance(e.value, ValueError)
    with pytest.raises(doorplate.LayerError):
        doorplate.Parser(custom_layer=tmp_path / "missing")
    with pytest.raises(TypeError):
        doorplate.Parser(custom_layer=42)


def test_dataframe_helpers_take_a_layer(layer_dir):
    pd = pytest.importorskip("pandas")
    pl = pytest.importorskip("polars")
    from doorplate.pandas import parse_column as pd_parse
    from doorplate.polars import parse_column as pl_parse

    out = pd_parse(pd.Series([TEXT]), columns=["street_suffix"], custom_layer=layer_dir)
    assert out["addr_street_suffix"].tolist() == ["TRL"]
    out = pl_parse(pl.Series([TEXT]), columns=["street_suffix"], custom_layer=layer_dir)
    assert out["addr_street_suffix"].to_list() == ["TRL"]


def test_duckdb_takes_a_layer(layer_dir):
    duckdb = pytest.importorskip("duckdb")
    pytest.importorskip("pyarrow")
    from doorplate.duckdb import parse_column, register

    con = duckdb.connect()
    register(con, custom_layer=layer_dir)
    con.execute(f"create table t as select '{TEXT}' as a")
    assert con.sql("select doorplate_parse(a).street_suffix from t").fetchall() == [("TRL",)]
    rel = parse_column(con.table("t"), "a", columns=["street_suffix"], custom_layer=layer_dir, connection=con)
    assert rel.fetchall()[0][-1] == "TRL"


# ---- the demo layer, the template and the guide's prompt (part 4) ----
ROOT = Path(__file__).resolve().parents[3]
LAYERS = ROOT / "examples" / "layers"


def test_the_demo_layer_loads_and_changes_what_it_says():
    layer = doorplate.load_layer(LAYERS / "riverbend-demo")
    assert layer.name == "riverbend-demo"
    assert layer.counts()["places"] == 2 and layer.counts()["ZIPs"] == 1
    text = "120 Fern Hollow Trayl, Fern Holow, WA 98991"
    base, a = doorplate.parse(text), doorplate.parse(text, custom_layer=layer)
    assert base.street_suffix is None and base.place is None
    assert a.street_suffix == "TRL" and a.place["name"] == "FERN HOLLOW"
    assert a.key() == "k3:S|120||FERN HOLLOW|TRL||WA|98991"
    assert "non_standard_abbreviation" in a.warnings
    lane = doorplate.parse("5 Pine Lanne, Lantrn Port, WA", custom_layer=layer)
    assert lane.street_suffix == "LN" and "non_standard_abbreviation" not in lane.warnings  # kind = "variant"
    unit = doorplate.parse("88 Nrth Lantern Rd Sute 4, Lantern Port WA 98991", custom_layer=layer)
    assert (unit.street_dir_prefix, unit.unit_type, unit.unit_number) == ("N", "STE", "4")
    assert doorplate.parse("9 Oak St 98991 Riverbend Territory", custom_layer=layer).place["name"] == "LANTERN PORT"


def test_the_template_loads_with_every_table_used():
    layer = doorplate.load_layer(LAYERS / "template")
    assert layer.name == "my-layer"
    counts = layer.counts()
    for key in ("suffix spellings", "unit spellings", "directional spellings", "state spellings",
                "special-word spellings", "highway spellings", "state suffix readings", "words",
                "places", "ZIPs"):
        assert counts[key] == 1, key


def test_the_guides_prompt_names_every_table_and_word_list():
    text = (ROOT / "docs" / "custom-layers.md").read_text()
    prompt = text[text.index("````text"):text.index("````\n", text.index("````text") + 8)]
    for table in ("suffix", "unit", "directional", "state", "special", "highway", "words"):
        assert f"[[{table}]]" in prompt, table
    for word in ("building", "area", "city_head", "non_recipient", "numbered_street",
                 "placeholder", "country", "place_prefix",
                 "po_box", "rural_route", "highway_contract", "general_delivery", "attention",
                 "municipality", "subdivision", "overrides.toml", "places.tsv", "zips.tsv", "layer.toml"):
        assert word in prompt, word
