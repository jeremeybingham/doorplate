"""Parse a CSV of addresses with Polars.

    pip install "doorplate[polars]"
    python examples/polars_pipeline.py [--out parsed.csv]

All addresses in examples/data are invented. This library formats and
parses; it does not validate that an address exists or can receive mail.
"""
import argparse
from pathlib import Path

import polars as pl

import doorplate as dp
from doorplate.polars import parse_column

DATA = Path(__file__).parent / "data"


def main(out: str | None = None) -> pl.DataFrame:
    # 1. One-line addresses in a single column.
    df = pl.read_csv(DATA / "addresses_oneline.csv")
    parsed = df.hstack(parse_column(df["address"]))
    print(parsed.select("id", "addr_street_number", "addr_street_name", "addr_city", "addr_state", "addr_zip5"))

    # 2. Keep what you need: pick columns, change the prefix, hint a state.
    small = parse_column(
        df["address"], columns=["key", "usps_line1", "usps_last_line"], prefix="", default_state="FL"
    )
    print(small.head(3))

    # 3. Find the rows that need a look: any warning, or text left over.
    check = parsed.filter(pl.col("addr_warnings").fill_null("") != "").select("id", "address", "addr_warnings")
    print(f"\n{check.height} row(s) with warnings:")
    print(check)

    # 4. Duplicates by match key (rows with no address text have no key).
    dupes = (
        parsed.filter(pl.col("addr_key").is_not_null())
        .group_by("addr_key")
        .len()
        .filter(pl.col("len") > 1)
    )
    print(f"{dupes.height} duplicated key(s)")

    # 5. Pre-split columns: parse_fields_many takes the columns as lists (nulls are None).
    split = pl.read_csv(DATA / "addresses_split.csv", infer_schema_length=0)
    rows = dp.parse_fields_many(
        line1=split["line1"].to_list(),
        line2=split["line2"].to_list(),
        city=split["city"].to_list(),
        state=split["state"].to_list(),
        zip=split["zip"].to_list(),
    )
    # 6. A display form for people (mixed case; not a Pub 28 form).
    display = [
        f"{d['line1'] or ''}, {d['last_line']}" if a and (d := a.to_display()) else None
        for a in rows
    ]
    print(
        split.hstack(
            pl.DataFrame(
                {
                    "addr_key": [a.key() if a else None for a in rows],
                    "addr_slug": [a.slug() if a else None for a in rows],
                    "addr_display": display,
                },
                schema={"addr_key": pl.String, "addr_slug": pl.String, "addr_display": pl.String},
            )
        )
    )
    print("display forms:", *display, sep="\n  ")

    if out:
        parsed.write_csv(out)
        print(f"wrote {out}")
    return parsed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the full parsed table to this CSV")
    main(ap.parse_args().out)
