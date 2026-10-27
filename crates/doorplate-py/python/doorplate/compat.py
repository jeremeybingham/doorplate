"""A usaddress-shaped module: change one import, keep the call sites.

    import doorplate.compat as usaddress

    usaddress.parse("123 Main St Apt 4, Miami FL 33101")   # [(token, label), ...]
    usaddress.tag("123 Main St Apt 4, Miami FL 33101")     # (OrderedDict, "Street Address")

This is label compatibility, not identical output. doorplate is rules plus data and
usaddress is a statistical model, so the two disagree at the edges; `docs/usaddress-compat.md`
("What differs") lists where. In short:

- `parse` keeps a token the parser did not place with the label `None` (usaddress labels
  every token). Intersections, landmarks, recipients and the like are not modeled.
- `tag` joins a label that appears in two runs (two units give `OccupancyType` `"Apt Apt"`)
  and `repeated_labels` of `doorplate.ParsedAddress` lists them; usaddress raises
  `RepeatedLabelError`. Pass `strict=True` to get the exception, so an existing
  `try/except RepeatedLabelError` keeps its meaning.
- Blank input gives `[]` and `({}, "Ambiguous")`, as in usaddress, not `ParseError`.
- Extras that usaddress does not have, keyword-only: `default_state` and `custom_layer`.

Not provided: `tokenize`, `TAGGER`, `LABELS` and the training helpers (there is no model).
This library formats and parses; it does not validate that an address exists or can receive mail.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ._core import ParseError, parse_tokens
from ._core import parse as _parse

if TYPE_CHECKING:
    from ._core import CustomLayer

__all__ = ["RepeatedLabelError", "parse", "tag"]


class RepeatedLabelError(Exception):
    """A label appears in two separate runs of tokens. Raised by `tag(..., strict=True)` only.

    Has the attributes of usaddress's exception: `original_string`, `parsed_string` (the
    `parse` result) and `message`; `repeated_label` and `repeated_labels` are extras.
    """

    def __init__(
        self,
        original_string: str,
        parsed_string: list[tuple[str, str | None]],
        repeated_labels: list[str],
    ) -> None:
        self.original_string = original_string
        self.parsed_string = parsed_string
        self.repeated_labels = repeated_labels
        self.repeated_label = repeated_labels[0] if repeated_labels else None
        self.message = (
            "Unable to tag this string because more than one area of the string has the "
            f"same label\n\nORIGINAL STRING:  {original_string}\n"
            f"PARSED TOKENS:    {parsed_string}\nUNCERTAIN LABEL:  {self.repeated_label}"
        )
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


def parse(
    address_string: str,
    *,
    default_state: str | None = None,
    custom_layer: "CustomLayer | str | os.PathLike[str] | None" = None,
) -> list[tuple[str, str | None]]:
    """`usaddress.parse`: `[(token, label)]`. A token the parser did not place has the
    label `None`. Blank input gives `[]`."""
    try:
        return parse_tokens(address_string, default_state, custom_layer)
    except ParseError:
        return []


def tag(
    address_string: str,
    tag_mapping: Mapping[str, str] | None = None,
    *,
    strict: bool = False,
    default_state: str | None = None,
    custom_layer: "CustomLayer | str | os.PathLike[str] | None" = None,
) -> tuple[OrderedDict[str, str], str]:
    """`usaddress.tag`: `(OrderedDict of label -> joined text, type)`, the type being
    `"Street Address"`, `"PO Box"` or `"Ambiguous"` (no `"Intersection"`: not modeled).

    `tag_mapping` renames labels as in usaddress. A label in two runs is joined, or with
    `strict=True` raises `RepeatedLabelError` (also when `tag_mapping` sends two labels to
    one name that are not neighbours, which is when usaddress raises). Blank input gives
    `({}, "Ambiguous")`.
    """
    try:
        a = _parse(address_string, default_state, custom_layer)
    except ParseError:
        return OrderedDict(), "Ambiguous"
    components, kind = a.tag()
    repeated = list(a.repeated_labels())
    out: OrderedDict[str, str] = OrderedDict()
    last = None
    for label, text in components.items():
        name = (tag_mapping.get(label) if tag_mapping else None) or label
        if name in out:  # two labels renamed to one: joined, and a repeat unless neighbours
            if name != last:
                repeated.append(name)
            out[name] = f"{out[name]} {text}".strip(" ,;")
        else:
            out[name] = text
        last = name
    if strict and repeated:
        raise RepeatedLabelError(
            address_string, parse_tokens(address_string, default_state, custom_layer), repeated
        )
    return out, kind
