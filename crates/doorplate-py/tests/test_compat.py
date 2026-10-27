"""`doorplate.compat`, the usaddress-shaped module (#36). Addresses are invented. These tests
need no usaddress; `test_usaddress_compat.py` compares with it when it is installed."""
import doorplate
import doorplate.compat as usaddress
import pytest

TEXT = "123 N Main St Apt 4, Miami FL 33101"
TWO_UNITS = "123 Main St Apt 4 Apt 5, Miami FL 33101"


def test_parse_is_parse_tokens():
    assert usaddress.parse(TEXT) == doorplate.parse_tokens(TEXT)
    assert usaddress.parse(TEXT)[0] == ("123", "AddressNumber")


def test_tag_has_usaddress_shape():
    d, kind = usaddress.tag(TEXT)
    assert type(d).__name__ == "OrderedDict" and kind == "Street Address"
    assert list(d) == [
        "AddressNumber", "StreetNamePreDirectional", "StreetName", "StreetNamePostType",
        "OccupancyType", "OccupancyIdentifier", "PlaceName", "StateName", "ZipCode",
    ]
    assert d["OccupancyIdentifier"] == "4"
    assert usaddress.tag("PO Box 12, Tampa FL 33601")[1] == "PO Box"
    assert usaddress.tag("Tampa FL")[1] == "Ambiguous"


def test_blank_input_is_empty_not_an_error():
    for s in ("", "   ", "---"):
        assert usaddress.parse(s) == []
        d, kind = usaddress.tag(s)
        assert dict(d) == {} and kind == "Ambiguous"


def test_repeated_labels_join_by_default_and_raise_when_strict():
    d, _ = usaddress.tag(TWO_UNITS)
    assert d["OccupancyType"] == "Apt Apt" and d["OccupancyIdentifier"] == "4 5"
    with pytest.raises(usaddress.RepeatedLabelError) as e:
        usaddress.tag(TWO_UNITS, strict=True)
    err = e.value
    assert err.original_string == TWO_UNITS
    assert ("Main", "StreetName") in err.parsed_string
    assert err.repeated_label == "OccupancyType" and "OccupancyIdentifier" in err.repeated_labels
    assert "same label" in str(err) and err.message == str(err)
    usaddress.tag(TEXT, strict=True)  # nothing repeated: no error


def test_tag_mapping_renames_labels():
    d, _ = usaddress.tag(TEXT, {"StateName": "State", "ZipCode": "Zip"})
    assert d["State"] == "FL" and d["Zip"] == "33101" and "StateName" not in d
    # neighbours renamed to one name are joined, not an error, even when strict
    d, _ = usaddress.tag(TEXT, {"StateName": "Tail", "ZipCode": "Tail"}, strict=True)
    assert d["Tail"] == "FL 33101"
    # labels that are not neighbours are a repeat, as in usaddress
    with pytest.raises(usaddress.RepeatedLabelError):
        usaddress.tag(TEXT, {"AddressNumber": "X", "ZipCode": "X"}, strict=True)


def test_extras_default_state_and_layer(tmp_path):
    assert usaddress.parse("281 Evelyn Dr Dothan", default_state="AL") != usaddress.parse(
        "281 Evelyn Dr Dothan"
    )
    (tmp_path / "layer.toml").write_text('name = "t"\nversion = "1"\n')
    (tmp_path / "aliases.toml").write_text(
        '[[suffix]]\nabbr = "TRL"\nspellings = ["TRAYL"]\nevidence = "invented"\n'
    )
    d, _ = usaddress.tag("123 Oak Trayl, Miami FL 33101", custom_layer=tmp_path)
    assert d["StreetNamePostType"] == "Trayl"


def test_a_script_written_for_usaddress_runs_with_only_the_import_changed():
    src = '''
import usaddress
def run(lines):
    out = []
    for line in lines:
        try:
            d, kind = usaddress.tag(line)
        except usaddress.RepeatedLabelError:
            d, kind = {}, "error"
        out.append((dict(d).get("ZipCode"), kind, len(usaddress.parse(line))))
    return out
'''
    ns = {}
    exec(src.replace("import usaddress", "import doorplate.compat as usaddress"), ns)  # noqa: S102
    got = ns["run"]([TEXT, "PO Box 12, Tampa FL 33601", "", TWO_UNITS])
    assert got == [("33101", "Street Address", 9), ("33601", "PO Box", 6),
                   (None, "Ambiguous", 0), ("33101", "Street Address", 10)]
