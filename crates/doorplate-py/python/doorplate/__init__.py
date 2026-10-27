"""Parse US addresses into components.

USPS Publication 28 and RESO output, a match key and a slug, with
diagnostics. This library formats and parses; it does not validate that an
address exists or can receive mail.
"""
from ._core import (
    Anonymized,
    Anonymizer,
    CustomLayer,
    LayerError,
    ParsedAddress,
    ParseError,
    Parser,
    __version__,
    address_type,
    anonymize,
    load_layer,
    parse,
    parse_fields,
    parse_fields_many,
    parse_many,
    parse_tokens,
    tag,
)

__all__ = [
    "Anonymized",
    "Anonymizer",
    "CustomLayer",
    "LayerError",
    "ParseError",
    "ParsedAddress",
    "Parser",
    "__version__",
    "address_type",
    "anonymize",
    "load_layer",
    "parse",
    "parse_fields",
    "parse_fields_many",
    "parse_many",
    "parse_tokens",
    "tag",
]
