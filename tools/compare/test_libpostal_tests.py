"""Tests for tools/compare/libpostal_tests.py on invented cases (issue 215, step 4). pytest tools/compare/test_libpostal_tests.py"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import libpostal_tests as T

C_SOURCE = r'''
TEST test_ca_parses(void) {
    CHECK_CALL(test_parse_result_equals("1 Elm St, Toronto", options, 1, (labeled_component_t){"road", "elm st"}));
    PASS();
}

TEST test_us_parses(void) {
    libpostal_address_parser_options_t options = libpostal_get_address_parser_default_options();

    CHECK_CALL(test_parse_result_equals(
        "Example Org 12 Main St, Apt 4, Springfield, N.Y., 12345",
        options,
        6,
        (labeled_component_t){"house", "example org"},
        (labeled_component_t){"house_number", "12"},
        (labeled_component_t){"road", "main st"},
        (labeled_component_t){"unit", "apt 4"},
        (labeled_component_t){"city", "springfield"},
        (labeled_component_t){"state", "n.y."}
    ));

    CHECK_CALL(test_parse_result_equals(
        // A comment line between the arguments, as in libpostal's file
        "5 Oak Ave, Dayton OH",
        options,
        3,
        (labeled_component_t){"house_number", "5"},
        (labeled_component_t){"road", "oak ave"},
        (labeled_component_t){"city", "dayton"}
    ));

    CHECK_CALL(test_parse_result_equals(
        "7 \"Quoted\" Way Brooklyn 11201",
        options,
        4,
        (labeled_component_t){"house_number", "7"},
        (labeled_component_t){"road", "\"quoted\" way"},
        (labeled_component_t){"city_district", "brooklyn"},
        (labeled_component_t){"postcode", "11201"}
    ));
    PASS();
}

TEST test_gb_parses(void) {
    CHECK_CALL(test_parse_result_equals("9 Rose Rd London", options, 1, (labeled_component_t){"road", "rose rd"}));
    PASS();
}
'''


def test_only_the_us_block_is_read_and_c_escapes_are_undone():
    cases = T.us_cases(C_SOURCE)
    assert len(cases) == 3
    assert cases[0][0] == "Example Org 12 Main St, Apt 4, Springfield, N.Y., 12345"
    assert cases[0][1][2] == ("road", "main st") and len(cases[0][1]) == 6
    assert cases[2][0] == '7 "Quoted" Way Brooklyn 11201' and cases[2][1][1] == ("road", '"quoted" way')
    assert cases[1][0] == "5 Oak Ave, Dayton OH"  # the comment line did not hide the case


def test_gold_fields_and_an_ordered_place():
    g = T.gold_from_components(T.us_cases(C_SOURCE)[0][1])
    assert g["number"] == ["12"] and g["road"] == ["main st"] and g["unit"] == ["apt 4"] and g["state"] == ["n.y."]
    assert g["zip"] == []  # the case declares no postcode: nothing is demanded
    assert T.place_ok("brooklyn new york", ["new york", "brooklyn"], "7 Elm St, Brooklyn, New York")  # joined in input order
    assert T.place_ok("brooklyn", ["new york", "brooklyn"], "7 Elm St Brooklyn New York")  # any one gold place
    assert not T.place_ok("queens", ["brooklyn"], "7 Elm St Queens")


def parse_stub(text):
    class P:
        state = {"new york": "NY", "n y": "NY", "ny": "NY"}.get(T.norm(text.split(",")[-1]))

    return P()


def test_a_row_is_right_when_every_gold_field_is_right_and_extra_fields_are_ignored():
    gold = T.gold_from_components(T.us_cases(C_SOURCE)[0][1])
    text = "Example Org 12 Main St, Apt 4, Springfield, N.Y., 12345"
    good = {"number": "12", "road": "main st", "place": "springfield", "state": "ny", "zip": "99999", "unit": "apt 4"}
    assert T.score_row(good, gold, text, parse_stub) == []  # the zip is extra: the gold has none
    bad = dict(good, road="main", unit="")
    assert T.score_row(bad, gold, text, parse_stub) == ["road", "unit"]
    assert T.score_row(dict(good, state="nj"), gold, text, parse_stub) == ["state"]


def test_the_three_parsers_are_reduced_to_the_same_fields():
    tags = [("12", "AddressNumber"), ("Main", "StreetName"), ("St", "StreetNamePostType"), ("Apt", "OccupancyType"), ("4", "OccupancyIdentifier"),
            ("Springfield", "PlaceName"), ("IL", "StateName"), ("62701", "ZipCode")]  # fmt: skip
    a = T.from_tags(tags)
    b = T.from_libpostal([["12", "house_number"], ["main st", "road"], ["apt 4", "unit"], ["springfield", "city"], ["il", "state"], ["62701", "postcode"]])
    assert a == b == {"number": "12", "road": "main st", "place": "springfield", "state": "il", "zip": "62701", "unit": "apt 4"}


def test_senzing_rows_become_gold_fields():
    row = {"house_number": "12", "road": "Main St", "suburb": "", "city_district": "Brooklyn", "city": "New York", "state": "NY", "postcode": "11201",
           "unit": "", "level": "3rd Floor", "staircase": "", "entrance": ""}  # fmt: skip
    g = T.gold_from_row(row)
    assert g["place"] == ["brooklyn", "new york"] and g["unit"] == ["3rd floor"] and g["zip"] == ["11201"]


def test_a_case_the_reader_cannot_parse_stops_the_run_instead_of_being_skipped():
    import pytest

    bad = 'TEST test_us_parses(void) {\n CHECK_CALL(test_parse_result_equals(WEIRD_MACRO("x"), options, 1, (labeled_component_t){"road", "x"}));\n}\n'
    with pytest.raises(SystemExit):
        T.us_cases(bad)


def test_c_escapes_are_undone():
    assert T.c_string(r"line one\nline two") == "line one\nline two"
    assert T.c_string(r'say \"hi\" \\ ok') == 'say "hi" \\ ok'
    assert T.c_string(r"keep \q") == r"keep \q"
