# ruff: noqa: UP031
"""Tests for the CSV reader, writer and helpers of the demo page (#335): site/demo/csv-core.js under
Node. Invented rows. Skipped when Node is not installed.

    pytest tools/docs/test_demo_csv.py
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[2] / "site" / "demo" / "csv-core.js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")


def js(expr):
    code = "const C = require(%s); console.log(JSON.stringify(%s));" % (
        json.dumps(str(CORE)),
        expr,
    )
    out = subprocess.run(
        ["node", "-e", code], capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out)


def read(text, delimiter=",", cuts=()):
    """Rows read from text, fed in pieces cut at the given offsets."""
    pieces, at = [], 0
    for c in list(cuts) + [len(text)]:
        pieces.append(text[at:c])
        at = c
    return js(
        "(function(){const r=new C.Reader(%s);const rows=[];for(const p of %s){rows.push(...r.push(p));}"
        "const e=r.end();if(e)rows.push(e);return rows;})()"
        % (json.dumps(delimiter), json.dumps(pieces))
    )


@node
def test_plain_rows_and_both_line_endings():
    assert read("a,b\n1,2\n") == [["a", "b"], ["1", "2"]]
    assert read("a,b\r\n1,2\r\n") == [["a", "b"], ["1", "2"]]
    assert read("a,b\r1,2") == [["a", "b"], ["1", "2"]]


@node
def test_quotes_commas_doubled_quotes_and_newlines_inside_a_field():
    text = 'id,addr\n1,"12 OAK ST, APT ""B""\nMIAMI FL"\n2,"x"\n'
    assert read(text) == [
        ["id", "addr"],
        ["1", '12 OAK ST, APT "B"\nMIAMI FL'],
        ["2", "x"],
    ]


@node
def test_empty_fields_and_a_last_row_with_no_newline():
    assert read("a,,c\n,,\nx,y,") == [["a", "", "c"], ["", "", ""], ["x", "y", ""]]
    assert read('a,"b"') == [["a", "b"]]
    assert read("") == []


@node
def test_a_chunk_boundary_anywhere_gives_the_same_rows():
    text = 'a,b,c\r\n1,"x, ""y""\nz",3\r\n"",4,5\n6,7,8'
    whole = read(text)
    for i in range(1, len(text)):
        assert read(text, cuts=[i]) == whole, i
    assert read(text, cuts=range(1, len(text))) == whole


@node
def test_other_delimiters_and_detection():
    assert read("a;b\n1;2", ";") == [["a", "b"], ["1", "2"]]
    assert read("a\tb\n1\t2", "\t") == [["a", "b"], ["1", "2"]]
    assert js('C.detectDelimiter("a;b;c\\n1,2,3")') == ";"
    assert js('C.detectDelimiter("a\\tb\\tc\\n")') == "\t"
    assert js('C.detectDelimiter("a|b|c\\n")') == "|"
    assert js('C.detectDelimiter("\\"a,b\\";c\\n")') == ";"
    assert js('C.detectDelimiter("single\\n")') == ","


@node
def test_writing_quotes_what_needs_it_and_round_trips():
    assert (
        js('C.formatRow(["a", "b,c", "d\\"e", "f\\ng", ""], ",")')
        == 'a,"b,c","d""e","f\ng",\n'
    )
    assert js('C.formatRow(["a;b", "c"], ";")') == '"a;b";c\n'
    row = ["x", "1,2", 'q"r', "line\nbreak", "", " pad "]
    text = js("C.formatRow(%s, ',')" % json.dumps(row))
    assert read(text) == [row]


@node
def test_the_formula_guard():
    assert js('C.guard("=1+1")') == "'=1+1"
    assert js('C.guard("@SUM(A1)")') == "'@SUM(A1)"
    assert js('C.guard("-5")') == "'-5"
    assert js('C.guard("k4:S|1|MAIN")') == "k4:S|1|MAIN"
    assert js('C.guard("")') == ""
    # In the user's own columns only text a spreadsheet would run counts; a number does not.
    assert js('C.looksLikeFormula("=A1")') is True
    assert js('C.looksLikeFormula("@x")') is True
    assert js('C.looksLikeFormula("-cmd")') is True
    assert js('C.looksLikeFormula("-5")') is False
    assert js('C.looksLikeFormula("+3.2")') is False
    assert js('C.looksLikeFormula("12 MAIN ST")') is False


@node
def test_column_guesses_from_headers():
    headers = ["id", "Name", "Street Address", "Address 2", "City", "State", "Zip Code"]
    assert js("C.guessColumn(%s, C.GUESS.line1)" % json.dumps(headers)) == 2
    assert js("C.guessColumn(%s, C.GUESS.line2)" % json.dumps(headers)) == 3
    assert js("C.guessColumn(%s, C.GUESS.city)" % json.dumps(headers)) == 4
    assert js("C.guessColumn(%s, C.GUESS.state)" % json.dumps(headers)) == 5
    assert js("C.guessColumn(%s, C.GUESS.zip)" % json.dumps(headers)) == 6
    assert (
        js(
            "C.guessColumn(%s, C.GUESS.address)"
            % json.dumps(["id", "full_address", "x"])
        )
        == 1
    )
    assert js("C.guessColumn(%s, C.GUESS.city)" % json.dumps(["a", "b"])) == -1
