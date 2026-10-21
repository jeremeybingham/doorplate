"""DuckDB: parse addresses in SQL, or from a relation.

    pip install "doorplate[duckdb]"
    python examples/duckdb_pipeline.py

`doorplate.duckdb.register` adds `doorplate_parse(text)` and
`doorplate_parse_fields(line1, line2, city, state, zip)` to a connection;
`parse_column` adds component columns to a relation without loading it into
memory. All addresses are invented. This library formats and parses; it does not
validate that an address exists or can receive mail.
"""
import argparse
from pathlib import Path

import duckdb

from doorplate import duckdb as dd

DATA = Path(__file__).parent / "data"


def main(out=None):
    con = duckdb.connect()
    dd.register(con, columns=["street_name", "city", "state", "zip5", "key", "warnings"])

    # 1. Parse a column in SQL. A struct field is read with `.name`; the row is
    #    parsed once however many fields you read.
    con.execute(
        "create table oneline as select * from read_csv(?, header=true, all_varchar=true)",
        [str(DATA / "addresses_oneline.csv")],
    )
    con.sql(
        "select id, doorplate_parse(address).street_name as street,"
        " doorplate_parse(address).key as key from oneline order by id::int"
    ).show()

    # 2. Rows with warnings.
    flagged = con.sql(
        "select count(*) from (select doorplate_parse(address).warnings w from oneline)"
        " where w <> ''"
    ).fetchall()[0][0]
    print(f"{flagged} row(s) with warnings")

    # 3. Pre-split columns.
    con.execute(
        "create table split as select * from read_csv(?, header=true, all_varchar=true)",
        [str(DATA / "addresses_split.csv")],
    )
    split = con.sql(
        "select id, doorplate_parse_fields(line1, line2, city, state, zip).key as key"
        " from split order by id::int"
    ).fetchall()
    print(split)

    # 4. A relation helper: the input columns plus parsed ones, still lazy.
    rel = dd.parse_column(
        con.table("oneline"), "address", columns=["street_name", "city", "state", "key"],
        connection=con,
    )
    print(rel.columns)
    if out:
        rel.write_csv(out)
        print(f"wrote {out}")
    return rel.fetchall()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the parsed table to this CSV")
    main(ap.parse_args().out)
