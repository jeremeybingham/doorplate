"""Column extraction shared by the pandas, Polars and DuckDB helpers.

Neither library is imported here. `extract` parses a batch and builds the chosen
columns in Rust (`_parse_columns`); `columns_of` reads them off already parsed
results, for the pre-split path.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Sequence

from ._core import CustomLayer, ParsedAddress, _parse_columns

DEFAULT_COLUMNS: tuple[str, ...] = (
    "street_number",
    "street_dir_prefix",
    "street_name",
    "street_suffix",
    "street_dir_suffix",
    "unit_type",
    "unit_number",
    "city",
    "state",
    "zip5",
    "zip4",
    "address_type",
    "key",
    "slug",
    "warnings",
)

# Columns that are computed, not plain attributes. All values are strings or None.
_DERIVED: dict[str, Callable[[ParsedAddress], str | None]] = {
    "address_type": lambda a: a.address_type(),
    "key": lambda a: a.key(),
    "key_unit": lambda a: a.key(unit=True),
    "slug": lambda a: a.slug(),
    "warnings": lambda a: ",".join(a.warnings),
    "usps_line1": lambda a: a.to_usps()["line1"],
    "usps_line2": lambda a: a.to_usps()["line2"],
    "usps_last_line": lambda a: a.to_usps()["last_line"],
}

# Plain attributes that hold a string or None.
_ATTRIBUTES = frozenset(
    {
        "street_number",
        "street_dir_prefix",
        "street_name",
        "street_suffix",
        "street_dir_suffix",
        "unit_type",
        "unit_number",
        "second_unit_type",
        "second_unit_number",
        "po_box",
        "military_post_office",
        "attention",
        "building",
        "city",
        "state",
        "zip5",
        "zip4",
        "unparsed",
    }
)

AVAILABLE_COLUMNS: frozenset[str] = _ATTRIBUTES | frozenset(_DERIVED)


def check_columns(columns: Sequence[str] | None) -> tuple[str, ...]:
    """Validate a column choice; `None` means the defaults."""
    if columns is None:
        return DEFAULT_COLUMNS
    if isinstance(columns, str):
        raise TypeError("columns must be a list of names, not a single string")
    names = tuple(columns)
    unknown = [c for c in names if c not in AVAILABLE_COLUMNS]
    if unknown:
        raise ValueError(
            f"unknown column(s) {unknown}; available: {sorted(AVAILABLE_COLUMNS)}"
        )
    return names


def texts_of(values: Iterable[object]) -> list[str]:
    """Strings for `parse_many`: anything that is not a string (None, NaN,
    pandas NA) becomes "", which parses to no result."""
    return [v if isinstance(v, str) else "" for v in values]


def columns_of(
    parsed: Sequence[ParsedAddress | None], names: Sequence[str]
) -> dict[str, list[str | None]]:
    """One list per column name from already parsed results; a `None` result
    is `None` in every column."""
    out: dict[str, list[str | None]] = {}
    for name in names:
        if name in _DERIVED:
            get = _DERIVED[name]
            out[name] = [get(a) if a is not None else None for a in parsed]
        else:
            out[name] = [getattr(a, name) if a is not None else None for a in parsed]
    return out


def extract(
    values: Iterable[object],
    columns: Sequence[str] | None,
    default_state: str | None,
    custom_layer: "CustomLayer | str | os.PathLike[str] | None" = None,
) -> tuple[tuple[str, ...], dict[str, list[str | None]]]:
    """Parse `values` and return the column names and one list per column.
    A row with no address text is `None` in every column."""
    names, data, _ = extract_present(values, columns, default_state, custom_layer)
    return names, data


def extract_present(
    values: Iterable[object],
    columns: Sequence[str] | None,
    default_state: str | None,
    custom_layer: "CustomLayer | str | os.PathLike[str] | None" = None,
) -> tuple[tuple[str, ...], dict[str, list[str | None]], list[bool]]:
    """`extract`, plus a list that is False for a row with no result (all its
    columns are `None`, but so are those of a result that has none of them).
    The columns are built in Rust, without a Python object per row."""
    names = check_columns(columns)
    lists, present = _parse_columns(
        texts_of(values), list(names), default_state, custom_layer
    )
    return names, dict(zip(names, lists)), present
