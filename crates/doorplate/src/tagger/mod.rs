//! Rule-based tagger (pipeline step 4).
//!
//! Gives every token a [`Tag`]. Rules live in [`rules`]; this module holds
//! the types, the entry points and the checks that run once everything is
//! tagged. Following Pub 28 section 231, the last line (ZIP, state, city) is
//! read from the right first, then the delivery line from both ends inward.
//!
//! The tagger never guesses: a token no rule claims becomes
//! [`Tag::Unparsed`] and is reported in `Diagnostics::unparsed`.

mod rules;

use std::ops::Range;

use crate::lexicon::{Lexicons, ZipPlaces};
use crate::tokenize::Token;
use crate::types::{FieldName, Warning};

/// Lines at least this long that end in something incomplete (a cut-off
/// ZIP, a designator with no number, a cut-off word) get
/// [`Warning::PossiblyTruncated`]. County sites cut address lines at about
/// 30 characters.
pub(crate) const TRUNCATION_MIN_LEN: usize = 30;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Tag {
    /// No rule claimed the token yet. Becomes `Unparsed` when tagging ends.
    Untagged,
    /// Consumed without a value: `#`, separators, BOX words, placeholder
    /// text, a repeated copy of the city.
    Skip,
    Unparsed,
    StreetNumber,
    PreDir,
    Name,
    Suffix,
    PostDir,
    /// A state named before a highway prefix or route (Appendix F).
    HighwayState,
    HighwayPrefix,
    HighwayRoute,
    /// Unit designator; 0 for the first unit, 1 for the second.
    UnitType(u8),
    UnitNumber(u8),
    PoBox,
    PoBoxNumber,
    /// An attention or care-of line (Pub 28 section 214).
    Attention,
    /// A building name (`EAST TOWER`).
    Building,
    /// RR or HC word.
    Route,
    RouteNumber,
    BoxNumber,
    /// A lone letter written after a box number, joined to it (`BOX 45 A`).
    BoxLetter,
    GeneralDelivery,
    MilitaryKind,
    MilitaryNumber,
    MilitaryBoxNumber,
    MilitaryPostOffice,
    City,
    State,
    Zip,
}

/// An uncertain rule that settled a boundary. Warnings report what went
/// wrong; these record what the tagger had to judge on a parse that may have
/// none. Internal: tests and the corpus tools read them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Decision {
    /// The city is a line or comma segment of its own (`..., MIAMI`).
    CityByComma,
    /// One line with no commas: the city starts after the street's suffix
    /// (`12 LAKE SHORE DR CHICAGO`), or is all there is (`TAMPA 33616`).
    CityBySuffix,
    /// The city was found in the place list (`MAIN ST WEST PALM BEACH`).
    CityByPlace,
    /// A state with no ZIP after it (`..., MIAMI FL`).
    StateWithoutZip,
    /// A unit with no designator: after the suffix (`DR 706`, `DR B`) or a
    /// later line that is only a number.
    BareUnit,
    /// A single letter joined to the house number (`428 B SOUTH MAIN ST`).
    NumberLetter,
    /// The parser's `default_state` decided a tag (a city or a state's data's
    /// highway spelling).
    DefaultState,
}

impl Decision {
    /// Stable snake_case identifier, read by the corpus tools.
    #[cfg(feature = "corpus")]
    pub(crate) const fn code(self) -> &'static str {
        match self {
            Decision::CityByComma => "city_by_comma",
            Decision::CityBySuffix => "city_by_suffix",
            Decision::CityByPlace => "city_by_place",
            Decision::StateWithoutZip => "state_without_zip",
            Decision::BareUnit => "bare_unit",
            Decision::NumberLetter => "number_letter",
            Decision::DefaultState => "default_state",
        }
    }
}

pub(crate) struct Tagged {
    pub tags: Vec<Tag>,
    pub warnings: Vec<Warning>,
    /// Each uncertain decision once, in the order first made.
    pub decisions: Vec<Decision>,
}

/// Lengths used for the truncation check.
pub(crate) struct LineLengths {
    /// Character length of each segment, indexed by segment number.
    pub seg: Vec<usize>,
    /// Character length of the whole input (single-line input only).
    pub whole: Option<usize>,
}

pub(crate) struct Tagger<'a> {
    toks: &'a [Token],
    tags: Vec<Tag>,
    warnings: Vec<Warning>,
    decisions: Vec<Decision>,
    lex: Lexicons,
    /// A token where the input looks cut off, if any.
    incomplete: Option<usize>,
    zero_number: bool,
    /// A lone letter after the house number was read as its suffix on the strength of the letter
    /// alone (`46 A LINDEN AVE`, #270): the text cannot say, so `ambiguous_number_letter` stays.
    number_letter_guess: bool,
    /// Pre-split input with a city, state or ZIP field: a street field that is
    /// only a country is dropped (#130).
    country_street: bool,
    lens: LineLengths,
    /// The state data that applies, once the last line's state or ZIP is
    /// known.
    places: Option<PlaceCtx>,
    /// The parser's `default_state`, used when the input names no state.
    hint: Option<&'static str>,
    /// Whether a place found under the hint decided a tag.
    hint_used: std::cell::Cell<bool>,
}

/// The state whose data is used to find the city, and the ZIP's places.
#[derive(Clone, Copy)]
pub(crate) struct PlaceCtx {
    state: &'static str,
    zip: Option<ZipPlaces>,
    /// The state is the parser's `default_state`, not the input's.
    hinted: bool,
}

impl<'a> Tagger<'a> {
    fn new(
        toks: &'a [Token],
        lex: Lexicons,
        lens: LineLengths,
        hint: Option<&'static str>,
    ) -> Self {
        Self {
            toks,
            tags: vec![Tag::Untagged; toks.len()],
            warnings: Vec::new(),
            decisions: Vec::new(),
            lex,
            incomplete: None,
            zero_number: false,
            number_letter_guess: false,
            country_street: false,
            lens,
            places: None,
            hint,
            hint_used: std::cell::Cell::new(false),
        }
    }

    /// A copy of text that appears twice was dropped: the parse is the one with the copy removed (`repeated_text`).
    pub(super) fn repeated(&mut self) {
        self.warn(Warning::RepeatedText);
    }

    pub(super) fn warn(&mut self, w: Warning) {
        if !self.warnings.contains(&w) {
            self.warnings.push(w);
        }
    }

    fn decide(&mut self, d: Decision) {
        if !self.decisions.contains(&d) {
            self.decisions.push(d);
        }
    }

    fn set(&mut self, r: Range<usize>, tag: Tag) {
        for t in self.tags.get_mut(r).into_iter().flatten() {
            *t = tag;
        }
    }

    fn text(&self, i: usize) -> &'a str {
        self.toks.get(i).map_or("", |t| t.text.as_str())
    }

    /// First token index of the segment that token `i` is in.
    fn seg_start(&self, i: usize) -> usize {
        let seg = self.toks[i].seg;
        let mut s = i;
        while s > 0 && self.toks[s - 1].seg == seg {
            s -= 1;
        }
        s
    }

    /// Diagnostics for line 2 text that is dropped, or used by the street, or
    /// kept as the building name, without a component of its own (#45). Called
    /// once line 2's tokens are tagged; line 2 text that is a unit, an
    /// attention line, the city, state or ZIP, or an unparsed remainder is
    /// reported (or not) as before.
    fn second_line_notes(&mut self, l1: &Range<usize>, l2: &Range<usize>) {
        let (Some(first), Some(second)) = (self.tags.get(l1.clone()), self.tags.get(l2.clone()))
        else {
            return;
        };
        if second.is_empty() {
            return;
        }
        let street = |t: &Tag| {
            matches!(
                t,
                Tag::PreDir
                    | Tag::Name
                    | Tag::Suffix
                    | Tag::PostDir
                    | Tag::HighwayPrefix
                    | Tag::HighwayRoute
            )
        };
        let skipped = second.iter().all(|t| *t == Tag::Skip);
        // The street began on line 1: a street on line 2 alone (`THE COVE` /
        // `1111 ASBURY WAY`, a box on line 1) is just the address.
        let began = first.iter().any(|t| street(t) || *t == Tag::StreetNumber);
        let in_street = began && second.iter().any(street);
        let building = second.contains(&Tag::Building);
        if skipped {
            self.warn(Warning::SecondLineSkipped);
        }
        if in_street {
            self.warn(Warning::SecondLineInStreet);
        }
        if building {
            self.warn(Warning::SecondLineBuilding);
        }
    }

    fn finish(mut self) -> Tagged {
        // A repeated line 2 already says so (`second_line_skipped`).
        if self.warnings.contains(&Warning::SecondLineSkipped) {
            self.warnings.retain(|w| *w != Warning::RepeatedText);
        }
        for t in &mut self.tags {
            if *t == Tag::Untagged {
                *t = Tag::Unparsed;
            }
        }
        let has = |tags: &[Tag], tag: Tag| tags.contains(&tag);
        let street_like = has(&self.tags, Tag::Name)
            || has(&self.tags, Tag::Suffix)
            || has(&self.tags, Tag::HighwayRoute);
        if street_like && !has(&self.tags, Tag::StreetNumber) && !self.zero_number {
            self.warn(Warning::MissingStreetNumber);
        }
        // "123 UNIT 1": a house number and a unit, no street.
        let unit = self
            .tags
            .iter()
            .any(|t| matches!(t, Tag::UnitType(_) | Tag::UnitNumber(_)));
        if unit && !street_like && has(&self.tags, Tag::StreetNumber) {
            self.warn(Warning::MissingStreetName);
        }
        // `123 A MAIN ST`: a single letter right after a plain house number that
        // went into a street name of more than one word. It may be the number's
        // suffix (`123A`); the text cannot say (#102).
        let letter_in_name = self.tags.windows(3).enumerate().any(|(k, w)| {
            let (num, letter) = (&self.toks[k], &self.toks[k + 1]);
            w == [Tag::StreetNumber, Tag::Name, Tag::Name]
                && num.seg == letter.seg
                && num.text.bytes().all(|b| b.is_ascii_digit() || b == b'-')
                && letter.text.len() == 1
                // `U S ROUTE 23` is the US highway, not number 20192U (as in `number_letter`).
                && !(letter.text == "U" && self.toks.get(k + 2).is_some_and(|n| n.text == "S"))
                && letter.text.bytes().all(|b| b.is_ascii_alphabetic())
        });
        if letter_in_name || self.number_letter_guess {
            self.warn(Warning::AmbiguousNumberLetter);
        }
        if has(&self.tags, Tag::Unparsed) {
            self.warn(Warning::UnparsedRemainder);
        }
        if self.hint_used.get() {
            self.warn(Warning::DefaultStateApplied);
            self.decide(Decision::DefaultState);
        }
        if let Some(k) = self.incomplete {
            let tok = &self.toks[k];
            let seg_len = self.lens.seg.get(tok.seg).copied().unwrap_or(0);
            let at_end = k + 1 == self.toks.len();
            let whole = self.lens.whole.unwrap_or(0);
            if seg_len >= TRUNCATION_MIN_LEN || (at_end && whole >= TRUNCATION_MIN_LEN) {
                self.warn(Warning::PossiblyTruncated);
            }
        }
        Tagged {
            tags: self.tags,
            warnings: self.warnings,
            decisions: self.decisions,
        }
    }
}

/// Tag a single-line input.
pub(crate) fn tag_line(
    toks: &[Token],
    lex: Lexicons,
    lens: LineLengths,
    hint: Option<&'static str>,
) -> Tagged {
    let mut t = Tagger::new(toks, lex, lens, hint);
    let (street_end, city) = t.last_line();
    let lo = t.drop_truncated_copy(0, street_end);
    if lo > 0 {
        t.repeated();
    }
    let z = t.drop_repeated_zip(lo, street_end);
    if z < street_end {
        t.repeated();
    }
    let street_end = z;
    let c = t.drop_city_copy(lo, street_end, city);
    if c < street_end {
        t.repeated();
    }
    let street_end = c;
    t.delivery(lo, street_end);
    t.finish()
}

/// Tag [`crate::Fields`] input. `ranges` gives each field's token range;
/// fields were tokenized in order, so the ranges are contiguous.
pub(crate) fn tag_fields(
    toks: &[Token],
    ranges: &[(FieldName, Range<usize>)],
    lex: Lexicons,
    lens: LineLengths,
    hint: Option<&'static str>,
) -> Tagged {
    let get = |f: FieldName| {
        ranges
            .iter()
            .find(|(n, _)| *n == f)
            .map_or(0..0, |(_, r)| r.clone())
    };
    let (l1, l2) = (get(FieldName::Line1), get(FieldName::Line2));
    let (city, state, zip) = (
        get(FieldName::City),
        get(FieldName::State),
        get(FieldName::Zip),
    );
    let mut line = l1.start.min(l2.start)..l1.end.max(l2.end);
    let mut t = Tagger::new(toks, lex, lens, hint);
    // Line 2 that repeats the end of line 1 (`9453 LUTOO LANE` / `LUTOO
    // LANE`, seen in Florida address data) is a copy.
    if !l2.is_empty() && l2.start == l1.end && l2.len() <= l1.len() {
        let same = toks[l2.clone()]
            .iter()
            .zip(&toks[l1.end - l2.len()..l1.end])
            .all(|(a, b)| a.text == b.text);
        if same {
            t.set(l2.clone(), Tag::Skip);
            line = l1.clone();
        }
    }
    // A line 2 of no-data markers (`PA NONE`, `999999999 999999999`) is
    // dropped as a placeholder instead of being read as a unit or leftover.
    if !l2.is_empty()
        && !l1.is_empty()
        && lex.is_no_data_line(&crate::classify::join(&toks[l2.clone()]))
    {
        t.set(l2.clone(), Tag::Skip);
        line = l1.clone();
    }
    // `123 MAIN ST` / `1/2`: a line 2 that is only a fraction is the fraction
    // of the house number, so line 1 is read alone and the fraction joins the
    // number. A fraction that opens a longer line 2 (`1/2 APT 3`) joins it
    // after the delivery line is read, if nothing claimed it.
    let line1_number = !l1.is_empty()
        && crate::classify::house_number(&toks[l1.start].text).is_some()
        && !toks
            .get(l1.start + 1)
            .is_some_and(|n| crate::classify::is_fraction(&n.text));
    let lone_fraction = line1_number
        && l2.len() == 1
        && l2.start == l1.end
        && crate::classify::is_fraction(&toks[l2.start].text);
    if lone_fraction {
        t.set(l2.clone(), Tag::StreetNumber);
        line = l1.clone();
    }
    // `123 MAIN ST` / `N`: a street that already ends in its suffix, then a lone
    // directional on line 2, is a unit, not a postdirectional (#170: NAD's
    // labels say unit for 88.8% of these). Line 1 is read alone.
    let lone_direction = !lone_fraction
        && !l1.is_empty()
        && l1.len() >= 3
        && l2.len() == 1
        && l2.start == l1.end
        && crate::classify::house_number(&toks[l1.start].text).is_some()
        && lex.suffix(&toks[l1.end - 1].text).is_some()
        && toks[l2.start].text.len() <= 2
        && lex.directional(&toks[l2.start].text).is_some();
    if lone_direction {
        line = l1.clone();
    }
    let before = line.start;
    line.start = t.drop_truncated_copy(line.start, line.end);
    if line.start > before {
        t.repeated();
    }
    let after_fraction = line1_number
        && !lone_fraction
        && l2.start == l1.end
        && !l2.is_empty()
        && crate::classify::is_fraction(&toks[l2.start].text);
    if city.is_empty() && state.is_empty() && zip.is_empty() {
        // Everything is on the address lines: read them like one line.
        let (street_end, c) = t.last_line_in(line.start, line.end);
        let z = t.drop_repeated_zip(line.start, street_end);
        if z < street_end {
            t.repeated();
        }
        let street_end = t.drop_city_copy(line.start, z, c);
        if street_end < z {
            t.repeated();
        }
        t.delivery(line.start, street_end);
        if after_fraction {
            t.claim_fraction(l2.start);
        }
        t.claim_bare_unit(l2.clone());
        t.claim_lone_direction(&l2, lone_direction);
        t.claim_name_after_box(&l1, &l2);
        t.second_line_notes(&l1, &l2);
        return t.finish();
    }
    let city_range = t.city_field(city, state.is_empty());
    t.state_field(state.clone());
    t.zip_field(zip.clone());
    let mut end = line.end;
    // The ZIP that tells the place context: the field, else one ending line 1.
    let mut zip_at = (t.tags.get(zip.start) == Some(&Tag::Zip)).then_some(zip.start);
    if zip.is_empty() {
        end = t.trailing_zip(line.start, end);
        zip_at = (end < line.end).then_some(end);
    } else {
        let z = t.drop_repeated_zip(line.start, end);
        if z < end {
            t.repeated();
        }
        end = z;
    }
    // The state data applies to the address lines as it does to one-line input
    // (`SR 60` is `STATE ROAD 60` in Florida), #110.
    let state_at = (t.tags.get(state.start) == Some(&Tag::State)).then_some(state);
    t.places = t.place_ctx(state_at, zip_at);
    let s2 = t.drop_repeated_state(line.start, end);
    if s2 < end {
        t.repeated();
    }
    let end = t.drop_city_copy(line.start, s2, city_range);
    if end < s2 {
        t.repeated();
    }
    t.country_street = true;
    t.delivery(line.start, end);
    if after_fraction {
        t.claim_fraction(l2.start);
    }
    t.claim_bare_unit(l2.clone());
    t.claim_lone_direction(&l2, lone_direction);
    t.claim_name_after_box(&l1, &l2);
    t.second_line_notes(&l1, &l2);
    t.finish()
}

#[cfg(test)]
mod tests {
    use super::Decision::*;
    use super::*;
    use crate::clean::clean;
    use crate::tokenize::tokenize;

    fn decisions(input: &str, hint: Option<&'static str>) -> Vec<Decision> {
        let lex = Lexicons::builtin();
        let toks = tokenize(&clean(input), None, 0, &lex);
        let lens = LineLengths {
            seg: Vec::new(),
            whole: Some(input.len()),
        };
        tag_line(&toks, lex, lens, hint).decisions
    }

    #[test]
    fn a_plain_parse_records_only_how_the_city_was_found() {
        for input in [
            "123 MAIN ST, MIAMI, FL 33101",
            "123 MAIN ST APT 4, MIAMI, FL 33101",
            "PO BOX 5, MIAMI, FL 33101",
            "123 MAIN ST, MIAMI",
        ] {
            assert_eq!(decisions(input, None), vec![CityByComma], "{input}");
        }
        assert_eq!(decisions("123 MAIN ST, FL 33101", None), vec![]);
    }

    #[test]
    fn a_city_on_one_line_by_suffix_or_place() {
        assert_eq!(
            decisions("12 LAKE SHORE DR ZYQXV FL 33101", None),
            vec![CityBySuffix]
        );
        #[cfg(feature = "places-us")]
        assert_eq!(
            decisions("123 MAIN ST WEST PALM BEACH FL 33401", None),
            vec![CityByPlace]
        );
    }

    #[test]
    fn a_state_with_no_zip() {
        assert_eq!(
            decisions("123 MAIN ST, ZYQXV FL", None),
            vec![StateWithoutZip, CityByComma]
        );
    }

    #[test]
    fn bare_units_and_the_number_letter() {
        assert_eq!(
            decisions("100 OAK DR 706, MIAMI, FL 33101", None),
            vec![CityByComma, BareUnit]
        );
        assert_eq!(
            decisions("100 OAK DR V 21, MIAMI, FL 33101", None),
            vec![CityByComma, BareUnit]
        );
        assert_eq!(
            decisions("2309 1ST AVE NO, 403, MIAMI, FL 33101", None),
            vec![CityByComma, BareUnit]
        );
        assert_eq!(
            decisions("428 B SOUTH MAIN ST, MIAMI, FL 33101", None),
            vec![CityByComma, NumberLetter]
        );
        // A designator makes the unit certain.
        assert_eq!(
            decisions("100 OAK DR APT 706, MIAMI, FL 33101", None),
            vec![CityByComma]
        );
    }

    #[test]
    #[cfg(feature = "places-us")]
    fn the_default_state_hint() {
        assert_eq!(
            decisions("281 EVELYN DR DOTHAN", Some("AL")),
            vec![CityByPlace, DefaultState]
        );
        assert_eq!(decisions("281 EVELYN DR DOTHAN", None), vec![]);
        assert_eq!(decisions("22200 SR 60", Some("FL")), vec![DefaultState]);
        assert_eq!(decisions("22200 SR 60", Some("OH")), vec![]);
        // The input's own state wins; the hint decides nothing.
        assert_eq!(
            decisions("500 OAK ST, ATLANTA, GA 30301", Some("FL")),
            vec![CityByComma]
        );
    }
}
