"""DuckDB helper: parse addresses in SQL or from a relation.

Needs DuckDB and PyArrow (`pip install doorplate[duckdb]`); both are imported
when `register` or `parse_column` is called, not when this module is. This
library formats and parses; it does not validate that an address exists or can
receive mail.

`register(con)` adds two vectorized functions to a connection:

    SELECT doorplate_parse(address).street_name, doorplate_parse(address).key
    FROM addresses;

    SELECT doorplate_parse_fields(line1, line2, city, state, zip) FROM split;

Each returns a STRUCT of the chosen columns (the names in `AVAILABLE_COLUMNS`,
all VARCHAR), or NULL for a NULL or blank row or one with no address text.
DuckDB hands the function 2,048 rows at a time; each batch is parsed in
parallel by Rust with the GIL released.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from ._columns import (
    AVAILABLE_COLUMNS,
    DEFAULT_COLUMNS,
    check_columns,
    columns_of,
    extract_present,
)
from ._core import CustomLayer, load_layer, parse_fields_many

if TYPE_CHECKING:
    import os

    import duckdb

__all__ = ["AVAILABLE_COLUMNS", "DEFAULT_COLUMNS", "parse_column", "register"]


def _imports() -> Any:
    try:
        import pyarrow as pa  # noqa: F401
    except ImportError as e:  # pragma: no cover - exercised only without pyarrow
        raise ImportError(
            "doorplate.duckdb needs PyArrow: pip install 'doorplate[duckdb]'"
        ) from e
    try:
        import duckdb  # noqa: F401
    except ImportError as e:  # pragma: no cover - exercised only without duckdb
        raise ImportError(
            "doorplate.duckdb needs DuckDB: pip install 'doorplate[duckdb]'"
        ) from e
    return pa


def _struct(pa: Any, names: Sequence[str], parsed: Sequence[Any]) -> Any:
    """A StructArray of the columns; a row with no result is a NULL struct."""
    return _struct_of(pa, names, columns_of(parsed, names), [a is not None for a in parsed])


def _struct_of(pa: Any, names: Sequence[str], data: Any, present: Sequence[bool]) -> Any:
    arrays = [pa.array(data[n], type=pa.string()) for n in names]
    mask = pa.array([not p for p in present], type=pa.bool_())
    return pa.StructArray.from_arrays(arrays, names=list(names), mask=mask)


def _struct_type(names: Sequence[str]) -> str:
    return "STRUCT(" + ", ".join(f'"{n}" VARCHAR' for n in names) + ")"


def _layer(
    custom_layer: "CustomLayer | str | os.PathLike[str] | None",
) -> CustomLayer | None:
    """A layer object for a layer or a folder path, loaded once."""
    if custom_layer is None or isinstance(custom_layer, CustomLayer):
        return custom_layer
    return load_layer(custom_layer)


def register(
    con: "duckdb.DuckDBPyConnection",
    name: str = "doorplate_parse",
    *,
    columns: Sequence[str] | None = None,
    default_state: str | None = None,
    custom_layer: "CustomLayer | str | os.PathLike[str] | None" = None,
) -> None:
    """Register `name` and `name + "_fields"` on `con`.

    `name(text)` parses one-line addresses; `name_fields(line1, line2, city,
    state, zip)` parses pre-split fields (any argument may be NULL). Both
    return a STRUCT with one VARCHAR field per name in `columns` (default
    `DEFAULT_COLUMNS`), and NULL where there is no address text.
    `default_state` is the lookup hint of `doorplate.parse`; `custom_layer` is a
    `doorplate.CustomLayer` (or a layer folder's path, loaded once) used on top of the
    shipped tables. Registering a name
    twice on one connection is an error in DuckDB: use `con.remove_function`
    first to replace it.
    """
    pa = _imports()
    names = check_columns(columns)
    ret = _struct_type(names)
    layer = _layer(custom_layer)

    def parse_texts(values: Any) -> Any:
        _, data, present = extract_present(
            values.to_pylist(), names, default_state, layer
        )
        return _struct_of(pa, names, data, present)

    # DuckDB reads the parameter count from the signature, so no *args.
    def parse_split(line1: Any, line2: Any, city: Any, state: Any, zip: Any) -> Any:
        parsed = parse_fields_many(
            line1=line1.to_pylist(),
            line2=line2.to_pylist(),
            city=city.to_pylist(),
            state=state.to_pylist(),
            zip=zip.to_pylist(),
            default_state=default_state,
            custom_layer=layer,
        )
        return _struct(pa, names, parsed)

    con.create_function(
        name, parse_texts, ["VARCHAR"], ret, type="arrow", null_handling="special"
    )
    con.create_function(
        f"{name}_fields",
        parse_split,
        ["VARCHAR"] * 5,
        ret,
        type="arrow",
        null_handling="special",
    )


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def parse_column(
    relation: "duckdb.DuckDBPyRelation",
    column: str,
    *,
    columns: Sequence[str] | None = None,
    prefix: str = "addr_",
    default_state: str | None = None,
    custom_layer: "CustomLayer | str | os.PathLike[str] | None" = None,
    connection: "duckdb.DuckDBPyConnection | None" = None,
) -> "duckdb.DuckDBPyRelation":
    """Parse the one-line addresses in `relation`'s column `column`.

    Returns a relation with the input's columns plus one VARCHAR column per
    name in `columns`, each prefixed with `prefix`. A NULL, blank or
    no-address-text row is NULL in every new column. The relation stays lazy:
    nothing is parsed until it is executed or fetched, so it works on tables
    larger than memory. `connection` must be the connection the relation came
    from (default: DuckDB's default connection, which `duckdb.sql(...)` uses).
    """
    _imports()
    import duckdb

    names = check_columns(columns)
    if connection is not None:
        con = connection
    else:
        # An attribute in older DuckDB releases, a function in newer ones.
        default = duckdb.default_connection
        con = default() if callable(default) else default
    # One function per column choice, state hint and layer, registered once.
    layer = _layer(custom_layer)
    fn = f"_doorplate_parse_{abs(hash((names, default_state, layer.fingerprint if layer else None)))}"
    try:
        register(con, fn, columns=names, default_state=default_state, custom_layer=layer)
    except duckdb.NotImplementedException:  # already registered on this connection
        pass
    holder = "__doorplate_parsed"
    step = relation.project(f"*, {fn}({_quote(column)}) AS {holder}")
    fields = ", ".join(
        f"{holder}.{_quote(n)} AS {_quote(prefix + n)}" for n in names
    )
    return step.project(f"* EXCLUDE ({holder}), {fields}")
