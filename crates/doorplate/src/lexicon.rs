//! Lexicon lookups: street suffixes, directionals, secondary unit
//! designators, states, and special address forms.
//!
//! All lexicon access goes through [`Lexicons`]. The tables are compiled from
//! `data/*.toml` by `build.rs` into sorted static arrays, so lookups are a
//! key normalization plus a binary search, with no runtime data loading.
//!
//! `Lexicons` is the one interface the tagger reads through. State data plugs
//! in here: it adds spellings that resolve to the same Pub 28 entries, so
//! the value types keep pointing at the base tables.

mod key;
mod place_key;

pub use key::normalize_key;
use key::normalize_key_cow;

use std::collections::HashSet;

use crate::layer::{CustomLayer, Layer, LayerInfo};
use crate::types::{
    Directional, MilitaryKind, MilitaryPostOffice, Place, PlaceKind, StateCode, StateKind,
    StreetSuffix, UnitType,
};

/// How a looked-up spelling relates to its table entry.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum MatchKind {
    /// The standard abbreviation or code itself ("AVE", "STE", "FL", "N").
    Standard,
    /// The full name ("AVENUE", "SUITE", "FLORIDA", "NORTH").
    FullName,
    /// Another spelling the source table lists ("AVNUE", "FLA" for states,
    /// "P O BOX").
    Variant,
    /// A spelling seen in real data that the Pub 28 table does not list
    /// ("TRC" for TRCE). Callers should report
    /// [`crate::Warning::NonStandardAbbreviation`].
    Observed,
}

/// A lexicon hit: the entry plus how the input spelled it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Lookup<T> {
    pub value: T,
    pub kind: MatchKind,
}

/// Non-street address words from `data/special.toml`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum Special {
    /// PO BOX (and synonyms such as DRAWER, CALLER).
    PoBox,
    /// The BOX word inside rural route and highway contract addresses.
    Box,
    /// Rural route: RR.
    RuralRoute,
    /// Highway contract route: HC.
    HighwayContract,
    /// GENERAL DELIVERY.
    GeneralDelivery,
    /// An attention or care-of word: ATTN, C/O.
    Attention,
}

impl Special {
    /// The standard form, as emitted.
    pub const fn standard(self) -> &'static str {
        match self {
            Special::PoBox => "PO BOX",
            Special::Box => "BOX",
            Special::RuralRoute => "RR",
            Special::HighwayContract => "HC",
            Special::GeneralDelivery => "GENERAL DELIVERY",
            Special::Attention => "ATTN",
        }
    }
}

/// A highway prefix such as COUNTY ROAD or US HIGHWAY; the route number that
/// follows it is part of the street name.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct HighwayPrefix {
    standard: &'static str,
}

impl HighwayPrefix {
    /// The standard form: `"COUNTY ROAD"`.
    pub fn standard(&self) -> &'static str {
        self.standard
    }
}

// Rows of the generated tables.
struct SuffixRow {
    name: &'static str,
    abbr: &'static str,
}

struct UnitRow {
    name: &'static str,
    abbr: &'static str,
    range_required: bool,
}

struct StateRow {
    code: &'static str,
    name: &'static str,
    kind: StateKind,
}

mod tables {
    use super::{MatchKind, Special, StateKind, StateRow, SuffixRow, UnitRow};
    use crate::types::{Directional, MilitaryKind, MilitaryPostOffice};

    include!(concat!(env!("OUT_DIR"), "/lexicon_tables.rs"));
}

pub use tables::{MAX_FORM_WORDS, MAX_PLACE_WORDS};

// The place tables are packed binary files written by build.rs (see
// `emit_places` there for the layout), so a lookup is a binary search over
// byte records with no pointers to relocate. Every read is bounds-checked and
// a malformed table gives `None`, never a panic.

const ROW_LEN: usize = 9;
const KEY_LEN: usize = 10;
const ZIP_LEN: usize = 9;

fn le32(b: &[u8], at: usize) -> Option<u32> {
    Some(u32::from_le_bytes(
        b.get(at..at.checked_add(4)?)?.try_into().ok()?,
    ))
}

/// The `n`th `len`-byte record of a packed table.
fn record(table: &'static [u8], len: usize, n: usize) -> Option<&'static [u8]> {
    let start = n.checked_mul(len)?;
    table.get(start..start.checked_add(len)?)
}

fn pool_str(pool: &'static str, off: u32, len: u8) -> Option<&'static str> {
    let start = usize::try_from(off).ok()?;
    pool.get(start..start.checked_add(usize::from(len))?)
}

fn place_row(i: u32) -> Option<Place> {
    let r = record(tables::PLACE_ROWS, ROW_LEN, usize::try_from(i).ok()?)?;
    let county = usize::from(u16::from_le_bytes([*r.get(7)?, *r.get(8)?]));
    Some(Place {
        state: tables::PLACE_STATES.get(usize::from(*r.get(5)?))?,
        name: pool_str(tables::PLACE_POOL, le32(r, 0)?, *r.get(4)?)?,
        county: match county {
            0 => "",
            n => tables::PLACE_COUNTIES.get(n - 1)?,
        },
        kind: match r.get(6)? {
            0 => PlaceKind::Municipality,
            1 => PlaceKind::Place,
            _ => PlaceKind::Subdivision,
        },
    })
}

/// Binary search over `n` sorted records: `cmp(i)` orders record `i` against
/// the wanted key (`None` if the table is malformed).
fn search(n: usize, cmp: impl Fn(usize) -> Option<std::cmp::Ordering>) -> Option<usize> {
    use std::cmp::Ordering::{Equal, Greater, Less};
    let (mut lo, mut hi) = (0, n);
    while lo < hi {
        let mid = lo + (hi - lo) / 2;
        match cmp(mid)? {
            Less => lo = mid + 1,
            Greater => hi = mid,
            Equal => return Some(mid),
        }
    }
    None
}

/// The row and spelling kind for a `STATE|key` place key.
fn find_place(key: &str) -> Option<(u32, MatchKind)> {
    let index = tables::PLACE_INDEX;
    let at = search(index.len() / KEY_LEN, |n| {
        let r = record(index, KEY_LEN, n)?;
        let k = pool_str(tables::PLACE_KEYS, le32(r, 0)?, *r.get(4)?)?;
        Some(cmp_keys(k, key))
    })?;
    let r = record(index, KEY_LEN, at)?;
    let kind = if *r.get(5)? == 0 {
        MatchKind::Standard
    } else {
        MatchKind::Variant
    };
    Some((le32(r, 6)?, kind))
}

/// Whether a key (without its `STATE|`) is the standard name of a place in
/// any state.
fn any_place(key: &str) -> bool {
    let at = |n: usize| {
        let r = record(
            tables::PLACE_INDEX,
            KEY_LEN,
            usize::try_from(le32(tables::PLACE_ANY, n * 4)?).ok()?,
        )?;
        pool_str(tables::PLACE_KEYS, le32(r, 0)?, *r.get(4)?)?.get(3..)
    };
    search(tables::PLACE_ANY.len() / 4, |n| Some(cmp_keys(at(n)?, key))).is_some()
}

/// A ZIP's main place row and shared place rows.
fn find_zip(zip5: &str) -> Option<(u32, &'static [u32])> {
    let index = tables::ZIP_INDEX;
    let at = search(index.len() / ZIP_LEN, |n| {
        Some(record(index, ZIP_LEN, n)?.get(..5)?.cmp(zip5.as_bytes()))
    })?;
    let main = le32(record(index, ZIP_LEN, at)?, 5)?;
    let shared = find(tables::ZIP_SHARED, zip5).copied().unwrap_or(&[]);
    Some((main, shared))
}

/// The places a ZIP belongs to: its main place, and any place it shares with
/// (the ZIP straddles a boundary; only a state data lists shared places).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ZipPlaces {
    main: Place,
    shared: SharedPlaces,
}

/// The places a ZIP shares: rows of the base table, or the places of a custom layer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SharedPlaces {
    Rows(&'static [u32]),
    Layer(&'static [Place]),
}

impl ZipPlaces {
    /// The ZIP's main place (its GeoNames place name).
    pub fn main(&self) -> Place {
        self.main
    }

    /// Other places that use the ZIP.
    pub fn shared(&self) -> impl Iterator<Item = Place> + '_ {
        let (rows, layer): (&[u32], &[Place]) = match self.shared {
            SharedPlaces::Rows(r) => (r, &[]),
            SharedPlaces::Layer(p) => (&[], p),
        };
        rows.iter()
            .filter_map(|&i| place_row(i))
            .chain(layer.iter().copied())
    }

    /// The main place, then the shared ones.
    pub fn all(&self) -> impl Iterator<Item = Place> + '_ {
        std::iter::once(self.main).chain(self.shared())
    }

    /// Whether `p` uses this ZIP.
    pub fn contains(&self, p: &Place) -> bool {
        self.all().any(|q| q == *p)
    }
}

/// `a.cmp(b)`, with the first byte compared inline: in a binary search over a
/// table most steps differ at the first byte, and this spares the call to
/// `memcmp` (the order is the same as `str::cmp`).
#[inline]
fn cmp_keys(a: &str, b: &str) -> std::cmp::Ordering {
    match a.as_bytes().first().cmp(&b.as_bytes().first()) {
        std::cmp::Ordering::Equal => a.cmp(b),
        other => other,
    }
}

fn find<'a, V>(index: &'a [(&'static str, V)], key: &str) -> Option<&'a V> {
    index
        .binary_search_by(|(k, _)| cmp_keys(k, key))
        .ok()
        .and_then(|i| index.get(i))
        .map(|(_, v)| v)
}

/// Access to the compiled lexicon tables. Cheap to copy, `Send + Sync`.
///
/// Every lookup normalizes its input with [`normalize_key`] first, so
/// `"Ave."`, `"ave"` and `"AVE"` all match. Multi-word forms ("NORTH EAST",
/// "NEW YORK", "PO BOX") match when passed as one space-separated string; no
/// form has more than [`MAX_FORM_WORDS`] words.
#[derive(Debug, Clone, Copy, Default)]
pub struct Lexicons {
    /// The custom layer consulted after the shipped tables, if any (`crate::layer`).
    layer: Option<&'static Layer>,
}

impl Lexicons {
    /// The built-in tables (Pub 28 base lexicon).
    pub const fn builtin() -> Self {
        Lexicons { layer: None }
    }

    /// The built-in tables plus a custom layer's spellings and words.
    pub(crate) fn with_layer(layer: CustomLayer) -> Self {
        Lexicons {
            layer: Some(layer.0),
        }
    }

    /// The custom layer in use, if any.
    pub fn layer(&self) -> Option<LayerInfo> {
        self.layer.map(|l| l.info)
    }

    /// Street suffix: `"AVENUE"`, `"Ave."`, `"AVNUE"` -> AVE.
    pub fn suffix(&self, s: &str) -> Option<Lookup<StreetSuffix>> {
        self.suffix_base(s)
            .or_else(|| self.layer?.suffix.get(&*normalize_key_cow(s)).copied())
    }

    fn suffix_base(&self, s: &str) -> Option<Lookup<StreetSuffix>> {
        let (i, kind) = *find(tables::SUFFIX_INDEX, &normalize_key_cow(s))?;
        let row = tables::SUFFIXES.get(usize::from(i))?;
        Some(Lookup {
            value: StreetSuffix {
                abbr: row.abbr,
                name: row.name,
            },
            kind,
        })
    }

    /// Street suffix as read in `state` (a USPS code): a state data may read
    /// a spelling as another suffix, always as [`MatchKind::Observed`]. Otherwise the same as
    /// [`Self::suffix`].
    pub fn suffix_in(&self, state: &str, s: &str) -> Option<Lookup<StreetSuffix>> {
        let key = format!("{state}|{}", normalize_key(s));
        if let Some(hit) = self.layer.and_then(|l| l.state_suffix.get(&key)) {
            return Some(*hit);
        }
        let Some(&i) = find(tables::STATE_SUFFIX_INDEX, &key) else {
            return self.suffix(s);
        };
        let row = tables::SUFFIXES.get(usize::from(i))?;
        Some(Lookup {
            value: StreetSuffix {
                abbr: row.abbr,
                name: row.name,
            },
            kind: MatchKind::Observed,
        })
    }

    /// Directional: `"NORTH EAST"`, `"N.E."`, `"ne"` -> NE.
    pub fn directional(&self, s: &str) -> Option<Lookup<Directional>> {
        self.directional_base(s)
            .or_else(|| self.layer?.directional.get(&*normalize_key_cow(s)).copied())
    }

    fn directional_base(&self, s: &str) -> Option<Lookup<Directional>> {
        let (value, kind) = *find(tables::DIRECTIONAL_INDEX, &normalize_key_cow(s))?;
        Some(Lookup { value, kind })
    }

    /// Secondary unit designator: `"Suite"` -> STE. Does not match `"#"`,
    /// which stands in for an unknown designator and is handled by the tagger.
    pub fn unit(&self, s: &str) -> Option<Lookup<UnitType>> {
        self.unit_base(s)
            .or_else(|| self.layer?.unit.get(&*normalize_key_cow(s)).copied())
    }

    fn unit_base(&self, s: &str) -> Option<Lookup<UnitType>> {
        let (i, kind) = *find(tables::UNIT_INDEX, &normalize_key_cow(s))?;
        let row = tables::UNITS.get(usize::from(i))?;
        Some(Lookup {
            value: UnitType {
                abbr: row.abbr,
                name: row.name,
                range_required: row.range_required,
            },
            kind,
        })
    }

    /// State or possession, by code, full name or traditional abbreviation:
    /// `"fl"`, `"Florida"`, `"Fla."` -> FL.
    pub fn state(&self, s: &str) -> Option<Lookup<StateCode>> {
        self.state_base(s)
            .or_else(|| self.layer?.state.get(&*normalize_key_cow(s)).copied())
    }

    fn state_base(&self, s: &str) -> Option<Lookup<StateCode>> {
        let (i, kind) = *find(tables::STATE_INDEX, &normalize_key_cow(s))?;
        let row = tables::STATES.get(usize::from(i))?;
        Some(Lookup {
            value: StateCode {
                code: row.code,
                name: row.name,
                kind: row.kind,
            },
            kind,
        })
    }

    /// Special address word: `"P.O. Box"` -> PO BOX, `"Rural Route"` -> RR.
    pub fn special(&self, s: &str) -> Option<Lookup<Special>> {
        self.special_base(s)
            .or_else(|| self.layer?.special.get(&*normalize_key_cow(s)).copied())
    }

    fn special_base(&self, s: &str) -> Option<Lookup<Special>> {
        let (value, kind) = *find(tables::SPECIAL_INDEX, &normalize_key_cow(s))?;
        Some(Lookup { value, kind })
    }

    /// Highway prefix: `"County Rd"` -> COUNTY ROAD, `"HWY"` -> HIGHWAY.
    pub fn highway(&self, s: &str) -> Option<Lookup<HighwayPrefix>> {
        self.highway_base(s)
            .or_else(|| self.layer?.highway.get(&*normalize_key_cow(s)).copied())
    }

    fn highway_base(&self, s: &str) -> Option<Lookup<HighwayPrefix>> {
        let (i, kind) = *find(tables::HIGHWAY_INDEX, &normalize_key_cow(s))?;
        let standard = *tables::HIGHWAYS.get(usize::from(i))?;
        Some(Lookup {
            value: HighwayPrefix { standard },
            kind,
        })
    }

    /// Highway prefix as read in `state` (a USPS code): a state data may add
    /// a spelling the base table lacks (`SR` is STATE ROAD in Florida, STATE
    /// ROUTE elsewhere), as [`MatchKind::Variant`] or [`MatchKind::Observed`]
    /// as the state data says. Otherwise the same as [`Self::highway`].
    pub fn highway_in(&self, state: &str, s: &str) -> Option<Lookup<HighwayPrefix>> {
        let key = format!("{state}|{}", normalize_key(s));
        if let Some(hit) = self.layer.and_then(|l| l.state_highway.get(&key)) {
            return Some(*hit);
        }
        let Some(&(i, kind)) = find(tables::STATE_HIGHWAY_INDEX, &key) else {
            return self.highway(s);
        };
        let standard = *tables::HIGHWAYS.get(usize::from(i))?;
        Some(Lookup {
            value: HighwayPrefix { standard },
            kind,
        })
    }

    /// Military delivery-line type: `"PSC"`, `"Postal Service Center"` -> PSC.
    pub fn military(&self, s: &str) -> Option<Lookup<MilitaryKind>> {
        let (value, kind) = *find(tables::MILITARY_INDEX, &normalize_key_cow(s))?;
        Some(Lookup { value, kind })
    }

    /// Military post office: `"APO"`, `"FPO"`, `"DPO"`.
    pub fn military_post_office(&self, s: &str) -> Option<Lookup<MilitaryPostOffice>> {
        let (value, kind) = *find(tables::MILITARY_PO_INDEX, &normalize_key_cow(s))?;
        Some(Lookup { value, kind })
    }

    /// Whether a whole street line is placeholder text ("NO SITUS",
    /// "0 UNKNOWN", "00 UNASSIGNED LOCATION RE"), or has no letters or digits
    /// at all ("-"). A leading run of zeros is ignored, and an
    /// "UNASSIGNED LOCATION" line may end in a short trailing code.
    /// Whether `s` is a name of the United States (`USA`, `UNITED STATES`).
    /// Source: `data/special.toml` `[country]`.
    pub(crate) fn is_country(&self, s: &str) -> bool {
        self.in_words(tables::COUNTRIES, &normalize_key_cow(s), |l| {
            &l.words.country
        })
    }

    /// The place named after a municipality-type prefix (`PINECREST` in
    /// `VILLAGE OF PINECREST`), or `None` when `city` has no such prefix or
    /// nothing after it. Source: `data/special.toml` `[place_prefix]`.
    pub(crate) fn strip_place_prefix<'a>(&self, city: &'a str) -> Option<&'a str> {
        let (first, rest) = city.trim().split_once(' ')?;
        let (of, rest) = rest.trim_start().split_once(' ')?;
        let rest = rest.trim();
        (of.eq_ignore_ascii_case("OF")
            && !rest.is_empty()
            && self.in_words(tables::PLACE_PREFIXES, &normalize_key_cow(first), |l| {
                &l.words.place_prefix
            }))
        .then_some(rest)
    }

    /// Whether `s`, at the start of a line ahead of a house number, is not a
    /// recipient name (`BLOCK`, `MILEPOST`, `NO`, `URB`). Source:
    /// `data/special.toml` `[non_recipient]`.
    pub(crate) fn is_non_recipient_word(&self, s: &str) -> bool {
        self.in_words(tables::NON_RECIPIENT_WORDS, &normalize_key_cow(s), |l| {
            &l.words.non_recipient
        })
    }

    /// Whether `s`, right after a spelled-out number at the start of a line,
    /// makes the number part of the street name (`MILE` in `ONE MILE RD`).
    /// Source: `data/special.toml` `[numbered_street]`.
    pub(crate) fn is_numbered_street_word(&self, s: &str) -> bool {
        self.in_words(tables::NUMBERED_STREET_WORDS, &normalize_key_cow(s), |l| {
            &l.words.numbered_street
        })
    }

    /// A word that ends a building name (`TOWER` in `EAST TOWER`).
    /// Source: `data/special.toml` `[building]`.
    pub(crate) fn is_building_word(&self, s: &str) -> bool {
        self.in_words(tables::BUILDING_WORDS, &normalize_key_cow(s), |l| {
            &l.words.building
        })
    }

    /// A word that opens a neighborhood or district name before a city
    /// (`DOWNTOWN` in `DOWNTOWN MIAMI`). Source: `data/special.toml` `[area]`.
    pub(crate) fn is_area_word(&self, s: &str) -> bool {
        self.in_words(tables::AREA_WORDS, &normalize_key_cow(s), |l| &l.words.area)
    }

    /// A suffix word that also opens a city name (`LAKE` in `LAKE GENEVA`).
    /// Source: `data/special.toml` `[city_head]`.
    pub(crate) fn is_city_head(&self, s: &str) -> bool {
        self.in_words(tables::CITY_HEADS, &normalize_key_cow(s), |l| {
            &l.words.city_head
        })
    }

    /// Whether `key` is a placeholder phrase (`data/special.toml` `[placeholder]`, or the layer's).
    pub(crate) fn is_placeholder_phrase(&self, key: &str) -> bool {
        self.in_words(tables::PLACEHOLDERS, key, |l| &l.words.placeholder)
    }

    /// Whether `key` is a word of a word list: the shipped list, or the layer's.
    fn in_words(&self, base: &[&str], key: &str, pick: fn(&Layer) -> &HashSet<String>) -> bool {
        find_str(base, key) || self.layer.is_some_and(|l| pick(l).contains(key))
    }

    pub(crate) fn is_placeholder(&self, s: &str) -> bool {
        let key = normalize_key(s);
        if !key.chars().any(char::is_alphanumeric) {
            return true;
        }
        let rest = match key.split_once(' ') {
            Some((zeros, rest)) if zeros.bytes().all(|b| b == b'0') => rest,
            _ => key.as_str(),
        };
        if self.is_placeholder_phrase(rest) {
            return true;
        }
        // "UNASSIGNED LOCATION RE": a trailing code of up to two letters.
        match rest.rsplit_once(' ') {
            Some((head, code)) => {
                head == "UNASSIGNED LOCATION"
                    && code.len() <= 2
                    && code.bytes().all(|b| b.is_ascii_alphabetic())
            }
            None => false,
        }
    }

    /// A line of no-data markers (issue #51): `NONE`, `PA NONE`, `NULL`,
    /// `999999999 999999999`. Every token is a marker (a one-word
    /// placeholder phrase, or a run of nine or more nines) or, once, a code
    /// of up to two letters, and at least one is a marker. Only whole lines match,
    /// so `NONE SUCH RD` is not one.
    pub(crate) fn is_no_data_line(&self, s: &str) -> bool {
        let key = normalize_key(s);
        let (mut marker, mut codes) = (false, 0);
        for t in key.split(' ').filter(|t| !t.is_empty()) {
            if self.is_no_data_token(t) {
                marker = true;
            } else if t.len() > 2 || !t.bytes().all(|b| b.is_ascii_alphabetic()) {
                return false;
            } else {
                codes += 1;
            }
        }
        marker && codes <= 1
    }

    /// A single no-data marker: `NULL`, `NONE` and the other one-word
    /// placeholder phrases, or a run of nine or more nines.
    fn is_no_data_token(&self, t: &str) -> bool {
        (t.len() >= 9 && t.bytes().all(|b| b == b'9')) || self.is_placeholder_phrase(t)
    }

    /// A filler word between a unit designator and its value: `SUITE NO. 407`,
    /// `APT NUM 5`.
    pub(crate) fn is_number_filler(&self, t: &str) -> bool {
        matches!(t, "NO" | "NUM" | "NUMBER")
    }

    /// `PO` or `P O` alone: the start of a PO Box with no number and no `BOX`
    /// (`PO BOX 12` is a form of its own; this is only the leftover, #130).
    pub(crate) fn is_bare_box_word(&self, s: &str) -> bool {
        matches!(s, "PO" | "P O")
    }

    /// A word that stands for a unit designator after a street's suffix but is
    /// not one in Pub 28: `BOX 3300`, `NO 65`, `NUM 230`, `LOC 12` (#128).
    pub(crate) fn is_unit_marker(&self, t: &str) -> bool {
        self.is_number_filler(t) || matches!(t, "BOX" | "LOC")
    }

    /// A word that joins two unit values: `UNIT 3 & 4`, `SUITE 5 AND 6`.
    pub(crate) fn is_value_joiner(&self, t: &str) -> bool {
        matches!(t, "&" | "AND")
    }

    /// A word that joins two streets at an intersection: `MAIN ST & OAK AVE`,
    /// `MAIN ST AT OAK AVE`.
    pub(crate) fn is_intersection_connector(&self, t: &str) -> bool {
        matches!(t, "&" | "@" | "AND" | "AT")
    }

    /// A marker that stands for a missing house number when it opens the
    /// street line: `NULL`, or a run of nine or more nines.
    pub(crate) fn is_number_marker(&self, t: &str) -> bool {
        t == "NULL" || (t.len() >= 9 && t.bytes().all(|b| b == b'9'))
    }

    /// The place-name comparison key: case, punctuation, spacing and
    /// abbreviations do not count (`W. Palm Bch` and `WEST PALM BEACH`
    /// share one). `ST`, `FT`, `MT` stand for SAINT, FORT, MOUNT; other
    /// words are expanded through the directional and suffix tables.
    pub(crate) fn place_key(&self, s: &str) -> String {
        let mut out = String::with_capacity(s.len());
        self.place_key_into(s, &mut out);
        out
    }

    /// [`Self::place_key`], appended to `out`.
    fn place_key_into(&self, s: &str, out: &mut String) {
        place_key::place_key_into(
            s,
            |w| {
                self.directional(w)
                    .map(|l| l.value.name())
                    .or_else(|| self.suffix(w).map(|l| l.value.name()))
            },
            out,
        );
    }

    /// Run `f` on the place key of `s`, with `prefix|` in front when given.
    /// The key is built in a buffer kept per thread, so a lookup allocates
    /// nothing once the buffer has grown.
    fn with_place_key<T>(&self, prefix: Option<&str>, s: &str, f: impl FnOnce(&str) -> T) -> T {
        thread_local! {
            static KEY: std::cell::RefCell<String> = const { std::cell::RefCell::new(String::new()) };
        }
        KEY.with(|buf| {
            let mut buf = buf.borrow_mut();
            buf.clear();
            if let Some(p) = prefix {
                buf.push_str(p);
                buf.push('|');
            }
            self.place_key_into(s, &mut buf);
            f(&buf)
        })
    }

    /// Whether a curated state data for `state` (a USPS code) is compiled in.
    /// Every state has the national list; state data adds spellings seen in real
    /// data and shared ZIPs, which is what makes a city that disagrees with
    /// its ZIP worth a warning (`Warning::ZipCityMismatch`).
    pub fn has_state_data(&self, state: &str) -> bool {
        tables::STATES_WITH_DATA.contains(&state)
    }

    /// The version of the curated data for `state` (a USPS code, the
    /// `version` in its `state.toml`), or `None` when there is none. A
    /// parse's [`crate::Diagnostics::state_data_version`] is this for its state.
    pub fn state_data_version(&self, state: &str) -> Option<&'static str> {
        tables::STATE_DATA_VERSIONS
            .iter()
            .find(|(s, _)| *s == state)
            .map(|(_, v)| *v)
    }

    /// A place in `state` (a USPS code) by name or a listed spelling:
    /// `"W Palm Bch"` -> WEST PALM BEACH ([`MatchKind::Standard`]),
    /// `"BOCA RATOM"` -> BOCA RATON ([`MatchKind::Variant`]). `None` when
    /// neither the national list nor state data has it.
    pub fn place(&self, state: &str, s: &str) -> Option<Lookup<Place>> {
        self.with_place_key(Some(state), s, |key| {
            if let Some((i, kind)) = find_place(key) {
                return Some(Lookup {
                    value: place_row(i)?,
                    kind,
                });
            }
            let layer = self.layer?;
            let &(i, kind) = layer.place_index.get(key)?;
            Some(Lookup {
                value: *layer.places.get(i)?,
                kind,
            })
        })
    }

    /// Whether `s` names a place (by name, not a listed misspelling) in any
    /// state.
    pub fn is_place(&self, s: &str) -> bool {
        self.with_place_key(None, s, |key| {
            any_place(key) || self.layer.is_some_and(|l| l.place_any.contains(key))
        })
    }

    /// Whether `s` is the name of a county of `state` (`HENNEPIN` in MN,
    /// `MIAMI DADE` in FL), with or without a trailing `COUNTY`. The counties
    /// are those of the national place list.
    pub(crate) fn is_county(&self, state: &str, s: &str) -> bool {
        let has = |key: &str| {
            tables::COUNTY_INDEX
                .binary_search_by(|k| cmp_keys(k, key))
                .is_ok()
        };
        let has = |key: &str| has(key) || self.layer.is_some_and(|l| l.counties.contains(key));
        self.with_place_key(Some(state), s, |key| {
            has(key) || key.strip_suffix("COUNTY").is_some_and(has)
        })
    }

    /// The places a 5-digit ZIP belongs to.
    pub fn zip_places(&self, zip5: &str) -> Option<ZipPlaces> {
        let Some((main, shared)) = find_zip(zip5) else {
            let z = self.layer?.zips.get(zip5)?;
            return Some(ZipPlaces {
                main: z.main,
                shared: SharedPlaces::Layer(z.shared),
            });
        };
        Some(ZipPlaces {
            main: place_row(main)?,
            shared: SharedPlaces::Rows(shared),
        })
    }

    /// All places, in table order, then a custom layer's.
    pub fn places(&self) -> impl Iterator<Item = Place> {
        let layer: &'static [Place] = self.layer.map_or(&[], |l| l.places.as_slice());
        (0..tables::PLACE_ROWS.len() / ROW_LEN)
            .filter_map(|i| place_row(u32::try_from(i).ok()?))
            .chain(layer.iter().copied())
    }

    /// All street suffixes, in table order.
    pub fn suffixes(&self) -> impl Iterator<Item = StreetSuffix> {
        tables::SUFFIXES.iter().map(|r| StreetSuffix {
            abbr: r.abbr,
            name: r.name,
        })
    }

    /// All secondary unit designators, in table order.
    pub fn units(&self) -> impl Iterator<Item = UnitType> {
        tables::UNITS.iter().map(|r| UnitType {
            abbr: r.abbr,
            name: r.name,
            range_required: r.range_required,
        })
    }

    /// All states and possessions, in table order.
    pub fn states(&self) -> impl Iterator<Item = StateCode> {
        tables::STATES.iter().map(|r| StateCode {
            code: r.code,
            name: r.name,
            kind: r.kind,
        })
    }
}

/// Lookups by a table row's own name, and the shipped state readings, for the layer loader.
#[cfg(feature = "custom-layer")]
impl Lexicons {
    pub(crate) fn suffix_by_abbr(&self, abbr: &str) -> Option<StreetSuffix> {
        tables::SUFFIXES
            .iter()
            .find(|r| r.abbr == abbr)
            .map(|r| StreetSuffix {
                abbr: r.abbr,
                name: r.name,
            })
    }

    pub(crate) fn unit_by_abbr(&self, abbr: &str) -> Option<UnitType> {
        tables::UNITS
            .iter()
            .find(|r| r.abbr == abbr)
            .map(|r| UnitType {
                abbr: r.abbr,
                name: r.name,
                range_required: r.range_required,
            })
    }

    pub(crate) fn state_by_code(&self, code: &str) -> Option<Lookup<StateCode>> {
        tables::STATES
            .iter()
            .find(|r| r.code == code)
            .map(|r| Lookup {
                value: StateCode {
                    code: r.code,
                    name: r.name,
                    kind: r.kind,
                },
                kind: MatchKind::Standard,
            })
    }

    pub(crate) fn highway_by_standard(&self, standard: &str) -> Option<HighwayPrefix> {
        tables::HIGHWAYS
            .iter()
            .find(|h| **h == standard)
            .map(|h| HighwayPrefix { standard: h })
    }

    /// Whether the shipped state data reads the spelling `STATE|KEY` as another suffix.
    pub(crate) fn has_state_suffix_override(&self, state_key: &str) -> bool {
        find(tables::STATE_SUFFIX_INDEX, state_key).is_some()
    }

    /// Whether the shipped state data adds the highway spelling `STATE|KEY`.
    pub(crate) fn has_state_highway_override(&self, state_key: &str) -> bool {
        find(tables::STATE_HIGHWAY_INDEX, state_key).is_some()
    }

    /// The place-name comparison key with a caller's word expansion (the layer loader's, which
    /// knows the layer's own spellings).
    pub(crate) fn place_key_with(
        &self,
        s: &str,
        expand: impl Fn(&str) -> Option<&'static str>,
    ) -> String {
        place_key::place_key(s, expand)
    }

    /// The shipped place at a `STATE|key`, if any (the national list or a state's data).
    pub(crate) fn base_place_by_key(&self, state_key: &str) -> Option<Place> {
        place_row(find_place(state_key)?.0)
    }

    /// Whether the shipped tables have a ZIP.
    pub(crate) fn has_zip(&self, zip5: &str) -> bool {
        find_zip(zip5).is_some()
    }

    /// Whether `key` is a place-prefix word (`VILLAGE` in `VILLAGE OF PINECREST`).
    pub(crate) fn is_place_prefix_word(&self, key: &str) -> bool {
        find_str(tables::PLACE_PREFIXES, key)
    }
}

fn find_str(sorted: &[&str], key: &str) -> bool {
    sorted.binary_search_by(|k| cmp_keys(k, key)).is_ok()
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    const LEX: Lexicons = Lexicons::builtin();

    fn suffix(s: &str) -> (&'static str, MatchKind) {
        let l = LEX.suffix(s).unwrap();
        (l.value.abbr(), l.kind)
    }

    #[test]
    fn indexes_are_sorted_and_unique() {
        fn check<V>(name: &str, index: &[(&str, V)]) {
            for w in index.windows(2) {
                assert!(w[0].0 < w[1].0, "{name}: {} !< {}", w[0].0, w[1].0);
            }
        }
        check("suffix", tables::SUFFIX_INDEX);
        check("directional", tables::DIRECTIONAL_INDEX);
        check("unit", tables::UNIT_INDEX);
        check("state", tables::STATE_INDEX);
        check("special", tables::SPECIAL_INDEX);
        check("highway", tables::HIGHWAY_INDEX);
        check("military", tables::MILITARY_INDEX);
        check("military_po", tables::MILITARY_PO_INDEX);
        check("zip_shared", tables::ZIP_SHARED);
        let keys: Vec<_> = (0..tables::PLACE_INDEX.len() / KEY_LEN)
            .map(|n| {
                let r = record(tables::PLACE_INDEX, KEY_LEN, n).unwrap();
                pool_str(tables::PLACE_KEYS, le32(r, 0).unwrap(), r[4]).unwrap()
            })
            .collect();
        assert!(keys.windows(2).all(|w| w[0] < w[1]), "place index order");
        let zips: Vec<_> = (0..tables::ZIP_INDEX.len() / ZIP_LEN)
            .map(|n| record(tables::ZIP_INDEX, ZIP_LEN, n).unwrap()[..5].to_vec())
            .collect();
        assert!(zips.windows(2).all(|w| w[0] < w[1]), "zip index order");
        assert!(tables::PLACEHOLDERS.windows(2).all(|w| w[0] < w[1]));
        assert!(tables::COUNTRIES.windows(2).all(|w| w[0] < w[1]));
    }

    #[test]
    fn table_sizes() {
        assert_eq!(LEX.suffixes().count(), 202);
        assert_eq!(LEX.units().count(), 25); // Appendix C2 plus PMB (section 285)
        assert_eq!(LEX.states().count(), 62);
        assert_eq!(MAX_FORM_WORDS, 4); // FEDERATED STATES OF MICRONESIA
    }

    #[test]
    fn suffix_lookup() {
        assert_eq!(suffix("AVE"), ("AVE", MatchKind::Standard));
        assert_eq!(suffix("avenue"), ("AVE", MatchKind::FullName));
        assert_eq!(suffix("Avnue."), ("AVE", MatchKind::Variant));
        assert_eq!(suffix("TERR"), ("TER", MatchKind::Variant));
        assert_eq!(suffix("WY"), ("WAY", MatchKind::Variant));
        assert_eq!(suffix("TRC"), ("TRCE", MatchKind::Observed));
        assert_eq!(suffix("CRT"), ("CT", MatchKind::Observed));
        assert_eq!(suffix("CAUSWA"), ("CSWY", MatchKind::Variant));
        assert_eq!(suffix("COMMONS"), ("CMNS", MatchKind::FullName));
        // Plural primaries share an abbreviation.
        assert_eq!(suffix("PARKS"), ("PARK", MatchKind::Variant));
        assert_eq!(suffix("PARKWAYS"), ("PKWY", MatchKind::Variant));
        assert_eq!(LEX.suffix("CIRCLE").unwrap().value.name(), "CIRCLE");
        assert!(LEX.suffix("MAIN").is_none());
        assert!(LEX.suffix("").is_none());
    }

    #[test]
    fn every_suffix_abbr_and_name_round_trips() {
        for s in LEX.suffixes() {
            assert_eq!(LEX.suffix(s.abbr()).unwrap().value, s);
            assert_eq!(LEX.suffix(s.name()).unwrap().value, s);
        }
    }

    #[test]
    fn directional_lookup() {
        let d = |s| LEX.directional(s).map(|l| (l.value, l.kind));
        assert_eq!(d("N"), Some((Directional::N, MatchKind::Standard)));
        assert_eq!(d("north"), Some((Directional::N, MatchKind::FullName)));
        assert_eq!(d("N.E."), Some((Directional::NE, MatchKind::Standard)));
        assert_eq!(d("South West"), Some((Directional::SW, MatchKind::Variant)));
        assert_eq!(d("NORTH-WEST"), Some((Directional::NW, MatchKind::Variant)));
        assert_eq!(d("NORTE"), None);
        for dir in Directional::ALL {
            assert_eq!(d(dir.abbr()).unwrap().0, dir);
            assert_eq!(d(dir.name()).unwrap().0, dir);
        }
    }

    #[test]
    fn unit_lookup() {
        let ste = LEX.unit("Suite").unwrap();
        assert_eq!((ste.value.abbr(), ste.kind), ("STE", MatchKind::FullName));
        assert!(ste.value.range_required());
        assert!(!LEX.unit("PH").unwrap().value.range_required());
        assert_eq!(LEX.unit("HANGER").unwrap().value.abbr(), "HNGR");
        let hangar = LEX.unit("HANGAR").unwrap();
        assert_eq!(
            (hangar.value.abbr(), hangar.kind),
            ("HNGR", MatchKind::Observed)
        );
        assert_eq!(LEX.unit("UPPER").unwrap().value.abbr(), "UPPR");
        let un = LEX.unit("UN").unwrap();
        assert_eq!((un.value.abbr(), un.kind), ("UNIT", MatchKind::Observed));
        assert!(LEX.unit("#").is_none());
        for u in LEX.units() {
            assert_eq!(LEX.unit(u.abbr()).unwrap().value, u);
        }
        let no_range: Vec<_> = LEX
            .units()
            .filter(|u| !u.range_required())
            .map(|u| u.abbr())
            .collect();
        assert_eq!(
            no_range,
            ["BSMT", "FRNT", "LBBY", "LOWR", "OFC", "PH", "REAR", "SIDE", "UPPR"]
        );
    }

    #[test]
    fn state_lookup() {
        let fl = LEX.state("fl").unwrap();
        assert_eq!((fl.value.code(), fl.kind), ("FL", MatchKind::Standard));
        assert_eq!(fl.value.name(), "FLORIDA");
        assert_eq!(fl.value.kind(), StateKind::State);
        assert_eq!(LEX.state("Florida").unwrap().kind, MatchKind::FullName);
        assert_eq!(LEX.state("Fla.").unwrap().kind, MatchKind::Variant);
        assert_eq!(LEX.state("new  york").unwrap().value.code(), "NY");
        assert_eq!(LEX.state("PR").unwrap().value.kind(), StateKind::Territory);
        assert_eq!(LEX.state("AE").unwrap().value.kind(), StateKind::Military);
        assert_eq!(LEX.state("D.C.").unwrap().value.code(), "DC");
        assert!(LEX.state("ZZ").is_none());
        for s in LEX.states() {
            assert_eq!(LEX.state(s.code()).unwrap().value, s);
            assert_eq!(LEX.state(s.name()).unwrap().value, s);
        }
    }

    #[test]
    fn special_lookup() {
        let sp = |s| LEX.special(s).map(|l| (l.value, l.kind));
        assert_eq!(sp("PO BOX"), Some((Special::PoBox, MatchKind::Standard)));
        assert_eq!(sp("P.O. Box"), Some((Special::PoBox, MatchKind::Standard)));
        assert_eq!(sp("p o box"), Some((Special::PoBox, MatchKind::Variant)));
        assert_eq!(sp("POBOX"), Some((Special::PoBox, MatchKind::Variant)));
        assert_eq!(sp("Drawer"), Some((Special::PoBox, MatchKind::Variant)));
        // Pub 28 section 283.
        assert_eq!(sp("BIN"), Some((Special::PoBox, MatchKind::Variant)));
        assert_eq!(
            sp("Rural Route"),
            Some((Special::RuralRoute, MatchKind::Variant))
        );
        // Pub 28 section 244: RFD and RD become RR.
        assert_eq!(sp("RFD"), Some((Special::RuralRoute, MatchKind::Variant)));
        assert_eq!(sp("RD"), Some((Special::RuralRoute, MatchKind::Variant)));
        // Pub 28 section 251: these are input only; HC is the standard.
        assert_eq!(
            sp("Highway Contract Route"),
            Some((Special::HighwayContract, MatchKind::Variant))
        );
        assert_eq!(Special::HighwayContract.standard(), "HC");
        assert_eq!(
            sp("STAR ROUTE"),
            Some((Special::HighwayContract, MatchKind::Variant))
        );
        assert_eq!(
            sp("Gen Del"),
            Some((Special::GeneralDelivery, MatchKind::Variant))
        );
        assert_eq!(sp("BOX").unwrap().0, Special::Box);
        assert_eq!(Special::PoBox.standard(), "PO BOX");
        assert!(sp("MAIN").is_none());
    }

    #[test]
    fn highway_lookup() {
        let h = |s| LEX.highway(s).map(|l| l.value.standard());
        assert_eq!(h("County Rd"), Some("COUNTY ROAD"));
        assert_eq!(h("CR"), Some("COUNTY ROAD"));
        assert_eq!(h("HWY"), Some("HIGHWAY"));
        assert_eq!(h("US HWY"), Some("US HIGHWAY"));
        assert_eq!(h("farm to market"), Some("FM"));
        // Pub 28 Appendix F.
        assert_eq!(h("ST HIGHWAY"), Some("STATE HIGHWAY"));
        assert_eq!(h("ST RD"), Some("STATE ROAD"));
        assert_eq!(h("ST RT"), Some("STATE ROUTE"));
        assert_eq!(h("TSR"), Some("TOWNSHIP ROAD"));
        assert_eq!(h("IH"), Some("INTERSTATE"));
        assert_eq!(h("RTE"), Some("ROUTE"));
        assert_eq!(h("RD"), Some("ROAD"));
        assert_eq!(h("LOOP"), Some("LOOP"));
        // State-dependent; left to state data.
        assert_eq!(h("SR"), None);
    }

    #[test]
    fn military_lookup() {
        assert_eq!(LEX.military("psc").unwrap().value, MilitaryKind::Psc);
        assert_eq!(
            LEX.military("Unit Postal Room").unwrap().value,
            MilitaryKind::Upr
        );
        assert_eq!(LEX.military("UNIT").unwrap().value, MilitaryKind::Unit);
        assert_eq!(
            LEX.military_post_office("fpo").unwrap().value,
            MilitaryPostOffice::Fpo
        );
        assert!(LEX.military("CMR").is_none());
    }

    #[test]
    fn countries() {
        for s in [
            "USA",
            "U.S.A.",
            "us",
            "United States",
            "UNITED STATES OF AMERICA",
        ] {
            assert!(LEX.is_country(s), "{s:?}");
        }
        for s in ["CANADA", "UNITED", "STATES", "USAF", ""] {
            assert!(!LEX.is_country(s), "{s:?}");
        }
    }

    #[test]
    fn placeholders() {
        for s in [
            "NO SITUS",
            "not assigned",
            "UNKNOWN",
            "0 UNKNOWN",
            "N/A",
            "PROPERTY ADDRESS UNKNOWN",
            "NO ADDRESS ON TAX ROLL",
            "00 UNASSIGNED LOCATION RE",
            "Unassigned Location PP",
            "PROPERTY LOCATION IS NOT AVAIL",
            "-",
            "",
        ] {
            assert!(LEX.is_placeholder(s), "{s:?}");
        }
        for s in [
            "123 MAIN ST",
            "UNKNOWN RD",
            "0 HIDDEN MEADOW CT",
            "ACCESS UNDETERMINED",
        ] {
            assert!(!LEX.is_placeholder(s), "{s:?}");
        }
    }

    /// The place key as it was written before the allocation-free version
    /// (#148): a new string for every word and every expansion.
    fn place_key_reference(lex: &Lexicons, s: &str) -> String {
        let mut out = String::with_capacity(s.len());
        for word in s.split(|c: char| c.is_whitespace() || c == '-' || c == '/') {
            let w: String = word
                .chars()
                .filter(|c| c.is_alphanumeric())
                .flat_map(char::to_uppercase)
                .collect();
            match w.as_str() {
                "" => {}
                "ST" => out.push_str("SAINT"),
                "FT" => out.push_str("FORT"),
                "MT" => out.push_str("MOUNT"),
                _ => match lex
                    .directional(&w)
                    .map(|l| l.value.name().to_string())
                    .or_else(|| lex.suffix(&w).map(|l| l.value.name().to_string()))
                {
                    Some(full) => out.push_str(&full),
                    None => out.push_str(&w),
                },
            }
        }
        out
    }

    #[test]
    fn place_key_matches_the_reference_on_names_and_generated_text() {
        let mut inputs: Vec<String> = LEX.places().map(|p| p.name().to_string()).collect();
        inputs.extend(
            LEX.suffixes()
                .flat_map(|s| [s.abbr().to_string(), s.name().to_string()]),
        );
        inputs.extend(
            [
                "St. Petersburg",
                "W. Palm Bch",
                "N FT MYERS",
                "LAND O' LAKES",
                "OPA-LOCKA",
                "",
                "  ",
                "-/",
                "ß",
                "ÀÉ ñ",
                "a\tb\nc",
            ]
            .map(String::from),
        );
        // Deterministic generated text: words from a pool that has the special cases, case,
        // punctuation, hyphens, slashes, whitespace and non-ASCII letters.
        let pool = [
            "st", "St.", "FT", "mt", "N", "ne", "SPGS", "Beach", "bch", "de", "O'", "x1", "9", ".",
            "-", "/", "ß", "É", "ǅ", "  ", "\t", "AVE", "Saint",
        ];
        let mut x: u64 = 0x9E37_79B9_7F4A_7C15;
        for _ in 0..30_000 {
            let mut s = String::new();
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            let words = (x % 6) as usize;
            for k in 0..words {
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                if k > 0 && x % 3 != 0 {
                    s.push(' ');
                }
                s.push_str(pool[(x >> 8) as usize % pool.len()]);
            }
            inputs.push(s);
        }
        for s in &inputs {
            assert_eq!(LEX.place_key(s), place_key_reference(&LEX, s), "{s:?}");
            // The lookups use the same key, through the per-thread buffer.
            let by_state = LEX.place("FL", s).map(|l| (l.value.name(), l.kind));
            let reference = find_place(&format!("FL|{}", place_key_reference(&LEX, s)))
                .and_then(|(i, kind)| place_row(i).map(|v| (v.name(), kind)));
            assert_eq!(by_state, reference, "{s:?}");
            assert_eq!(
                LEX.is_place(s),
                any_place(&place_key_reference(&LEX, s)),
                "{s:?}"
            );
        }
    }

    #[test]
    fn cmp_keys_is_str_cmp() {
        let mut keys: Vec<String> = LEX
            .suffixes()
            .flat_map(|s| [s.abbr().to_string(), s.name().to_string()])
            .collect();
        keys.extend(LEX.places().map(|p| p.name().to_string()));
        keys.extend(
            [
                "", " ", "A", "AB", "B", "é", "ß", "~", "\u{7f}", "AVE", "AVENUE",
            ]
            .map(String::from),
        );
        keys.truncate(600);
        for a in &keys {
            for b in &keys {
                assert_eq!(cmp_keys(a, b), a.as_str().cmp(b.as_str()), "{a:?} {b:?}");
            }
        }
    }

    #[test]
    fn place_key_rules() {
        let k = |s| LEX.place_key(s);
        assert_eq!(k("St. Petersburg"), "SAINTPETERSBURG");
        assert_eq!(k("W PALM BCH"), k("WEST PALM BEACH"));
        assert_eq!(k("ALTAMONTE SPGS"), k("ALTAMONTE SPRINGS"));
        assert_eq!(k("N FT MYERS"), k("NORTH FORT MYERS"));
        assert_eq!(k("DE FUNIAK SPRINGS"), k("DEFUNIAK SPRINGS"));
        assert_eq!(k("OPA-LOCKA"), k("OPA LOCKA"));
        assert_eq!(k("LAND O' LAKES"), k("LAND O LAKES"));
        assert_ne!(k("PALM BEACH"), k("PALM BEACH GARDENS"));
    }

    #[test]
    fn place_lookup() {
        let p = |s| LEX.place("FL", s).map(|l| (l.value.name(), l.kind));
        assert_eq!(
            p("W. Palm Bch"),
            Some(("WEST PALM BEACH", MatchKind::Standard))
        );
        assert_eq!(
            p("PORT ST LUCIE"),
            Some(("PORT SAINT LUCIE", MatchKind::Standard))
        );
        assert_eq!(p("BOCA RATOM"), Some(("BOCA RATON", MatchKind::Variant)));
        assert_eq!(p("WINGATE ST"), None);
        assert_eq!(LEX.place("GA", "MIAMI"), None);
        let miami = LEX.place("FL", "MIAMI").unwrap().value;
        assert_eq!(
            (miami.state(), miami.county(), miami.kind()),
            ("FL", "DADE", PlaceKind::Municipality)
        );
        assert!(LEX.has_state_data("FL"));
        assert!(!LEX.has_state_data("GA"));
        assert_eq!(LEX.places().filter(|p| p.state() == "FL").count(), {
            // The state data's 665 places and 62 added communities, plus the national list's 405 Census
            // places it lacks when that is compiled in.
            if cfg!(feature = "places-us") {
                1132
            } else {
                727
            }
        });
    }

    #[cfg(feature = "places-us")]
    #[test]
    fn national_layer_sits_under_the_state_data() {
        // The national list is compiled in for every state ...
        assert!(tables::PLACE_ROWS.len() / ROW_LEN > 50_000);
        assert!(tables::ZIP_INDEX.len() / ZIP_LEN > 41_000);
        assert!(find_place("MO|SAINTLOUIS").is_some());
        assert_eq!(
            find_place("PA|ROARINGBROOKTWP").map(|p| p.1),
            Some(MatchKind::Variant)
        );
        assert!(find_zip("63101").is_some());
        assert!(find_zip("6310").is_none() && find_zip("631011").is_none());
        // ... and lookups read every state.
        let stl = LEX.place("MO", "ST LOUIS").unwrap();
        assert_eq!(
            (stl.value.name(), stl.kind),
            ("SAINT LOUIS", MatchKind::Standard)
        );
        assert_eq!(LEX.zip_places("63101").unwrap().main().state(), "MO");
        assert!(LEX.is_place("LA GRANGE PARK"));
        assert!(!LEX.is_place("LA GRANGE PARKK"));
        assert!(LEX.places().any(|p| p.state() == "MO"));
        assert!(!LEX.has_state_data("MO"));
    }

    #[cfg(feature = "places-us")]
    #[test]
    fn national_rows_only_add_to_the_state_data() {
        // A Census place the state data lacks is added, with its county and kind.
        let trinity = LEX.place("FL", "TRINITY").unwrap();
        assert_eq!(trinity.kind, MatchKind::Standard);
        assert_eq!(
            (trinity.value.county(), trinity.value.kind()),
            ("PASCO", PlaceKind::Place)
        );
        // The state data's own row and spelling win.
        let miami = LEX.place("FL", "MIAMI").unwrap().value;
        assert_eq!(
            (miami.county(), miami.kind()),
            ("DADE", PlaceKind::Municipality)
        );
        assert_eq!(
            LEX.place("FL", "BOCA RATOM").unwrap().kind,
            MatchKind::Variant
        );
        // The Census's Everglades is the state data's EVERGLADES CITY, not a second
        // place (build_us.py renames it).
        assert_eq!(LEX.place("FL", "EVERGLADES"), None);
        assert_eq!(
            LEX.place("FL", "EVERGLADES CITY").unwrap().value.county(),
            "COLLIER"
        );
        // A national-only place the state data's observed ZIPs name is shared.
        let bellview = LEX.place("FL", "BELLVIEW").unwrap().value;
        let z = LEX.zip_places("32526").unwrap();
        assert_eq!(z.main().name(), "PENSACOLA");
        assert!(z.contains(&bellview));
        // The state data's ZIP table is not touched: 32507 is still PENSACOLA.
        assert_eq!(LEX.zip_places("32507").unwrap().main().name(), "PENSACOLA");
    }

    #[test]
    fn state_highway_override() {
        // SR is not in the base table (State Road in Florida, State Route
        // elsewhere); the Florida state data reads it as STATE ROAD.
        assert!(LEX.highway("SR").is_none());
        let fl = LEX.highway_in("FL", "sr").unwrap();
        assert_eq!(
            (fl.value.standard(), fl.kind),
            ("STATE ROAD", MatchKind::Variant)
        );
        assert!(LEX.highway_in("OH", "SR").is_none());
        let cty = LEX.highway_in("FL", "CTY HWY").unwrap();
        assert_eq!(
            (cty.value.standard(), cty.kind),
            ("COUNTY HIGHWAY", MatchKind::Observed)
        );
        // A base spelling reads the same in every state.
        assert_eq!(
            LEX.highway_in("FL", "CO RD").unwrap().value.standard(),
            "COUNTY ROAD"
        );
    }

    #[test]
    fn state_suffix_override() {
        // CR is an observed CIRCLE spelling everywhere (#108), so no state
        // data overrides it; `suffix_in` falls back to the base table.
        let base = LEX.suffix("CR").unwrap();
        assert_eq!(base.value.abbr(), "CIR");
        assert_eq!(base.kind, MatchKind::Observed);
        let fl = LEX.suffix_in("FL", "cr").unwrap();
        assert_eq!(fl.value.abbr(), "CIR");
        assert_eq!(fl.kind, MatchKind::Observed);
        assert_eq!(LEX.suffix_in("CO", "CR").unwrap().value.abbr(), "CIR");
        assert_eq!(LEX.suffix("CK").unwrap().value.abbr(), "CRK");
        assert_eq!(LEX.suffix_in("FL", "CIRCLE").unwrap().value.abbr(), "CIR");
        // An observed ZIP place (zips_observed.tsv): CORAL GABLES in 33134.
        let gables = LEX.place("FL", "CORAL GABLES").unwrap().value;
        assert!(LEX.zip_places("33134").unwrap().contains(&gables));
    }

    #[test]
    fn zip_lookup() {
        let z = LEX.zip_places("32507").unwrap();
        assert_eq!(z.main().name(), "PENSACOLA");
        assert!(z.contains(&z.main()));
        // A ZIP shared by two places.
        let aventura = LEX.place("FL", "AVENTURA").unwrap().value;
        let shared = LEX.zip_places("33180").unwrap();
        assert!(shared.contains(&aventura));
        assert_ne!(shared.main(), aventura);
        // The national list covers every state; no ZIP, no place.
        assert_eq!(LEX.zip_places("10001").unwrap().main().state(), "NY");
        assert!(LEX.zip_places("00000").is_none());
        // Every place is found by its own name.
        for p in LEX.places() {
            assert_eq!(LEX.place(p.state(), p.name()).unwrap().value, p);
        }
    }

    #[test]
    fn normalize_key_cow_matches_normalize_key() {
        for s in [
            "", " ", "MAIN", "PO BOX", "PO  BOX", " PO BOX", "PO BOX ", "N.E.", "north", "a\u{b}b",
            "A\tB", "straße", "\u{a0}X", "A-B", "#4", "..",
        ] {
            assert_eq!(super::key::normalize_key_cow(s), normalize_key(s), "{s:?}");
        }
        assert!(matches!(
            super::key::normalize_key_cow("PO BOX"),
            std::borrow::Cow::Borrowed(_)
        ));
    }

    #[test]
    fn normalize_key_rules() {
        assert_eq!(normalize_key("  p.o.   box "), "PO BOX");
        assert_eq!(normalize_key("N.E."), "NE");
        assert_eq!(normalize_key("north-west"), "NORTH-WEST");
        assert_eq!(normalize_key("\tNew\nYork"), "NEW YORK");
        assert_eq!(normalize_key("..."), "");
    }
}
