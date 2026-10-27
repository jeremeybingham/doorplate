//! Reading a layer from text (feature `custom-layer`): parsing, validation and the leaked,
//! deduplicated store the loaded data lives in.

use std::collections::hash_map::Entry;
use std::collections::{HashMap, HashSet};
use std::fmt;
use std::sync::{Mutex, OnceLock};

use toml::{Table, Value};

use super::{CustomLayer, Layer, LayerInfo, LayerZip, WordLists};
use crate::lexicon::{
    normalize_key, HighwayPrefix, Lexicons, Lookup, MatchKind, Special, MAX_FORM_WORDS,
    MAX_PLACE_WORDS,
};
use crate::types::{Directional, Place, PlaceKind, StateCode, StateKind, StreetSuffix, UnitType};

/// The text of a layer's files. Only `layer` (the `layer.toml`) is required.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
#[non_exhaustive]
pub struct LayerSources<'a> {
    /// `layer.toml`: `name`, `version`, optional `notes`.
    pub layer: &'a str,
    /// `aliases.toml`: spellings of the base tables and additions to the word lists.
    pub aliases: Option<&'a str>,
    /// `overrides.toml`: state-scoped readings of a spelling.
    pub overrides: Option<&'a str>,
    /// `places.tsv`: places (and their misspellings) to add.
    pub places: Option<&'a str>,
    /// `zips.tsv`: ZIPs to add, each naming its place.
    pub zips: Option<&'a str>,
}

impl<'a> LayerSources<'a> {
    /// Sources with the text of `layer.toml`.
    pub fn new(layer: &'a str) -> Self {
        LayerSources {
            layer,
            ..Self::default()
        }
    }

    /// Add the text of `aliases.toml`.
    #[must_use]
    pub fn aliases(mut self, text: &'a str) -> Self {
        self.aliases = Some(text);
        self
    }

    /// Add the text of `overrides.toml`.
    #[must_use]
    pub fn overrides(mut self, text: &'a str) -> Self {
        self.overrides = Some(text);
        self
    }

    /// Add the text of `places.tsv`.
    #[must_use]
    pub fn places(mut self, text: &'a str) -> Self {
        self.places = Some(text);
        self
    }

    /// Add the text of `zips.tsv`.
    #[must_use]
    pub fn zips(mut self, text: &'a str) -> Self {
        self.zips = Some(text);
        self
    }
}

/// A layer that cannot be loaded: every problem found, each naming its file and entry.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LayerError {
    problems: Vec<String>,
}

impl LayerError {
    /// The problems, one per line of the message.
    pub fn problems(&self) -> &[String] {
        &self.problems
    }
}

impl fmt::Display for LayerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "the custom layer has {} problem{}:",
            self.problems.len(),
            if self.problems.len() == 1 { "" } else { "s" }
        )?;
        for p in &self.problems {
            write!(f, "\n  {p}")?;
        }
        Ok(())
    }
}

impl std::error::Error for LayerError {}

impl CustomLayer {
    /// Load a layer from the text of its files. Everything is checked first; on any problem
    /// nothing is loaded and the error lists them all. Loading the same content again returns
    /// the layer already loaded.
    ///
    /// ```
    /// use doorplate::{CustomLayer, LayerSources, ParseOptions, Parser};
    ///
    /// let layer = CustomLayer::from_sources(
    ///     &LayerSources::new("name = \"county\"\nversion = \"1\"\n").aliases(
    ///         "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"TRAYL\"]\nevidence = \"county export\"\n",
    ///     ),
    /// )?;
    /// let parser = Parser::with_options(ParseOptions::new().custom_layer(layer))?;
    /// let a = parser.parse("123 Oak Trayl, Miami, FL 33101")?;
    /// assert_eq!(a.street_suffix.map(|s| s.abbr()), Some("TRL"));
    /// assert_eq!(a.diagnostics.custom_layer.map(|l| l.name), Some("county"));
    /// # Ok::<(), Box<dyn std::error::Error>>(())
    /// ```
    pub fn from_sources(src: &LayerSources<'_>) -> Result<CustomLayer, LayerError> {
        let mut errs = Errors::default();
        let meta = read_meta(src.layer, &mut errs);
        let aliases = src
            .aliases
            .and_then(|t| parse_file("aliases.toml", t, &mut errs));
        let overrides = src
            .overrides
            .and_then(|t| parse_file("overrides.toml", t, &mut errs));
        let mut data = Data::default();
        if let Some(t) = &aliases {
            read_aliases(t, &mut data, &mut errs);
        }
        if let Some(t) = &overrides {
            read_overrides(t, &mut data, &mut errs);
        }
        if let Some(t) = src.places {
            read_places(t, &mut data, &mut errs);
        }
        if let Some(t) = src.zips {
            read_zips(t, &mut data, &mut errs);
        }
        let Some((name, version)) = meta else {
            return Err(errs.into_error());
        };
        if !errs.0.is_empty() {
            return Err(errs.into_error());
        }
        let fingerprint = fingerprint(src);
        let mut store = store().lock().unwrap_or_else(|e| e.into_inner());
        if let Some(&layer) = store.get(&fingerprint) {
            return Ok(CustomLayer(layer));
        }
        let info = LayerInfo {
            name: leak(name),
            version: leak(version),
            fingerprint: leak(fingerprint.clone()),
        };
        let layer: &'static Layer = Box::leak(Box::new(data.into_layer(info)));
        store.insert(fingerprint, layer);
        Ok(CustomLayer(layer))
    }
}

type Store = Mutex<HashMap<String, &'static Layer>>;

fn store() -> &'static Store {
    static STORE: OnceLock<Store> = OnceLock::new();
    STORE.get_or_init(|| Mutex::new(HashMap::new()))
}

fn leak(s: String) -> &'static str {
    Box::leak(s.into_boxed_str())
}

/// FNV-1a 64 over each file's label and bytes, as 16 hex digits.
fn fingerprint(src: &LayerSources<'_>) -> String {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    let mut feed = |bytes: &[u8]| {
        for &b in bytes {
            h ^= u64::from(b);
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
        h ^= 0xff;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    };
    for (label, text) in [
        ("layer.toml", Some(src.layer)),
        ("aliases.toml", src.aliases),
        ("overrides.toml", src.overrides),
        ("places.tsv", src.places),
        ("zips.tsv", src.zips),
    ] {
        if let Some(t) = text {
            feed(label.as_bytes());
            feed(t.as_bytes());
        }
    }
    format!("{h:016x}")
}

#[derive(Default)]
struct Errors(Vec<String>);

impl Errors {
    fn add(&mut self, ctx: &str, msg: impl fmt::Display) {
        self.0.push(format!("{ctx}: {msg}"));
    }

    fn into_error(self) -> LayerError {
        LayerError { problems: self.0 }
    }
}

// ---------------------------------------------------------------------------------------------
// The files

fn parse_file(name: &str, text: &str, errs: &mut Errors) -> Option<Table> {
    match text.parse::<Table>() {
        Ok(t) => Some(t),
        Err(e) => {
            errs.add(name, format!("not valid TOML: {}", e.message()));
            None
        }
    }
}

fn read_meta(text: &str, errs: &mut Errors) -> Option<(String, String)> {
    let t = parse_file("layer.toml", text, errs)?;
    unknown_keys("layer.toml", &t, &["name", "version", "notes"], errs);
    let name = req_str("layer.toml", &t, "name", errs);
    let version = req_str("layer.toml", &t, "version", errs);
    if let Some(n) = &name {
        let ok = !n.is_empty()
            && n.len() <= 64
            && n.chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'));
        if !ok {
            errs.add(
                "layer.toml",
                "`name` must be 1 to 64 characters of letters, digits, `.`, `_` and `-`",
            );
        }
    }
    Some((name?, version?))
}

fn unknown_keys(ctx: &str, t: &Table, known: &[&str], errs: &mut Errors) {
    for k in t.keys() {
        if !known.contains(&k.as_str()) {
            errs.add(
                ctx,
                format!("unknown key `{k}` (known: {})", known.join(", ")),
            );
        }
    }
}

fn req_str(ctx: &str, t: &Table, key: &str, errs: &mut Errors) -> Option<String> {
    match t.get(key) {
        Some(Value::String(s)) if !s.trim().is_empty() => Some(s.trim().to_string()),
        Some(_) => {
            errs.add(ctx, format!("`{key}` must be a non-empty string"));
            None
        }
        None => {
            errs.add(ctx, format!("`{key}` is required"));
            None
        }
    }
}

fn str_list(ctx: &str, t: &Table, key: &str, errs: &mut Errors) -> Vec<String> {
    match t.get(key) {
        Some(Value::Array(a)) if !a.is_empty() => {
            let mut out = Vec::new();
            for v in a {
                match v {
                    Value::String(s) if !s.trim().is_empty() => out.push(s.clone()),
                    _ => errs.add(ctx, format!("`{key}` must hold non-empty strings")),
                }
            }
            out
        }
        Some(_) => {
            errs.add(ctx, format!("`{key}` must be a non-empty list of strings"));
            Vec::new()
        }
        None => {
            errs.add(ctx, format!("`{key}` is required"));
            Vec::new()
        }
    }
}

/// The entries of `[[name]]` in a file, each with a context string for messages.
fn entries<'a>(
    file: &str,
    t: &'a Table,
    name: &str,
    errs: &mut Errors,
) -> Vec<(String, &'a Table)> {
    let Some(v) = t.get(name) else {
        return Vec::new();
    };
    let Value::Array(a) = v else {
        errs.add(
            file,
            format!("`{name}` must be an array of tables (`[[{name}]]`)"),
        );
        return Vec::new();
    };
    a.iter()
        .enumerate()
        .filter_map(|(i, e)| match e {
            Value::Table(t) => Some((format!("{file} [[{name}]] #{}", i + 1), t)),
            _ => {
                errs.add(file, format!("`{name}` #{} is not a table", i + 1));
                None
            }
        })
        .collect()
}

/// Every entry names its evidence, so a reader can judge it.
fn need_evidence(ctx: &str, t: &Table, errs: &mut Errors) {
    let has = |k: &str| matches!(t.get(k), Some(Value::String(s)) if !s.trim().is_empty());
    if !has("evidence") && !has("note") {
        errs.add(
            ctx,
            "needs `evidence` or `note` (where the spelling was seen, or why)",
        );
    }
}

/// A normalized spelling that fits the lexicon: letters or digits, at most `MAX_FORM_WORDS`
/// words.
fn spelling_key(ctx: &str, raw: &str, errs: &mut Errors) -> Option<String> {
    let key = normalize_key(raw);
    if !key.chars().any(char::is_alphanumeric) {
        errs.add(ctx, format!("spelling {raw:?} has no letters or digits"));
        return None;
    }
    if key.split(' ').count() > MAX_FORM_WORDS {
        errs.add(
            ctx,
            format!("spelling {raw:?} has more than {MAX_FORM_WORDS} words"),
        );
        return None;
    }
    Some(key)
}

// ---------------------------------------------------------------------------------------------
// Aliases

#[derive(Default)]
struct Data {
    suffix: HashMap<String, Lookup<StreetSuffix>>,
    unit: HashMap<String, Lookup<UnitType>>,
    directional: HashMap<String, Lookup<Directional>>,
    state: HashMap<String, Lookup<StateCode>>,
    special: HashMap<String, Lookup<Special>>,
    highway: HashMap<String, Lookup<HighwayPrefix>>,
    state_suffix: HashMap<String, Lookup<StreetSuffix>>,
    state_highway: HashMap<String, Lookup<HighwayPrefix>>,
    words: WordLists,
    places: Vec<Place>,
    place_index: HashMap<String, (usize, MatchKind)>,
    place_any: HashSet<String>,
    counties: HashSet<String>,
    zips: HashMap<String, LayerZip>,
}

impl Data {
    fn into_layer(self, info: LayerInfo) -> Layer {
        Layer {
            info,
            suffix: self.suffix,
            unit: self.unit,
            directional: self.directional,
            state: self.state,
            special: self.special,
            highway: self.highway,
            state_suffix: self.state_suffix,
            state_highway: self.state_highway,
            words: self.words,
            places: self.places,
            place_index: self.place_index,
            place_any: self.place_any,
            counties: self.counties,
            zips: self.zips,
        }
    }
}

/// `kind` of an entry: `observed` (the default; raises `non_standard_abbreviation`) or
/// `variant`.
fn kind_of(ctx: &str, t: &Table, errs: &mut Errors) -> MatchKind {
    match t.get("kind").and_then(Value::as_str) {
        None | Some("observed") => MatchKind::Observed,
        Some("variant") => MatchKind::Variant,
        Some(other) => {
            errs.add(
                ctx,
                format!("`kind` is `variant` or `observed`, not {other:?}"),
            );
            MatchKind::Observed
        }
    }
}

/// Add `spellings` to `map` as `value`, refusing a spelling the base already has (`in_base`) or
/// that an earlier entry added.
fn add_spellings<T: Copy>(
    ctx: &str,
    spellings: &[String],
    kind: MatchKind,
    value: T,
    in_base: impl Fn(&str) -> bool,
    map: &mut HashMap<String, Lookup<T>>,
    errs: &mut Errors,
) {
    for raw in spellings {
        let Some(key) = spelling_key(ctx, raw, errs) else {
            continue;
        };
        if in_base(&key) {
            errs.add(
                ctx,
                format!("{raw:?} is already in the shipped tables; a layer only adds spellings"),
            );
        } else if let Entry::Vacant(v) = map.entry(key) {
            v.insert(Lookup { value, kind });
        } else {
            errs.add(ctx, format!("{raw:?} is already added by another entry"));
        }
    }
}

const SPELLING_KEYS: &[&str] = &["spellings", "kind", "evidence", "note"];

fn keys_with(first: &str) -> Vec<&str> {
    std::iter::once(first)
        .chain(SPELLING_KEYS.iter().copied())
        .collect()
}

fn read_aliases(t: &Table, d: &mut Data, errs: &mut Errors) {
    let file = "aliases.toml";
    unknown_keys(
        file,
        t,
        &[
            "suffix",
            "unit",
            "directional",
            "state",
            "special",
            "highway",
            "words",
        ],
        errs,
    );
    let base = Lexicons::builtin();

    for (ctx, e) in entries(file, t, "suffix", errs) {
        unknown_keys(&ctx, e, &keys_with("abbr"), errs);
        need_evidence(&ctx, e, errs);
        let Some(abbr) = req_str(&ctx, e, "abbr", errs) else {
            continue;
        };
        let spellings = str_list(&ctx, e, "spellings", errs);
        let Some(target) = base.suffix_by_abbr(&abbr) else {
            errs.add(
                &ctx,
                format!("no street suffix with the abbreviation {abbr:?}"),
            );
            continue;
        };
        let kind = kind_of(&ctx, e, errs);
        add_spellings(
            &ctx,
            &spellings,
            kind,
            target,
            |k| base.suffix(k).is_some(),
            &mut d.suffix,
            errs,
        );
    }
    for (ctx, e) in entries(file, t, "unit", errs) {
        unknown_keys(&ctx, e, &keys_with("abbr"), errs);
        need_evidence(&ctx, e, errs);
        let Some(abbr) = req_str(&ctx, e, "abbr", errs) else {
            continue;
        };
        let spellings = str_list(&ctx, e, "spellings", errs);
        let Some(target) = base.unit_by_abbr(&abbr) else {
            errs.add(
                &ctx,
                format!("no unit designator with the abbreviation {abbr:?}"),
            );
            continue;
        };
        let kind = kind_of(&ctx, e, errs);
        add_spellings(
            &ctx,
            &spellings,
            kind,
            target,
            |k| base.unit(k).is_some(),
            &mut d.unit,
            errs,
        );
    }
    for (ctx, e) in entries(file, t, "directional", errs) {
        unknown_keys(&ctx, e, &keys_with("abbr"), errs);
        need_evidence(&ctx, e, errs);
        let Some(abbr) = req_str(&ctx, e, "abbr", errs) else {
            continue;
        };
        let spellings = str_list(&ctx, e, "spellings", errs);
        let Some(target) = Directional::ALL.iter().copied().find(|d| d.abbr() == abbr) else {
            errs.add(
                &ctx,
                format!("{abbr:?} is not a directional (N, S, E, W, NE, NW, SE, SW)"),
            );
            continue;
        };
        let kind = kind_of(&ctx, e, errs);
        add_spellings(
            &ctx,
            &spellings,
            kind,
            target,
            |k| base.directional(k).is_some(),
            &mut d.directional,
            errs,
        );
    }
    for (ctx, e) in entries(file, t, "state", errs) {
        unknown_keys(&ctx, e, &keys_with("code"), errs);
        need_evidence(&ctx, e, errs);
        let Some(code) = req_str(&ctx, e, "code", errs) else {
            continue;
        };
        let spellings = str_list(&ctx, e, "spellings", errs);
        let Some(target) = base.state_by_code(&code).map(|l| l.value) else {
            errs.add(
                &ctx,
                format!("no state or territory with the code {code:?}"),
            );
            continue;
        };
        let kind = kind_of(&ctx, e, errs);
        add_spellings(
            &ctx,
            &spellings,
            kind,
            target,
            |k| base.state(k).is_some(),
            &mut d.state,
            errs,
        );
    }
    for (ctx, e) in entries(file, t, "special", errs) {
        unknown_keys(&ctx, e, &keys_with("form"), errs);
        need_evidence(&ctx, e, errs);
        let Some(which) = req_str(&ctx, e, "form", errs) else {
            continue;
        };
        let spellings = str_list(&ctx, e, "spellings", errs);
        let target = match which.as_str() {
            "po_box" => Special::PoBox,
            "box" => Special::Box,
            "rural_route" => Special::RuralRoute,
            "highway_contract" => Special::HighwayContract,
            "general_delivery" => Special::GeneralDelivery,
            "attention" => Special::Attention,
            other => {
                errs.add(
                    &ctx,
                    format!("`form` {other:?} is not one of po_box, box, rural_route, highway_contract, general_delivery, attention"),
                );
                continue;
            }
        };
        let kind = kind_of(&ctx, e, errs);
        add_spellings(
            &ctx,
            &spellings,
            kind,
            target,
            |k| base.special(k).is_some(),
            &mut d.special,
            errs,
        );
    }
    for (ctx, e) in entries(file, t, "highway", errs) {
        unknown_keys(&ctx, e, &keys_with("standard"), errs);
        need_evidence(&ctx, e, errs);
        let Some(standard) = req_str(&ctx, e, "standard", errs) else {
            continue;
        };
        let spellings = str_list(&ctx, e, "spellings", errs);
        let Some(target) = base.highway_by_standard(&standard) else {
            errs.add(
                &ctx,
                format!("no highway prefix with the standard name {standard:?}"),
            );
            continue;
        };
        let kind = kind_of(&ctx, e, errs);
        add_spellings(
            &ctx,
            &spellings,
            kind,
            target,
            |k| base.highway(k).is_some(),
            &mut d.highway,
            errs,
        );
    }
    for (ctx, e) in entries(file, t, "words", errs) {
        unknown_keys(&ctx, e, &["list", "words", "evidence", "note"], errs);
        need_evidence(&ctx, e, errs);
        let Some(list) = req_str(&ctx, e, "list", errs) else {
            continue;
        };
        let words = str_list(&ctx, e, "words", errs);
        type InBase = fn(&Lexicons, &str) -> bool;
        let (set, in_base): (&mut HashSet<String>, InBase) = match list.as_str() {
            "building" => (&mut d.words.building, Lexicons::is_building_word),
            "area" => (&mut d.words.area, Lexicons::is_area_word),
            "city_head" => (&mut d.words.city_head, Lexicons::is_city_head),
            "non_recipient" => (&mut d.words.non_recipient, Lexicons::is_non_recipient_word),
            "numbered_street" => (
                &mut d.words.numbered_street,
                Lexicons::is_numbered_street_word,
            ),
            "placeholder" => (&mut d.words.placeholder, Lexicons::is_placeholder_phrase),
            "country" => (&mut d.words.country, Lexicons::is_country),
            "place_prefix" => (&mut d.words.place_prefix, Lexicons::is_place_prefix_word),
            other => {
                errs.add(
                    &ctx,
                    format!("`list` {other:?} is not one of building, area, city_head, non_recipient, numbered_street, placeholder, country, place_prefix"),
                );
                continue;
            }
        };
        for raw in &words {
            let Some(key) = spelling_key(&ctx, raw, errs) else {
                continue;
            };
            if in_base(&base, &key) {
                errs.add(
                    &ctx,
                    format!("{raw:?} is already in the shipped `{list}` list"),
                );
            } else if !set.insert(key) {
                errs.add(&ctx, format!("{raw:?} is listed twice"));
            }
        }
    }
}

// ---------------------------------------------------------------------------------------------
// Overrides

fn read_overrides(t: &Table, d: &mut Data, errs: &mut Errors) {
    let file = "overrides.toml";
    unknown_keys(file, t, &["suffix", "highway"], errs);
    let base = Lexicons::builtin();

    for (ctx, e) in entries(file, t, "suffix", errs) {
        unknown_keys(
            &ctx,
            e,
            &["state", "spelling", "abbr", "evidence", "note"],
            errs,
        );
        need_evidence(&ctx, e, errs);
        let (Some(state), Some(spelling), Some(abbr)) = (
            req_str(&ctx, e, "state", errs),
            req_str(&ctx, e, "spelling", errs),
            req_str(&ctx, e, "abbr", errs),
        ) else {
            continue;
        };
        let Some(code) = base.state_by_code(&state) else {
            errs.add(
                &ctx,
                format!("no state or territory with the code {state:?}"),
            );
            continue;
        };
        let Some(target) = base.suffix_by_abbr(&abbr) else {
            errs.add(
                &ctx,
                format!("no street suffix with the abbreviation {abbr:?}"),
            );
            continue;
        };
        let Some(key) = spelling_key(&ctx, &spelling, errs) else {
            continue;
        };
        if base.suffix(&key).is_none() {
            errs.add(
                &ctx,
                format!("{spelling:?} is not a spelling the shipped tables have; add it under `[[suffix]]` in aliases.toml instead"),
            );
            continue;
        }
        let full = format!("{}|{key}", code.value.code());
        if base.has_state_suffix_override(&full) {
            errs.add(
                &ctx,
                format!("the shipped {state} data already reads {spelling:?} its own way"),
            );
        } else if let Entry::Vacant(v) = d.state_suffix.entry(full) {
            v.insert(Lookup {
                value: target,
                kind: MatchKind::Observed,
            });
        } else {
            errs.add(
                &ctx,
                format!("{spelling:?} in {state} is already overridden by another entry"),
            );
        }
    }
    for (ctx, e) in entries(file, t, "highway", errs) {
        unknown_keys(
            &ctx,
            e,
            &["state", "spelling", "highway", "kind", "evidence", "note"],
            errs,
        );
        need_evidence(&ctx, e, errs);
        let (Some(state), Some(spelling), Some(standard)) = (
            req_str(&ctx, e, "state", errs),
            req_str(&ctx, e, "spelling", errs),
            req_str(&ctx, e, "highway", errs),
        ) else {
            continue;
        };
        let Some(code) = base.state_by_code(&state) else {
            errs.add(
                &ctx,
                format!("no state or territory with the code {state:?}"),
            );
            continue;
        };
        let Some(target) = base.highway_by_standard(&standard) else {
            errs.add(
                &ctx,
                format!("no highway prefix with the standard name {standard:?}"),
            );
            continue;
        };
        let Some(key) = spelling_key(&ctx, &spelling, errs) else {
            continue;
        };
        let kind = kind_of(&ctx, e, errs);
        let full = format!("{}|{key}", code.value.code());
        if base.has_state_highway_override(&full) {
            errs.add(
                &ctx,
                format!("the shipped {state} data already reads {spelling:?} its own way"),
            );
        } else if let Entry::Vacant(v) = d.state_highway.entry(full) {
            v.insert(Lookup {
                value: target,
                kind,
            });
        } else {
            errs.add(
                &ctx,
                format!("{spelling:?} in {state} is already overridden by another entry"),
            );
        }
    }
}

// ---------------------------------------------------------------------------------------------
// Places and ZIPs (TSV)

/// The rows of a TSV file with a header: a column named in `required` must be there, one in
/// `optional` may be; any other column is an error. Blank lines and `#` lines are skipped.
/// Each row is a map from column name to its trimmed text, with the context for messages.
fn read_tsv(
    file: &str,
    text: &str,
    required: &[&str],
    optional: &[&str],
    errs: &mut Errors,
) -> Vec<(String, HashMap<String, String>)> {
    let mut lines = text
        .lines()
        .enumerate()
        .filter(|(_, l)| !l.trim().is_empty() && !l.trim_start().starts_with('#'));
    let Some((_, header)) = lines.next() else {
        errs.add(
            file,
            format!(
                "empty; the header line names the columns ({})",
                required.join(", ")
            ),
        );
        return Vec::new();
    };
    let cols: Vec<&str> = header.split('\t').map(str::trim).collect();
    let mut ok = true;
    for c in &cols {
        if !required.contains(c) && !optional.contains(c) {
            errs.add(
                file,
                format!(
                    "unknown column `{c}` (columns: {})",
                    required
                        .iter()
                        .chain(optional)
                        .copied()
                        .collect::<Vec<_>>()
                        .join(", ")
                ),
            );
            ok = false;
        }
    }
    for r in required {
        if !cols.contains(r) {
            errs.add(
                file,
                format!("the header has no `{r}` column (separate columns with tabs)"),
            );
            ok = false;
        }
    }
    if !ok {
        return Vec::new();
    }
    let mut out = Vec::new();
    for (n, line) in lines {
        let ctx = format!("{file} line {}", n + 1);
        let cells: Vec<&str> = line.split('\t').collect();
        if cells.len() != cols.len() {
            errs.add(
                &ctx,
                format!("{} columns, the header has {}", cells.len(), cols.len()),
            );
            continue;
        }
        let row = cols
            .iter()
            .zip(cells)
            .map(|(c, v)| ((*c).to_string(), v.trim().to_string()))
            .collect();
        out.push((ctx, row));
    }
    out
}

fn need_row_evidence(ctx: &str, row: &HashMap<String, String>, errs: &mut Errors) {
    if !matches!(row.get("evidence"), Some(e) if !e.is_empty()) {
        errs.add(ctx, "needs an `evidence` (where the place was seen)");
    }
}

/// A state code of a state, DC or territory (not a military "state").
fn real_state(base: &Lexicons, ctx: &str, code: &str, errs: &mut Errors) -> Option<&'static str> {
    match base.state_by_code(code) {
        Some(l) if l.value.kind() != StateKind::Military => Some(l.value.code()),
        _ => {
            errs.add(
                ctx,
                format!("{code:?} is not the code of a US state, DC or territory"),
            );
            None
        }
    }
}

/// The place-name comparison key with the layer's own suffix and directional spellings, the way
/// `Lexicons` computes it when the layer is in use.
fn place_key_of(d: &Data, name: &str) -> String {
    let base = Lexicons::builtin();
    base.place_key_with(name, |w| {
        let k = normalize_key(w);
        base.directional(w)
            .or_else(|| d.directional.get(&k).copied())
            .map(|l| l.value.name())
            .or_else(|| {
                base.suffix(w)
                    .or_else(|| d.suffix.get(&k).copied())
                    .map(|l| l.value.name())
            })
    })
}

fn place_name(ctx: &str, raw: &str, what: &str, errs: &mut Errors) -> Option<String> {
    let key = normalize_key(raw);
    if key.is_empty() || !key.chars().any(char::is_alphabetic) {
        errs.add(ctx, format!("{what} {raw:?} has no letters"));
        return None;
    }
    if key.split(' ').count() > MAX_PLACE_WORDS {
        errs.add(
            ctx,
            format!("{what} {raw:?} has more than {MAX_PLACE_WORDS} words, the longest the place lookup reads"),
        );
        return None;
    }
    Some(key)
}

fn read_places(text: &str, d: &mut Data, errs: &mut Errors) {
    let file = "places.tsv";
    let base = Lexicons::builtin();
    let rows = read_tsv(
        file,
        text,
        &["state", "name", "evidence"],
        &["county", "kind", "variants"],
        errs,
    );
    for (ctx, row) in &rows {
        need_row_evidence(ctx, row, errs);
        let Some(state) = real_state(&base, ctx, &row["state"], errs) else {
            continue;
        };
        let Some(name) = place_name(ctx, &row["name"], "the name", errs) else {
            continue;
        };
        let kind = match row.get("kind").map(String::as_str) {
            None | Some("" | "place") => PlaceKind::Place,
            Some("municipality") => PlaceKind::Municipality,
            Some("subdivision") => PlaceKind::Subdivision,
            Some(other) => {
                errs.add(
                    ctx,
                    format!("`kind` is municipality, place or subdivision, not {other:?}"),
                );
                continue;
            }
        };
        let county = match row.get("county").map(String::as_str) {
            None | Some("") => None,
            Some(c) => match place_name(ctx, c, "the county", errs) {
                Some(c) => Some(c),
                None => continue,
            },
        };
        let key = format!("{state}|{}", place_key_of(d, &name));
        // (key, how it is spelled, the text as written, for messages)
        let mut keys = vec![(key, MatchKind::Standard, row["name"].clone())];
        for v in row
            .get("variants")
            .map_or("", String::as_str)
            .split(';')
            .map(str::trim)
            .filter(|v| !v.is_empty())
        {
            if let Some(vn) = place_name(ctx, v, "the variant", errs) {
                keys.push((
                    format!("{state}|{}", place_key_of(d, &vn)),
                    MatchKind::Variant,
                    v.to_string(),
                ));
            }
        }
        let mut clash = false;
        for (i, (k, _, raw)) in keys.iter().enumerate() {
            if base.base_place_by_key(k).is_some() {
                errs.add(
                    ctx,
                    format!("{raw:?} is already in the national place list or the shipped {state} data; a layer only adds places"),
                );
                clash = true;
            } else if d.place_index.contains_key(k) {
                errs.add(ctx, format!("{raw:?} is the same place as one listed earlier (case, punctuation and abbreviations do not make a different place)"));
                clash = true;
            } else if keys[..i].iter().any(|(o, _, _)| o == k) {
                errs.add(ctx, format!("{raw:?} matches the same as the name or another variant (case, punctuation and abbreviations such as HTS for HEIGHTS are already equal); drop it"));
                clash = true;
            }
        }
        if clash {
            continue;
        }
        let idx = d.places.len();
        d.places.push(Place {
            state,
            name: leak(name),
            county: county.as_deref().map_or("", |c| leak(c.to_string())),
            kind,
        });
        for (k, mk, _) in keys {
            if mk == MatchKind::Standard {
                d.place_any.insert(k[3..].to_string());
            }
            d.place_index.insert(k, (idx, mk));
        }
        if let Some(c) = county {
            d.counties
                .insert(format!("{state}|{}", place_key_of(d, &c)));
        }
    }
}

/// A place of `state` by name, among the layer's places and the shipped ones.
fn find_place_of(d: &Data, state: &str, name: &str) -> Option<Place> {
    let key = format!("{state}|{}", place_key_of(d, name));
    match d.place_index.get(&key) {
        Some(&(i, _)) => d.places.get(i).copied(),
        None => Lexicons::builtin().base_place_by_key(&key),
    }
}

fn read_zips(text: &str, d: &mut Data, errs: &mut Errors) {
    let file = "zips.tsv";
    let base = Lexicons::builtin();
    let rows = read_tsv(
        file,
        text,
        &["zip", "state", "place", "evidence"],
        &["shared"],
        errs,
    );
    for (ctx, row) in &rows {
        need_row_evidence(ctx, row, errs);
        let zip = &row["zip"];
        if zip.len() != 5 || !zip.bytes().all(|b| b.is_ascii_digit()) {
            errs.add(ctx, format!("`zip` {zip:?} is not five digits"));
            continue;
        }
        if base.has_zip(zip) {
            errs.add(
                ctx,
                format!("{zip} is already in the shipped ZIP list; a layer only adds ZIPs"),
            );
            continue;
        }
        if d.zips.contains_key(zip.as_str()) {
            errs.add(ctx, format!("{zip} is listed twice"));
            continue;
        }
        let Some(state) = real_state(&base, ctx, &row["state"], errs) else {
            continue;
        };
        let Some(main) = find_place_of(d, state, &row["place"]) else {
            errs.add(
                ctx,
                format!("the place {:?} is not in the national list, the shipped {state} data or this layer's places.tsv", row["place"]),
            );
            continue;
        };
        let mut shared = Vec::new();
        let mut bad = false;
        for name in row
            .get("shared")
            .map_or("", String::as_str)
            .split(';')
            .map(str::trim)
            .filter(|n| !n.is_empty())
        {
            match find_place_of(d, state, name) {
                Some(p) if p != main && !shared.contains(&p) => shared.push(p),
                Some(_) => {
                    errs.add(ctx, format!("the shared place {name:?} repeats the main place or another shared place"));
                    bad = true;
                }
                None => {
                    errs.add(
                        ctx,
                        format!("the shared place {name:?} is not a known place of {state}"),
                    );
                    bad = true;
                }
            }
        }
        if !bad {
            let shared: &'static [Place] = Box::leak(shared.into_boxed_slice());
            d.zips.insert(zip.clone(), LayerZip { main, shared });
        }
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn the_lexicon_sees_the_layer_places_zips_and_counties() {
        let layer = CustomLayer::from_sources(
            &LayerSources::new("name = \"t\"\nversion = \"1\"\n")
                .places("state\tname\tcounty\tevidence\nFL\tQUINCEWOOD HEIGHTS\tZEPHYR\tx\nFL\tBAYVIEW MILLS\t\tx\n")
                .zips("zip\tstate\tplace\tshared\tevidence\n33999\tFL\tQUINCEWOOD HEIGHTS\tBAYVIEW MILLS\tx\n"),
        )
        .unwrap();
        let lex = Lexicons::with_layer(layer);
        let base = Lexicons::builtin();
        assert!(lex.is_place("Quincewood Hts") && !base.is_place("Quincewood Hts"));
        assert!(lex.is_county("FL", "Zephyr County") && !base.is_county("FL", "Zephyr"));
        let names: Vec<_> = lex.places().map(|p| p.name()).collect();
        assert!(names.ends_with(&["QUINCEWOOD HEIGHTS", "BAYVIEW MILLS"]));
        assert_eq!(base.places().count() + 2, lex.places().count());
        let z = lex.zip_places("33999").unwrap();
        assert_eq!(z.main().name(), "QUINCEWOOD HEIGHTS");
        assert_eq!(
            z.shared().map(|p| p.name()).collect::<Vec<_>>(),
            ["BAYVIEW MILLS"]
        );
        assert!(z.contains(&lex.place("FL", "Bayview Mills").unwrap().value));
        assert!(base.zip_places("33999").is_none());
    }
}
