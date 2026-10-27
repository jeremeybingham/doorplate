"""`doorplate.duckdb`: the SQL functions and `parse_column` give what
`parse_many` / `parse_fields_many` give, blank rows are NULL, order is kept,
and each row is parsed once. Skips when DuckDB or PyArrow is not installed."""
import pytest

import doorplate as uap
from doorplate import _columns

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
dd = pytest.importorskip("doorplate.duckdb")

TEXTS = [
    "123 N Main St Apt 4, Miami FL 33101",
    "",
    "PO Box 12, Tampa FL 33601",
    "!!!",
    "281 EVELYN DR DOTHAN",
    None,
]
BLANK_ROWS = {1, 3, 5}


@pytest.fixture
def con():
    c = duckdb.connect()
    dd.register(c)
    c.execute("create table t (id integer, address varchar)")
    c.executemany("insert into t values (?, ?)", list(enumerate(TEXTS)))
    return c


def test_sql_function_matches_parse_many(con):
    rows = con.sql(
        "select doorplate_parse(address).street_name, doorplate_parse(address).key,"
        " doorplate_parse(address).warnings from t order by id"
    ).fetchall()
    _, data = _columns.extract(TEXTS, ["street_name", "key", "warnings"], None)
    assert rows == list(zip(data["street_name"], data["key"], data["warnings"]))
    assert all(rows[i] == (None, None, None) for i in BLANK_ROWS)
    assert rows[0][0] == "MAIN"


def test_whole_struct_is_null_for_blank_rows(con):
    got = con.sql("select doorplate_parse(address) is null from t order by id").fetchall()
    assert [g[0] for g in got] == [i in BLANK_ROWS for i in range(len(TEXTS))]


def test_columns_and_default_state():
    c = duckdb.connect()
    dd.register(c, "p", columns=["city", "state"], default_state="AL")
    got = c.sql("select p('281 Evelyn Dr Dothan')").fetchall()[0][0]
    a = uap.parse("281 Evelyn Dr Dothan", default_state="AL")
    assert got == {"city": a.city, "state": a.state}
    with pytest.raises(ValueError, match="unknown column"):
        dd.register(c, "q", columns=["nope"])


def test_fields_function_matches_parse_fields_many():
    c = duckdb.connect()
    dd.register(c)
    rows = c.sql(
        "select doorplate_parse_fields(line1, line2, city, state, zip).key,"
        " doorplate_parse_fields(line1, line2, city, state, zip).slug from (values"
        " ('412 N HARBOR ST', 'APT 3B', 'TAMPA', 'FL', '33602'),"
        " ('PO BOX 4821', NULL, 'JACKSONVILLE', 'FL', '32201'),"
        " (NULL, NULL, NULL, NULL, NULL)) v(line1, line2, city, state, zip)"
    ).fetchall()
    many = uap.parse_fields_many(
        line1=["412 N HARBOR ST", "PO BOX 4821", None],
        line2=["APT 3B", None, None],
        city=["TAMPA", "JACKSONVILLE", None],
        state=["FL", "FL", None],
        zip=["33602", "32201", None],
    )
    assert rows == [(a.key(), a.slug()) if a else (None, None) for a in many]
    assert rows[2] == (None, None)


def test_parse_column_keeps_columns_and_order(con):
    rel = dd.parse_column(
        con.table("t"), "address", columns=["street_name", "key"], connection=con
    )
    assert rel.columns == ["id", "address", "addr_street_name", "addr_key"]
    rows = sorted(rel.fetchall())
    _, data = _columns.extract(TEXTS, ["street_name", "key"], None)
    assert [r[2] for r in rows] == data["street_name"]
    assert [r[3] for r in rows] == data["key"]
    assert all(rows[i][2] is None and rows[i][3] is None for i in BLANK_ROWS)


def test_parse_column_prefix_and_defaults(con):
    rel = dd.parse_column(con.table("t"), "address", prefix="", connection=con)
    # "key" would collide with nothing here; the defaults are all present.
    assert rel.columns == ["id", "address", *dd.DEFAULT_COLUMNS]
    # Calling it twice on one connection reuses the registered function.
    dd.parse_column(con.table("t"), "address", prefix="x_", connection=con).fetchall()


def test_parse_column_uses_the_default_connection():
    rel = duckdb.sql("select '123 N Main St, Miami FL 33101' as a")
    out = dd.parse_column(rel, "a", columns=["street_name"]).fetchall()
    assert out == [("123 N Main St, Miami FL 33101", "MAIN")]


def test_each_row_is_parsed_once(monkeypatch):
    seen = []
    real = _columns._parse_columns
    monkeypatch.setattr(
        _columns, "_parse_columns", lambda t, *a: (seen.append(len(t)), real(t, *a))[1]
    )
    c = duckdb.connect()
    dd.register(c)
    c.execute("create table big as select '123 N Main St, Miami FL 33101' a from range(5000)")
    c.sql(
        "select doorplate_parse(a).street_name, doorplate_parse(a).key,"
        " doorplate_parse(a).slug from big"
    ).fetchall()
    assert sum(seen) == 5000
    seen.clear()
    dd.parse_column(c.table("big"), "a", connection=c).fetchall()
    assert sum(seen) == 5000  # not once per output column


def test_many_rows_match_parse_many():
    c = duckdb.connect()
    dd.register(c, columns=["key"])
    n = 5000
    texts = [f"{i} N Main St Apt {i % 7}, Miami FL 33101" for i in range(n)]
    c.execute("create table big (i integer, a varchar)")
    c.executemany("insert into big values (?, ?)", list(enumerate(texts)))
    got = [r[0] for r in c.sql("select doorplate_parse(a).key from big order by i").fetchall()]
    assert got == [a.key() for a in uap.parse_many(texts)]
