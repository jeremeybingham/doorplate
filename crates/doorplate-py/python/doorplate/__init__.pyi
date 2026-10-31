"""Type stubs for doorplate (the compiled module is `_core`)."""
import os
from collections.abc import Sequence
from typing import TypedDict

__version__: str

class ParseError(ValueError):
    """The input has no address text at all (empty or only punctuation)."""

class Highway(TypedDict):
    """A street named after a highway (`KY STATE HIGHWAY 625`)."""

    state: str | None
    prefix: str
    route: str
    name: str

class RuralRoute(TypedDict):
    """`RR 2 BOX 15` or `HC 3 BOX 4`."""

    kind: str
    route: str
    box: str | None

class Military(TypedDict):
    """`PSC 1650 BOX 10`."""

    kind: str
    number: str
    box: str | None

class Place(TypedDict):
    """The place the city stands for (`city` itself is never changed)."""

    name: str
    state: str
    county: str
    kind: str  # "municipality" | "place" | "subdivision"
    source: str  # "name" | "variant" | "completed" | "zip"

class Usps(TypedDict):
    """The USPS Publication 28 form (`ParsedAddress.to_usps`)."""

    line1: str | None
    line2: str | None
    city: str | None
    state: str | None
    zip: str | None
    last_line: str

class Display(TypedDict):
    """The display and long forms (`ParsedAddress.to_display`, `to_long`)."""

    line1: str | None
    city: str | None
    state: str | None
    zip: str | None
    last_line: str

class LayerInfoDict(TypedDict):
    """The custom layer a parse used: its name, version and content fingerprint."""

    name: str
    version: str
    fingerprint: str

class Provenance(TypedDict):
    """Which release, which state data and which custom layer produced the result."""

    library_version: str
    state_data_version: str | None
    custom_layer: LayerInfoDict | None

class ParsedAddressDict(TypedDict):
    """Everything `ParsedAddress.to_dict()` returns."""

    input: str
    street_number: str | None
    street_dir_prefix: str | None
    street_name: str | None
    street_suffix: str | None
    street_dir_suffix: str | None
    highway: Highway | None
    unit_type: str | None
    unit_number: str | None
    second_unit_type: str | None
    second_unit_number: str | None
    po_box: str | None
    rural_route: RuralRoute | None
    general_delivery: bool
    military: Military | None
    military_post_office: str | None
    attention: str | None
    building: str | None
    city: str | None
    state: str | None
    zip5: str | None
    zip4: str | None
    place: Place | None
    warnings: list[str]
    unparsed: str | None
    address_type: str
    key: str | None
    key_unit: str | None
    slug: str | None
    usps: Usps
    reso: dict[str, str]
    provenance: Provenance

class ParsedAddress:
    """A parsed address. Read-only. Formats and parses; it does not validate
    that the address exists or can receive mail."""

    @property
    def input(self) -> str:
        """The input as given (for fields, the non-empty fields joined with `, `)."""
    @property
    def street_number(self) -> str | None:
        """The house number, as written (`123`, `123A`, `12-14`), or `None`."""
    @property
    def street_dir_prefix(self) -> str | None:
        """Directional before the street name, as its USPS abbreviation (`N`, `SW`)."""
    @property
    def street_name(self) -> str | None:
        """The street name without its suffix or directionals (`MAIN`)."""
    @property
    def street_suffix(self) -> str | None:
        """Street suffix, as its USPS abbreviation (`ST`, `AVE`)."""
    @property
    def street_dir_suffix(self) -> str | None:
        """Directional after the street name or suffix, as its USPS abbreviation."""
    @property
    def highway(self) -> Highway | None:
        """A street named after a highway: `{state, prefix, route, name}`, or `None`."""
    @property
    def unit_type(self) -> str | None:
        """The unit designator as its USPS abbreviation (`APT`, `STE`), or `None`."""
    @property
    def unit_number(self) -> str | None:
        """The unit value (`4`, `B`), or `None`."""
    @property
    def second_unit_type(self) -> str | None:
        """A second unit designator, when the line has two (`APT 5 RM 2`)."""
    @property
    def second_unit_number(self) -> str | None:
        """The second unit's value."""
    @property
    def po_box(self) -> str | None:
        """The PO box number, or `None`."""
    @property
    def rural_route(self) -> RuralRoute | None:
        """`{kind: "RR" | "HC", route, box}`, or `None`."""
    @property
    def general_delivery(self) -> bool:
        """True for a `GENERAL DELIVERY` address."""
    @property
    def military(self) -> Military | None:
        """`{kind: "CPR" | "OPC" | "PSC" | "UPR" | "UNIT", number, box}`, or `None`."""
    @property
    def military_post_office(self) -> str | None:
        """`APO`, `FPO` or `DPO` where the city goes."""
    @property
    def attention(self) -> str | None:
        """An attention or care-of line (`ATTN JANE DOE`), when line 2 was one."""
    @property
    def building(self) -> str | None:
        """A building name that was on its own line."""
    @property
    def city(self) -> str | None:
        """The city as the input wrote it (upper case). It is never changed; see `place`."""
    @property
    def state(self) -> str | None:
        """Two-letter USPS state code."""
    @property
    def zip5(self) -> str | None:
        """The five-digit ZIP."""
    @property
    def zip4(self) -> str | None:
        """The four-digit ZIP+4 extension."""
    @property
    def place(self) -> Place | None:
        """The place the city stands for: `{name, state, county, kind, source}`, or `None`. `city` is never changed."""
    @property
    def warnings(self) -> list[str]:
        """Warning codes (`"missing_zip"`, ...), in the order they were raised. What each means is on the Warnings page."""
    @property
    def unparsed(self) -> str | None:
        """Text the parse could not place, or `None`."""
    @property
    def library_version(self) -> str:
        """The doorplate version that produced the result."""
    @property
    def state_data_version(self) -> str | None:
        """The version of the curated data for the address's state, or `None`."""
    @property
    def custom_layer(self) -> LayerInfoDict | None:
        """The custom layer the parse used, as `{name, version, fingerprint}`, or `None`. A layer can change a key: keep the fingerprint with stored keys."""
    def address_type(self) -> str:
        """`street`, `po_box`, `rural_route`, `military`, `general_delivery`, `dual` or `unknown`."""
    def key(self, unit: bool = False) -> str | None:
        """The match key (`k4:...`), or `None` when there is nothing to key on. With `unit=True` the unit numbers are part of it."""
    def slug(self) -> str | None:
        """A URL-safe label, for display only. Use `key()` for identity."""
    def to_usps(self, max_line: int | None = None) -> Usps:
        """The USPS Publication 28 form: `{line1, line2, city, state, zip, last_line}`. With `max_line`, a unit that does not fit on `line1` moves to `line2`."""
    def to_display(self) -> Display:
        """Mixed case with Pub 28 abbreviations, `123 N Main St Apt 4`, for showing to people. Not a Pub 28 form (see `to_usps`)."""
    def to_long(self) -> Display:
        """Mixed case with directionals, suffixes and units spelled out, `123 North Main Street Apartment 4`. Same keys as `to_display`."""
    def to_reso(self) -> dict[str, str]:
        """RESO Data Dictionary 2.0 fields by name; a field with no value is left out."""
    def to_usaddress_tags(self) -> list[tuple[str, str | None]]:
        """Every input token with the label usaddress would give it: `[(token, label)]`; `label` is `None` for a token the parse did not place."""
    def tag(self) -> tuple[dict[str, str], str]:
        """The counterpart of `usaddress.tag()`: `(dict, address_type)` with usaddress's label names and its three type names. It never raises `RepeatedLabelError`: the runs are joined and `repeated_labels()` lists the labels."""
    def repeated_labels(self) -> list[str]:
        """The labels `tag()` joined from separate runs (two units give `OccupancyType`); empty when none."""
    def to_dict(self) -> ParsedAddressDict:
        """Everything as plain Python values: the components (absent ones are `None`), `warnings`, `unparsed`, `place`, `address_type`, `key`, `key_unit`, `slug`, `usps`, `reso` and `provenance`."""

class Anonymized:
    """An obfuscated text and whether the parser reads it like the original."""

    text: str
    faithful: bool

class Anonymizer:
    """Shape-preserving obfuscation of address-like text: digits and unknown words are replaced
    by others of the same length and case; suffixes, directionals, unit designators, states, the
    city and the first three ZIP digits stay. Obfuscation, not anonymity: read the output
    before you share it."""

    def __init__(self, seed: int | None = None) -> None:
        """`seed=None` picks a random seed; a published seed lets anyone check a guess."""
    @property
    def seed(self) -> int:
        """The seed in use; pass it to `Anonymizer(seed)` to repeat the output."""
    def anonymize(self, text: str) -> Anonymized:
        """Obfuscate one text. `faithful` says whether the parser reads the result like the original."""
    def anonymize_many(self, texts: Sequence[str]) -> list[Anonymized]:
        """A batch; the same value gets the same replacement across it. Releases the GIL."""

def anonymize(text: str, seed: int | None = None) -> str:
    """Obfuscate one text with a new random seed (or `seed`). Returns the text only."""

class LayerError(ValueError):
    """A custom layer that cannot be loaded; the message lists every problem."""

class CustomLayer:
    """A loaded custom layer: your own spellings, words, places and ZIPs on top of the shipped
    tables. A layer can change a key: keep `fingerprint` with stored keys."""

    @property
    def name(self) -> str:
        """The layer's name, from `layer.toml`."""
    @property
    def version(self) -> str:
        """The layer's version, from `layer.toml`."""
    @property
    def fingerprint(self) -> str:
        """16 hex digits over the layer's files; it changes when any byte changes."""
    def counts(self) -> dict[str, int]:
        """What the layer holds, as `{what: count}` (what is empty is left out)."""

def load_layer(path: str | os.PathLike[str]) -> CustomLayer:
    """Load a custom layer from a folder (`layer.toml` and any of `aliases.toml`, `overrides.toml`, `places.tsv`, `zips.tsv`). Raises `LayerError` listing every problem."""

class Parser:
    """An address parser with settings. Cheap to construct and thread-safe."""

    def __init__(
        self,
        default_state: str | None = None,
        custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
    ) -> None:
        """`default_state` (a USPS code or a state name) is a hint for lookups when the input names no state: it never fills `state`. Raises `ValueError` for anything that is not a US state, DC or territory. `custom_layer` is a `CustomLayer` or a folder path."""
    def parse(self, text: str) -> ParsedAddress:
        """Parse one address string. Raises `ParseError` only when there is no address text at all; anything else comes back with warnings."""
    def parse_fields(
        self,
        line1: str | None = None,
        line2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        zip: str | None = None,
    ) -> ParsedAddress:
        """Parse pre-split fields."""
    def parse_many(self, texts: Sequence[str]) -> list[ParsedAddress | None]:
        """Parse a batch. The GIL is released while Rust parses (in parallel). An element with no address text gives `None`."""
    def parse_fields_many(
        self,
        line1: Sequence[str | None] | None = None,
        line2: Sequence[str | None] | None = None,
        city: Sequence[str | None] | None = None,
        state: Sequence[str | None] | None = None,
        zip: Sequence[str | None] | None = None,
    ) -> list[ParsedAddress | None]:
        """Parse a batch of pre-split addresses given as columns: each of `line1`, `line2`, `city`, `state` and `zip` is a sequence (an element may be `None`) or omitted, and the given columns must have the same length. The GIL is released while Rust parses (in parallel). An element with no address text gives `None`."""

def parse(
    text: str,
    default_state: str | None = None,
    custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
) -> ParsedAddress:
    """Parse one address string (see `Parser.parse`)."""
def parse_fields(
    line1: str | None = None,
    line2: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
    default_state: str | None = None,
    custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
) -> ParsedAddress:
    """Parse pre-split fields (see `Parser.parse_fields`)."""
def parse_many(
    texts: Sequence[str],
    default_state: str | None = None,
    custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
) -> list[ParsedAddress | None]:
    """Parse a batch (see `Parser.parse_many`)."""
def parse_fields_many(
    line1: Sequence[str | None] | None = None,
    line2: Sequence[str | None] | None = None,
    city: Sequence[str | None] | None = None,
    state: Sequence[str | None] | None = None,
    zip: Sequence[str | None] | None = None,
    default_state: str | None = None,
    custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
) -> list[ParsedAddress | None]:
    """Parse a batch of pre-split addresses (see `Parser.parse_fields_many`)."""
def tag(
    text: str,
    default_state: str | None = None,
    custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
) -> tuple[dict[str, str], str]:
    """The counterpart of `usaddress.tag()`: `(dict, address_type)`."""
def parse_tokens(
    text: str,
    default_state: str | None = None,
    custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
) -> list[tuple[str, str | None]]:
    """The counterpart of `usaddress.parse()`: `[(token, label)]`."""
def address_type(
    text: str,
    default_state: str | None = None,
    custom_layer: CustomLayer | str | os.PathLike[str] | None = None,
) -> str:
    """The kind of address in `text`: `street`, `po_box`, `rural_route`, `military`, `general_delivery`, `dual` or `unknown`."""
