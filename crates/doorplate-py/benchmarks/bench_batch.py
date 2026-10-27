"""Time `parse_many` against a Python loop of `parse`.

    maturin develop --release        # in crates/doorplate-py
    python crates/doorplate-py/benchmarks/bench_batch.py [N]

The input is the golden corpus's single-line addresses (tests/corpus),
repeated to N (default 100,000). Each timing is the best of three runs. With
`to_dict`, the Python objects are turned into dicts too. The last rows build
a pandas and a polars DataFrame of seven chosen columns from the parsed
addresses (the README recipes), then `parse_column` (15 default columns, built in
Rust since #24), and the last two time the DuckDB functions (`doorplate.duckdb`) over a table, when those libraries are installed.
"""
import json
import os
import pathlib
import sys
import time

import doorplate as dp

ROOT = pathlib.Path(__file__).resolve().parents[3]


def corpus_inputs():
    out = []
    for path in sorted((ROOT / "tests" / "corpus").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                s = json.loads(line).get("input")
                if s:
                    out.append(s)
    return out


def best(fn, runs=3):
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    return min(times)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    base = corpus_inputs()
    texts = (base * (n // len(base) + 1))[:n]
    print(f"{n} addresses ({len(base)} distinct), {len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count()} CPUs, "
          f"library {dp.__version__}")
    rows = [
        ("loop of parse", lambda: [dp.parse(s) for s in texts]),
        ("parse_many", lambda: dp.parse_many(texts)),
        ("loop of parse + to_dict", lambda: [dp.parse(s).to_dict() for s in texts]),
        ("parse_many + to_dict", lambda: [a.to_dict() for a in dp.parse_many(texts) if a]),
    ]
    cols = ["street_number", "street_name", "street_suffix", "unit_number",
            "city", "state", "zip5"]
    try:
        import pandas as pd

        rows.append((
            "parse_many -> pandas",
            lambda: pd.DataFrame(
                [{c: getattr(a, c) for c in cols} if a else {}
                 for a in dp.parse_many(texts)]
            ),
        ))
        from doorplate.pandas import parse_column as pd_parse_column

        pd_series = pd.Series(texts)
        rows.append(("pandas parse_column, 15", lambda: pd_parse_column(pd_series)))
    except ImportError:
        pass
    try:
        import polars as pl

        def to_polars():
            parsed = dp.parse_many(texts)
            return pl.DataFrame(
                {c: [getattr(a, c) if a else None for a in parsed] for c in cols},
                schema={c: pl.String for c in cols},
            )

        rows.append(("parse_many -> polars", to_polars))
        from doorplate.polars import parse_column as pl_parse_column

        series = pl.Series(texts)
        rows.append(("polars parse_column, 15", lambda: pl_parse_column(series)))
    except ImportError:
        pass
    try:
        import duckdb

        from doorplate import duckdb as dd

        con = duckdb.connect()
        con.execute("create table addr (a varchar)")
        con.executemany("insert into addr values (?)", [(s,) for s in texts])
        dd.register(con, "p_all")
        dd.register(con, "p_cols", columns=cols)
        rows.append((
            "duckdb, 15 columns",
            lambda: con.sql("select p_all(a).key from addr").fetchall(),
        ))
        rows.append((
            "duckdb, 7 columns",
            lambda: con.sql("select p_cols(a).zip5 from addr").fetchall(),
        ))
    except ImportError:
        pass
    base_t = None
    for name, fn in rows:
        t = best(fn)
        base_t = base_t or t
        print(f"{name:26} {t:7.3f} s  {n / t:10,.0f} addresses/s  {base_t / t:5.1f}x")


if __name__ == "__main__":
    main()
