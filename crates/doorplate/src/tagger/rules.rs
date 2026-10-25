//! Tagging rules. The source of each rule (a Pub 28 section, or an address
//! shape observed in Florida address data) is in `docs/usps-pub28-notes.md`.

use std::ops::Range;

use super::{Decision, PlaceCtx, Tag, Tagger};
use crate::classify::{
    all_digits, has_digit, house_number, is_bare_unit, is_cut_designator, is_fraction,
    is_glued_ordinal, is_grid_number, is_letter, is_lettered_route, is_ordinal, is_route_value,
    is_slash_pair, is_unit_pair, is_unit_value, is_unit_word, join, longest_at, longest_ending,
    spelled_number, spelled_ordinal, zip_parts, NumberShape, ORDINAL_SUFFIXES,
};
use crate::lexicon::{MatchKind, Special, MAX_PLACE_WORDS};
use crate::tokenize::Token;
use crate::types::{StateKind, Warning};

/// A special delivery line: the tags to apply and where it ends.
struct SpecialMatch {
    tags: Vec<(Range<usize>, Tag)>,
    end: usize,
    /// Whether a unit may follow (PO Box, rural route).
    units: bool,
}

/// A highway street name found in the delivery line.
struct HighwayAt {
    pre: Range<usize>,
    /// A state before the prefix (`KY STATE HIGHWAY 1`); empty if none.
    state: Range<usize>,
    /// Empty when a state stands for the prefix (`KENTUCKY 440`).
    prefix: Range<usize>,
    route: usize,
}

impl Tagger<'_> {
    // ---- last line: ZIP, state, city ---------------------------------------

    /// Tag the last line of a single-line input. Returns the end of the
    /// delivery-line tokens and the city's tokens, if any.
    pub(super) fn last_line(&mut self) -> (usize, Option<Range<usize>>) {
        self.last_line_in(0, self.toks.len())
    }

    /// [`Self::last_line`] over tokens `lo..hi`.
    pub(super) fn last_line_in(&mut self, lo: usize, hi: usize) -> (usize, Option<Range<usize>>) {
        if lo >= hi {
            return (hi, None);
        }
        let toks = self.toks;
        let mut end = hi;
        let last = &toks[hi - 1];
        let after_hash = hi - 1 > lo && toks[hi - 2].is_hash();
        let mut zip = false;
        let mut bad_zip = false;

        // ZIP: the last token. A number after '#' is a unit (`#11176`).
        if zip_parts(&last.text).is_some() && !after_hash && !last.paren {
            self.set(hi - 1..hi, Tag::Zip);
            end -= 1;
            zip = true;
        } else if all_digits(&last.text) && !after_hash && hi - 1 > lo {
            // A cut-off ZIP right after a state: `FL 3`, `FL 320`.
            let seg_start = self.seg_start(hi - 1).max(lo);
            if let Some((_, w)) =
                longest_ending(toks, seg_start, hi - 1, |s| self.state_ok(s, true))
            {
                let starts_segment = hi - 1 - w == seg_start && seg_start > lo;
                let long = self.lens.whole.unwrap_or(0) >= super::TRUNCATION_MIN_LEN;
                if starts_segment || long {
                    self.set(hi - 1..hi, Tag::Unparsed);
                    self.warn(Warning::InvalidZip);
                    self.incomplete = Some(hi - 1);
                    end -= 1;
                    bad_zip = true;
                }
            }
        }

        // State: right before the ZIP, or first in the ZIP's segment
        // (anything between is unparsed). With no ZIP, only a state that
        // ends a later segment ("..., MIAMI FL").
        let mut ll_start = end;
        let mut state: Option<Range<usize>> = None;
        if end > lo {
            let seg_start = self.seg_start(end - 1).max(lo);
            if zip || bad_zip {
                if let Some((_, w)) =
                    longest_ending(toks, seg_start, end, |s| self.state_ok(s, true))
                {
                    state = Some(self.state_span(end - w, end));
                } else if let Some((_, w)) =
                    longest_at(toks, seg_start, end, |s| self.state_ok(s, false))
                {
                    self.set(seg_start + w..end, Tag::Unparsed);
                    state = Some(seg_start..seg_start + w);
                }
            } else if let Some((_, w)) =
                longest_ending(toks, seg_start, end, |s| self.state_ok(s, false))
            {
                // No ZIP: a state ending a later segment ("..., MIAMI FL"),
                // or ending a single line after a city ("... ST MIAMI FL",
                // not "... ST FL", where FL may be a floor).
                let later_seg = seg_start > lo;
                if later_seg
                    || self.city_after_street(lo, end - w).is_some()
                    || self.state_alone(lo, end - w, end)
                {
                    state = Some(end - w..end);
                }
            }
        }
        // "12 SIMON CT 32505": on one line with no commas, a state that is
        // also a street suffix, with no city before it, is the suffix.
        if let Some(r) = state.clone() {
            let text = join(&toks[r.clone()]);
            let one_line = toks[r.start].seg == toks[lo].seg;
            // "8517 CEDAR BARK CIR KY": after an abbreviated suffix it is
            // the state.
            let after_suffix = r.start > lo && self.abbreviated_suffix(r.start - 1);
            // "69 HERITAGE WOODS WALLINGFORD CT 06492": a ZIP that belongs to
            // the state, with a place of that state right before it, makes it
            // the state ("12 SIMON CT 06492" has no place before CT).
            let zip_agrees = zip
                && self.lex.state(&text).is_some_and(|s| {
                    let code = s.value.code();
                    zip_parts(&toks[hi - 1].text)
                        .and_then(|(z5, _)| self.lex.zip_places(z5))
                        .is_some_and(|z| z.main().state() == code)
                        && (1..=MAX_PLACE_WORDS).any(|w| {
                            r.start > lo + w
                                && self
                                    .lex
                                    .place(code, &join(&toks[r.start - w..r.start]))
                                    .is_some()
                        })
                });
            if one_line
                && self.lex.suffix(&text).is_some()
                && !after_suffix
                && !zip_agrees
                && self.city_after_street(lo, r.start).is_none()
            {
                state = None;
            }
        }
        if let Some(r) = &state {
            self.set(r.clone(), Tag::State);
            ll_start = r.start;
            if !zip && !bad_zip {
                self.decide(Decision::StateWithoutZip);
            }
        }
        self.places = self.place_ctx(state.clone(), zip.then_some(hi - 1));
        if !zip && !bad_zip && state.is_none() {
            // "123 MAIN ST, MIAMI": a last segment of plain words after a
            // street is the city.
            let cs = self.seg_start(hi - 1).max(lo);
            if cs > lo && self.looks_like_city(cs, hi) && !self.starts_unit(cs, hi) {
                self.set(cs..hi, Tag::City);
                self.decide(Decision::CityByComma);
                return (cs, Some(cs..hi));
            }
            // With a `default_state` hint: "281 EVELYN DR DOTHAN", the city
            // by the place list in that state.
            if self.places.is_some_and(|c| c.hinted) {
                if let Some(k) = self.place_city(cs, hi) {
                    self.set(k..hi, Tag::City);
                    self.decide(Decision::CityByPlace);
                    return (k, Some(k..hi));
                }
            }
            return (hi, None);
        }

        // APO / FPO / DPO with a military state code takes the city's place.
        let military_state = state.as_ref().is_some_and(|r| {
            self.lex
                .state(&join(&toks[r.clone()]))
                .is_some_and(|l| l.value.kind() == StateKind::Military)
        });
        if military_state && ll_start > lo {
            let k = ll_start - 1;
            if self.lex.military_post_office(self.text(k)).is_some() {
                self.set(k..k + 1, Tag::MilitaryPostOffice);
                return (k, None);
            }
        }
        if ll_start == lo {
            return (lo, None);
        }

        // City.
        let prev = ll_start - 1;
        let city = if toks[prev].seg != toks[ll_start].seg {
            // The last line starts its segment: the city is the segment before.
            let cs = self.seg_start(prev).max(lo);
            let first_seg = toks[cs].seg == toks[lo].seg;
            if !first_seg
                || (self.looks_like_city(cs, ll_start) && !self.known_street(cs, ll_start))
            {
                Some((cs, Decision::CityByComma))
            } else {
                // "626 E KILBOURN AVE MILWAUKEE, WI 53202": the street and
                // the city share the first segment. A segment ending in a
                // suffix or directional is all street (`427 SOUTH LA SALLE
                // STREET, 60605`).
                let last = self.text(prev);
                let street_end =
                    self.lex.suffix(last).is_some() || self.lex.directional(last).is_some();
                if street_end {
                    None
                } else {
                    self.city_in_line(cs, ll_start)
                }
            }
        } else {
            let cs = self.seg_start(prev).max(lo);
            if toks[cs].seg != toks[lo].seg {
                // "..., # 234 SANTA FE NM": a unit starting the city's
                // segment belongs to the street.
                Some((self.after_unit(cs, ll_start), Decision::CityByComma))
            } else {
                // One line with no commas: the city follows the street.
                self.city_in_line(lo, ll_start)
            }
        };
        match city {
            Some((c, how)) if c < ll_start => {
                self.set(c..ll_start, Tag::City);
                self.decide(how);
                (c, Some(c..ll_start))
            }
            _ => (ll_start, None),
        }
    }

    /// Where the city starts in a run with no commas, and the rule that
    /// found it. A place the state data knows wins over the suffix rule
    /// (`MAIN ST WEST PALM BEACH`).
    fn city_in_line(&self, lo: usize, hi: usize) -> Option<(usize, Decision)> {
        self.place_city(lo, hi)
            .map(|c| (self.with_area(lo, c), Decision::CityByPlace))
            .or_else(|| {
                self.city_after_street(lo, hi)
                    .map(|c| (c, Decision::CityBySuffix))
            })
    }

    /// `123 MAIN ST DOWNTOWN MIAMI`: area words right before a known city, and
    /// right after the street's suffix, belong to the city. Returns where the
    /// city starts.
    fn with_area(&self, lo: usize, c: usize) -> usize {
        let seg = self.toks[c].seg;
        let mut k = c;
        while k > lo + 1 && self.toks[k - 1].seg == seg && self.lex.is_area_word(self.text(k - 1)) {
            k -= 1;
        }
        if k < c && k > lo + 1 && self.lex.suffix(self.text(k - 1)).is_some() {
            k
        } else {
            c
        }
    }

    /// The place context for the last line: the state tagged there, else the
    /// state of the ZIP's main place.
    pub(super) fn place_ctx(
        &self,
        state: Option<Range<usize>>,
        zip: Option<usize>,
    ) -> Option<PlaceCtx> {
        let zip = zip
            .and_then(|k| zip_parts(self.text(k)))
            .and_then(|(z5, _)| self.lex.zip_places(z5));
        let (state, hinted) = match state {
            Some(r) => (self.lex.state(&join(&self.toks[r]))?.value.code(), false),
            None => match zip {
                Some(z) => (z.main().state(), false),
                // No state and no known ZIP: the parser's hint, if any.
                None => (self.hint?, true),
            },
        };
        let zip = zip.filter(|z| z.main().state() == state);
        Some(PlaceCtx { state, zip, hinted })
    }

    /// `WINGATE ST, 32507`: with a state data, a first segment of plain words
    /// that ends in a street suffix and is no place the state data knows is the
    /// street, not the city.
    fn known_street(&self, lo: usize, hi: usize) -> bool {
        let Some(ctx) = self.places else {
            return false;
        };
        hi > lo + 1
            && self.lex.suffix(self.text(hi - 1)).is_some()
            && self
                .lex
                .place(ctx.state, &join(&self.toks[lo..hi]))
                .is_none()
    }

    /// In a line with no commas, where the city starts by the state data's
    /// place list: the longest run of words ending at `hi` that is a place,
    /// preferring one the ZIP belongs to. A listed misspelling counts only
    /// when the ZIP agrees. After a house number, a street name must be left
    /// before the city; with no number the whole run may be the city
    /// (`PALM BEACH 33480`).
    pub(super) fn place_city(&self, lo: usize, hi: usize) -> Option<usize> {
        let ctx = self.places?;
        let first_number = lo < hi && house_number(self.text(lo)).is_some();
        let min = if first_number { lo + 2 } else { lo };
        let mut best: Option<(usize, bool)> = None;
        for k in min.max(hi.saturating_sub(MAX_PLACE_WORDS))..hi {
            let run = &self.toks[k..hi];
            if run.iter().any(|t| has_digit(&t.text) || t.is_hash()) {
                continue;
            }
            let Some(hit) = self.lex.place(ctx.state, &join(run)) else {
                continue;
            };
            let agrees = ctx.zip.is_some_and(|z| z.contains(&hit.value));
            if hit.kind != MatchKind::Standard && !agrees {
                continue;
            }
            // Longest first, so a later run replaces it only if the ZIP
            // agrees with it and not with the longer one.
            if !matches!(best, Some((_, a)) if a || !agrees) {
                best = Some((k, agrees));
            }
        }
        if best.is_some() && ctx.hinted {
            self.hint_used.set(true);
        }
        best.map(|(k, _)| k)
    }

    /// A state spelling. `loose` also accepts traditional abbreviations
    /// (FLA), which are only safe right before a ZIP.
    /// The state tokens in `s..e`, without a leading WASHINGTON when the rest
    /// is the District (`WASHINGTON DC 20009` is the city and DC; the whole
    /// phrase is also a spelling of the state itself).
    fn state_span(&self, s: usize, e: usize) -> Range<usize> {
        if e > s + 1
            && self.text(s) == "WASHINGTON"
            && self.lex.state(&join(&self.toks[s + 1..e])).is_some()
        {
            s + 1..e
        } else {
            s..e
        }
    }

    fn state_ok(&self, s: &str, loose: bool) -> Option<()> {
        let l = self.lex.state(s)?;
        (loose || l.kind != MatchKind::Variant).then_some(())
    }

    /// "8517 CEDAR BARK CIR AL": with no ZIP and no city, a USPS state code
    /// or name (`s..e`) ending a one-line street. Never NE or FL (also a
    /// directional and a floor). A code that is also a suffix or highway word
    /// (CT, KY, LA, MT, PR, WY, FM) only right after a suffix written as its
    /// abbreviation (`CIR KY`, not `HIDDEN MEADOW CT`).
    fn state_alone(&self, lo: usize, s: usize, e: usize) -> bool {
        if s < lo + 2 {
            return false;
        }
        let text = join(&self.toks[s..e]);
        let Some(l) = self.lex.state(&text) else {
            return false;
        };
        if l.kind == MatchKind::Variant
            || l.value.kind() == StateKind::Military
            || self.lex.directional(&text).is_some()
            || self.lex.unit(&text).is_some()
        {
            return false;
        }
        let other_word = self.lex.suffix(&text).is_some() || self.lex.highway(&text).is_some();
        !other_word || self.abbreviated_suffix(s - 1)
    }

    /// Whether token `k` is a street suffix written as its Pub 28
    /// abbreviation, shorter than the word (`CIR`; not `CIRCLE`, `MEADOW`,
    /// or `PARK`, whose abbreviation is the word itself).
    fn abbreviated_suffix(&self, k: usize) -> bool {
        let t = self.text(k);
        self.lex
            .suffix(t)
            .is_some_and(|l| l.value.abbr() == t && l.value.name() != t)
    }

    /// The token after a unit (`# 234`, `STE 5`) starting at `k`, or `k` when
    /// there is no unit there or nothing would be left before `hi`.
    fn after_unit(&self, k: usize, hi: usize) -> usize {
        let end = if self.toks[k].is_hash() {
            self.value_at(k, hi).map(|(v, _)| v + 1)
        } else {
            longest_at(self.toks, k, hi, |s| self.lex.unit(s))
                .and_then(|(_, w)| self.value_at(k + w, hi))
                .map(|(v, _)| v + 1)
        };
        match end {
            Some(e) if e < hi => e,
            _ => k,
        }
    }

    /// Whether the first segment, when it is all that comes before the last
    /// line, is a city rather than a street: no digits, and not a PO Box,
    /// route, general delivery or military line.
    fn looks_like_city(&self, lo: usize, hi: usize) -> bool {
        let toks = &self.toks[lo..hi];
        !toks.iter().any(|t| has_digit(&t.text))
            && longest_at(self.toks, lo, hi, |s| self.lex.special(s)).is_none()
            && longest_at(self.toks, lo, hi, |s| self.lex.military(s)).is_none()
    }

    /// Whether `lo..hi` starts with a unit designator or `#` (a second
    /// address line such as `STE 200` or `REAR`).
    fn starts_unit(&self, lo: usize, hi: usize) -> bool {
        self.toks[lo].is_hash() || longest_at(self.toks, lo, hi, |s| self.lex.unit(s)).is_some()
    }

    /// In a line with no commas, where the city starts: after the last
    /// street suffix, its postdirectional and a unit. With no suffix, the
    /// whole run is the city only if it has no digits (`TAMPA 33616`).
    fn city_after_street(&self, lo: usize, hi: usize) -> Option<usize> {
        if lo >= hi {
            return None;
        }
        // "GENERAL DELIVERY JUNEAU", "PO BOX 5 MIAMI".
        if let Some(m) = self.match_special(lo, hi) {
            return (m.end < hi).then_some(m.end);
        }
        let is_suffix = |k: usize| self.lex.suffix(self.text(k)).is_some();
        let first_number = house_number(self.text(lo)).is_some();
        // "3739 COUNTY ROAD 8 LAUREL": a highway route ends the street
        // (section 237), or a suffix after a name past the route
        // ("HWY 66 FRONTAGE RD TULSA").
        let mut start = if first_number { lo + 1 } else { lo };
        if start < hi && is_fraction(self.text(start)) {
            start += 1;
        }
        if let Some(h) = self.highway_at(start, hi) {
            let c = h.route + 1;
            let p = (c + 1..hi).find(|&k| is_suffix(k) && k + 1 < hi && !is_suffix(k + 1));
            return self.after_street(p.map_or(c, |p| p + 1), hi);
        }
        // The street ends at a suffix with a name before it. Prefer the
        // first one followed by a word that is not also a suffix
        // ("12 LAKE SHORE DR CHICAGO"), else the last one.
        let min = if first_number { lo + 2 } else { lo + 1 };
        // `123 MAIN ST LAKE GENEVA`: a suffix, then a word that opens a city
        // and is also a suffix, with a word after it: the street ends at the
        // first suffix.
        let head = (min..hi.saturating_sub(2)).find(|&k| {
            is_suffix(k)
                && self.toks[k + 1].seg == self.toks[k].seg
                && self.lex.is_city_head(self.text(k + 1))
                // `HILL PARK WAY OTIS`: a suffix with more words after it ends
                // the street, so the head belongs to the street name.
                && !(is_suffix(k + 2) && k + 3 < hi)
        });
        let suffix = head
            .or_else(|| (min..hi).find(|&k| is_suffix(k) && k + 1 < hi && !is_suffix(k + 1)))
            .or_else(|| (min..hi).rev().find(|&k| is_suffix(k)));
        let Some(p) = suffix else {
            let digits = self.toks[lo..hi].iter().any(|t| has_digit(&t.text));
            return (!digits).then_some(lo);
        };
        self.after_street(p + 1, hi)
    }

    /// Where the city starts once the street's name ends before `c`: after
    /// a postdirectional and a unit.
    fn after_street(&self, c: usize, hi: usize) -> Option<usize> {
        let mut c = c;
        if c < hi && self.lex.directional(self.text(c)).is_some() {
            // `123 MAIN ST NORTH GLEN ELLYN`: a spelled-out compass word with
            // plain words after it, in the same segment, opens the city (a
            // neighborhood or a `NORTH <town>`). An abbreviation (`N`) stays
            // the postdirectional.
            let opens_city = self.text(c).len() > 2
                && c + 1 < hi
                && self.toks[c + 1].seg == self.toks[c].seg
                && !self.toks[c + 1].is_hash()
                && self.lex.unit(self.text(c + 1)).is_none();
            if opens_city {
                return Some(c);
            }
            // A directional with nothing after it is the postdirectional
            // (`HIGHWAY 29 SOUTH 32533`), not a city.
            c += 1;
        }
        if c + 1 < hi
            && (self.toks[c].is_hash() || self.lex.unit(self.text(c)).is_some())
            && is_unit_value(self.text(c + 1))
        {
            c += 2;
        }
        (c < hi).then_some(c)
    }

    /// Drop a copy of the city at the end of the delivery line, possibly cut
    /// off: `85231 BOSTWICK DR FERNANDINA B` before `FERNANDINA BEACH`,
    /// `SEVENTH AV HILLIARD` before `HILLIARD`.
    /// Returns the new end of the delivery line.
    pub(super) fn drop_city_copy(
        &mut self,
        lo: usize,
        hi: usize,
        city: Option<Range<usize>>,
    ) -> usize {
        let Some(city) = city else { return hi };
        let words: Vec<&str> = self.toks[city].iter().map(|t| t.text.as_str()).collect();
        // Line 2 `CAPE CORAL` with city `CAPE CORAL`: a whole line or comma
        // segment that is the city, even when its first word is a suffix.
        let k = words.len();
        if hi > lo + k {
            let tail = &self.toks[hi - k..hi];
            let whole_seg = self.toks[hi - k - 1].seg != tail[0].seg
                && tail.iter().all(|t| t.seg == tail[0].seg)
                && !self.toks.get(hi).is_some_and(|t| t.seg == tail[0].seg);
            if whole_seg && tail.iter().zip(&words).all(|(t, w)| t.text == *w) {
                self.set(hi - k..hi, Tag::Skip);
                return hi - k;
            }
        }
        for k in (1..=words.len()).rev() {
            if hi < lo + k + 1 {
                continue;
            }
            let tail = &self.toks[hi - k..hi];
            // "UNIT 412 INLET BEACH" before "INLET BEACH": after a whole unit
            // (designator or '#', then a value) an exact copy of the city
            // is dropped even when it starts with a suffix word.
            let s = hi - k;
            let after_unit = s >= lo + 2
                && is_unit_value(self.text(s - 1))
                && (self.toks[s - 2].is_hash() || self.lex.unit(self.text(s - 2)).is_some());
            if after_unit && k == words.len() && tail.iter().zip(&words).all(|(t, w)| t.text == *w)
            {
                self.set(s..hi, Tag::Skip);
                return s;
            }
            // "100 MAIN ST" before "ST PETERSBURG": a suffix is the street's.
            if self.lex.suffix(&tail[0].text).is_some() {
                continue;
            }
            // "SUITE A" before "ARCHER": a value after a designator or '#'
            // is the unit's.
            let before = &self.toks[hi - k - 1];
            if before.is_hash() || self.lex.unit(&before.text).is_some() {
                continue;
            }
            // `123 MAIN ST WEST` before `WEST POINT`: a lone directional right
            // after a suffix or a grid number is the street's postdirectional,
            // not a copy of the city's first word.
            let prev = self.text(hi - k - 1);
            if k == 1
                && self.lex.directional(&tail[0].text).is_some()
                && (self.lex.suffix(prev).is_some()
                    || prev.bytes().all(|c| c.is_ascii_digit())
                    || is_ordinal(prev))
            {
                continue;
            }
            // One cut-off word needs two letters or more; a lone letter is
            // more likely a unit ("DR B") than a copy of "BRADENTON".
            if k == 1 && tail[0].text.len() < 2 && tail[0].text != words[0] {
                continue;
            }
            let matches = tail.iter().enumerate().all(|(n, t)| {
                if n + 1 == k {
                    // A cut-off word is not a directional: `RD NE` before
                    // `NEW SALISBURY` is the street's postdirectional.
                    words[n].starts_with(t.text.as_str())
                        && (t.text == words[n] || self.lex.directional(&t.text).is_none())
                } else {
                    t.text == words[n]
                }
            });
            if matches {
                self.set(hi - k..hi, Tag::Skip);
                return hi - k;
            }
        }
        // `2516 HAMMOCK RD,CLOUD` before `ST CLOUD`: a whole comma segment
        // that repeats the city's last words (the start cut off). Tried last,
        // so a copy across the comma (`RD WESLEY, CHAPEL`) is dropped whole.
        for k in (1..words.len()).rev() {
            if hi <= lo + k + 1 {
                continue;
            }
            let tail = &self.toks[hi - k..hi];
            let whole_seg = self.toks[hi - k - 1].seg != tail[0].seg
                && tail.iter().all(|t| t.seg == tail[0].seg)
                && !self.toks.get(hi).is_some_and(|t| t.seg == tail[0].seg);
            let end = &words[words.len() - k..];
            if whole_seg
                && tail[0].text.len() >= 3
                && tail.iter().zip(end).all(|(t, w)| t.text == *w)
            {
                self.set(hi - k..hi, Tag::Skip);
                return hi - k;
            }
        }
        hi
    }

    // ---- multi-field input -------------------------------------------------

    /// Tag the city field. A trailing state (`BOCA RATON, FL`) is taken as
    /// the state when the state field is empty. Returns the city's tokens.
    pub(super) fn city_field(&mut self, r: Range<usize>, take_state: bool) -> Option<Range<usize>> {
        if r.is_empty() {
            return None;
        }
        if r.len() == 1 && self.lex.military_post_office(self.text(r.start)).is_some() {
            self.set(r, Tag::MilitaryPostOffice);
            return None;
        }
        let mut end = r.end;
        if take_state {
            if let Some((_, w)) =
                longest_ending(self.toks, r.start + 1, r.end, |s| self.state_ok(s, false))
            {
                self.set(r.end - w..r.end, Tag::State);
                end -= w;
            }
        }
        self.set(r.start..end, Tag::City);
        Some(r.start..end)
    }

    pub(super) fn state_field(&mut self, r: Range<usize>) {
        if r.is_empty() {
            return;
        }
        let whole = longest_at(self.toks, r.start, r.end, |s| self.state_ok(s, true))
            .filter(|(_, w)| *w == r.len());
        if whole.is_some() {
            self.set(r, Tag::State);
        } else {
            self.set(r, Tag::Unparsed);
            self.warn(Warning::UnknownState);
        }
    }

    pub(super) fn zip_field(&mut self, r: Range<usize>) {
        if r.is_empty() {
            return;
        }
        if r.len() == 1 && zip_parts(self.text(r.start)).is_some() {
            self.set(r, Tag::Zip);
        } else {
            self.set(r, Tag::Unparsed);
            self.warn(Warning::InvalidZip);
        }
    }

    /// A ZIP at the end of the address line when the ZIP field is empty
    /// (`7702 LILLIAN HWY 32506`). Returns the new end of the line.
    pub(super) fn trailing_zip(&mut self, lo: usize, hi: usize) -> usize {
        if hi >= lo + 2 && zip_parts(self.text(hi - 1)).is_some() && !self.toks[hi - 2].is_hash() {
            self.set(hi - 1..hi, Tag::Zip);
            return hi - 1;
        }
        hi
    }

    /// A ZIP ending the address line that repeats the ZIP already tagged on
    /// the last line (`413 OLD CORRY FIELD RD B 32506` before
    /// `PENSACOLA, FL- 32506`, Escambia). The copy is skipped. Returns the
    /// new end of the line.
    pub(super) fn drop_repeated_zip(&mut self, lo: usize, hi: usize) -> usize {
        if hi < lo + 2 || zip_parts(self.text(hi - 1)).is_none() || self.toks[hi - 2].is_hash() {
            return hi;
        }
        let copy = self.text(hi - 1);
        let repeated = (0..self.toks.len())
            .any(|i| i != hi - 1 && self.tags[i] == Tag::Zip && self.text(i) == copy);
        if repeated {
            self.set(hi - 1..hi, Tag::Skip);
            return hi - 1;
        }
        hi
    }

    /// A state ending the address line that repeats the state already
    /// tagged from its field (`4486 W OAKLAWN ST LECANTO FL` with state
    /// `FL`). The copy is skipped, so the city copy before it can be too.
    /// Not when the code is also the street's own suffix or directional:
    /// `DEBBIE CT` with state `CT` keeps its Court, and `MAIN ST NE` with
    /// state `NE` keeps its postdirectional. Returns the new end of the line.
    pub(super) fn drop_repeated_state(&mut self, lo: usize, hi: usize) -> usize {
        let code = |s: &str| self.lex.state(s).map(|l| l.value.code());
        let field: Vec<_> = (0..self.toks.len())
            .filter(|&i| self.tags[i] == Tag::State)
            .map(|i| self.toks[i].clone())
            .collect();
        let Some(tagged) = code(&join(&field)) else {
            return hi;
        };
        match longest_ending(self.toks, lo + 1, hi, |s| self.state_ok(s, false)) {
            Some((_, w)) if code(&join(&self.toks[hi - w..hi])) == Some(tagged) => {
                if w == 1 && (self.completes_street(lo, hi) || self.floor_word(lo, hi)) {
                    return hi;
                }
                self.set(hi - w..hi, Tag::Skip);
                hi - w
            }
            _ => hi,
        }
    }

    /// The last token (`hi - 1`) is the floor word `FL` right after an ordinal
    /// (`123 MAIN ST 5TH FL`, `THIRD FL`, with state `FL`): a floor, not a copy
    /// of the state (#114), when a street suffix comes before the ordinal (`123
    /// 5TH FL` is the street `5TH`). A city before it (`LECANTO FL`) or a plain number
    /// (`5 FL`, read as unit 5 as before) is not.
    fn floor_word(&self, lo: usize, hi: usize) -> bool {
        if hi < lo + 2 {
            return false;
        }
        let (prev, last) = (self.text(hi - 2), self.text(hi - 1));
        self.lex.unit(last).is_some_and(|l| l.value.abbr() == "FL")
            && self.toks[hi - 2].seg == self.toks[hi - 1].seg
            && (is_ordinal(prev) || spelled_ordinal(prev).is_some())
            && self.suffix_before(lo + 1, hi - 2)
    }

    /// The last token (`hi - 1`) is a street suffix or directional, not just a
    /// copy of the state: a directional always (`MAIN ST NE`); a suffix written
    /// as a Pub 28 spelling (CT, KY, MT, PR, WY; not an observed spelling
    /// such as LA) when the street has no suffix yet (`DEBBIE CT`, but
    /// `OAK ST NORWICH CT` ends in a state copy).
    fn completes_street(&self, lo: usize, hi: usize) -> bool {
        let last = self.text(hi - 1);
        // In the street's own segment: after a comma (`N ELM ST, OAKDALE NE`) the
        // token ends a city and state, not the street.
        if hi - 1 <= lo || self.toks[lo].seg != self.toks[hi - 1].seg {
            return false;
        }
        if self.lex.directional(last).is_some() {
            return true;
        }
        self.lex
            .suffix(last)
            .is_some_and(|l| l.kind != MatchKind::Observed)
            && !(lo..hi - 1).any(|k| self.lex.suffix(self.text(k)).is_some())
    }

    /// The fraction opening line 2 (`123 MAIN ST` / `1/2 APT 3`) is the
    /// fraction of the house number when the delivery pass left it unclaimed.
    pub(super) fn claim_fraction(&mut self, k: usize) {
        if matches!(self.tags[k], Tag::Untagged | Tag::Unparsed)
            && self.tags.contains(&Tag::StreetNumber)
        {
            self.set(k..k + 1, Tag::StreetNumber);
        }
    }

    /// A line 2 of one to three short bare tokens (`2 5`, `4 G`, `B B5`) is a
    /// unit when the delivery pass left it unclaimed, no unit was found yet and the street has
    /// a name. Words do
    /// not qualify: a token is digits, one or two letters, or letters mixed
    /// with digits (up to six characters), and one token holds a digit or is
    /// a single letter.
    pub(super) fn claim_bare_unit(&mut self, r: Range<usize>) {
        let lex = self.lex;
        let free = r
            .clone()
            .all(|k| matches!(self.tags[k], Tag::Untagged | Tag::Unparsed) && !self.toks[k].paren);
        let one_seg = r
            .clone()
            .all(|k| self.toks[k].seg == self.toks[r.start].seg);
        // The street needs a name of its own: `1921 NW` / `46` is a street cut
        // across lines, and a highway or PO Box line takes no bare unit.
        let named = (0..self.toks.len())
            .any(|k| self.tags[k] == Tag::Name && lex.directional(self.text(k)).is_none());
        if r.is_empty() || !free || !one_seg || !named || self.tags.contains(&Tag::UnitNumber(0)) {
            return;
        }
        let tokens = || r.clone().map(|k| self.text(k));
        if !is_bare_unit(tokens())
            || !tokens().all(|t| lex.unit(t).is_none() && !lex.is_placeholder(t))
        {
            return;
        }
        self.set(r, Tag::UnitNumber(0));
        self.decide(Decision::BareUnit);
    }

    /// A lone directional on line 2 that `tag_fields` kept out of the street
    /// (#170) is the unit, with no designator, as a bare letter is.
    pub(super) fn claim_lone_direction(&mut self, r: &Range<usize>, lone: bool) {
        if lone
            && r.clone()
                .all(|k| matches!(self.tags[k], Tag::Untagged | Tag::Unparsed))
            && !self.tags.contains(&Tag::UnitNumber(0))
        {
            self.set(r.clone(), Tag::UnitNumber(0));
            self.decide(Decision::BareUnit);
        }
    }

    // ---- delivery line -----------------------------------------------------

    /// A street field that is only a country (`UNITED STATES`, `USA`) next to a
    /// city, state or ZIP field: dropped, no street (#130). Single-line input
    /// is not touched (`USA` alone stays what it was). Returns whether it was.
    pub(super) fn country_street_line(&mut self, lo: usize, hi: usize) -> bool {
        if lo >= hi
            || !(lo..hi).all(|k| self.toks[k].seg == self.toks[lo].seg)
            || !self.lex.is_country(&join(&self.toks[lo..hi]))
        {
            return false;
        }
        self.set(lo..hi, Tag::Skip);
        self.warn(Warning::CountryIgnored);
        self.warn(Warning::MissingStreetName);
        true
    }

    pub(super) fn delivery(&mut self, lo: usize, hi: usize) {
        let hi = self.department_line(lo, hi);
        let lo = self.co_lead(lo, hi);
        let (lo, hi) = self.attention(lo, hi);
        if self.country_street && self.country_street_line(lo, hi) {
            return;
        }
        let lo = self.name_line(lo, hi);
        let lo = self.leading_recipient(lo, hi);
        if lo >= hi || self.placeholder(lo, hi) {
            return;
        }
        // "PO BOX" with no number: a box word, not a street name (#130). It
        // stays in `unparsed`.
        if (lo..hi).all(|k| self.toks[k].seg == self.toks[lo].seg)
            && (self.lex.is_bare_box_word(&join(&self.toks[lo..hi]))
                || longest_at(self.toks, lo, hi, |s| {
                    self.lex.special(s).filter(|l| l.value == Special::PoBox)
                })
                .is_some_and(|(_, w)| lo + w == hi))
        {
            self.set(lo..hi, Tag::Unparsed);
            return;
        }
        let mut lo = lo;
        while lo < hi && self.toks[lo].is_dash() {
            self.set(lo..lo + 1, Tag::Skip);
            lo += 1;
        }
        // "NULL MAIN ST": a no-data marker where the house number goes is
        // dropped, and the street keeps its own words.
        if hi - lo > 1 && self.lex.is_number_marker(self.text(lo)) {
            self.set(lo..lo + 1, Tag::Skip);
            lo += 1;
        }
        // "N/A - MAGNOLIA AVE": a placeholder prefix before a dash.
        if let Some(d) = (lo..hi).find(|&k| self.toks[k].is_dash()) {
            if d > lo && self.lex.is_placeholder(&join(&self.toks[lo..d])) {
                let rest = &self.toks[d + 1..hi];
                // "NO ADDRESS - 061S311301002007": a trailing parcel code.
                if rest.len() == 1 && has_digit(&rest[0].text) {
                    self.set(lo..hi, Tag::Skip);
                    self.warn(Warning::Placeholder);
                    return;
                }
                self.set(lo..d + 1, Tag::Skip);
                lo = d + 1;
            }
        }
        // "PO BOX 12442 PO BOX 12442": the same line written twice.
        let n = hi - lo;
        if n >= 2 && n % 2 == 0 {
            let half = n / 2;
            let twice = (0..half).all(|k| self.text(lo + k) == self.text(lo + half + k));
            if twice {
                self.set(lo + half..hi, Tag::Skip);
                return self.delivery(lo, lo + half);
            }
        }
        let hi = self.building(lo, hi);
        if lo >= hi || self.dual(lo, hi) || self.stray_box(lo, hi) || self.special_line(lo, hi) {
            return;
        }
        self.street(lo, hi);
    }

    /// A name or building on line 1 (or in the first comma segment) with the
    /// street on the next line: `THE COVE` / `1111 ASBURY WAY`. The first
    /// segment has no digit, is no designator, PO Box or placeholder, and
    /// the next one starts with a house number and a word; the first becomes
    /// the attention line. Returns the start of the address.
    fn name_line(&mut self, lo: usize, hi: usize) -> usize {
        let lex = self.lex;
        if lo >= hi {
            return lo;
        }
        let seg = self.toks[lo].seg;
        let Some(e) = (lo..hi).find(|&k| self.toks[k].seg != seg) else {
            return lo;
        };
        let first = &self.toks[lo..e];
        let plain = first
            .iter()
            .all(|t| !has_digit(&t.text) && !t.is_hash() && !t.is_dash());
        let word =
            |k: usize| lex.special(self.text(k)).is_some() || lex.unit(self.text(k)).is_some();
        if !plain
            || word(lo)
            || lex.is_placeholder(&join(first))
            || house_number(self.text(e)).is_none()
        {
            return lo;
        }
        // The street needs a word of its own after the number (not a unit:
        // `4 APT B`).
        let seg2 = self.toks[e].seg;
        let named = self.toks[e + 1..hi]
            .iter()
            .take_while(|t| t.seg == seg2)
            .any(|t| {
                t.text.len() >= 3
                    && t.text.bytes().all(|c| c.is_ascii_alphabetic())
                    && lex.unit(&t.text).is_none()
            });
        if !named {
            return lo;
        }
        self.set(lo..e, Tag::Attention);
        e
    }

    /// A cut-off copy of the address ahead of the whole address, as some
    /// mailing-address fields write it: `624 E COLONI 624 E COLONIAL DR`. The
    /// house number comes again after words that match the start of what
    /// follows (the last one may be cut short), all in one segment. The copy
    /// is dropped. Returns the start of the address.
    pub(super) fn drop_truncated_copy(&mut self, lo: usize, hi: usize) -> usize {
        if hi < lo + 4 || house_number(self.text(lo)).is_none() {
            return lo;
        }
        let seg = self.toks[lo].seg;
        for k in lo + 2..hi {
            if self.toks[k].seg != seg {
                break;
            }
            if self.text(k) != self.text(lo) {
                continue;
            }
            let m = k - lo - 1;
            if k + 1 + m > hi || (m == 1 && self.text(lo + 1).len() < 2) {
                continue;
            }
            let body = &self.toks[lo + 1..k];
            let rest = &self.toks[k + 1..k + 1 + m];
            let copy = body.iter().zip(rest).enumerate().all(|(i, (b, r))| {
                if i + 1 == m {
                    r.text.starts_with(&b.text)
                } else {
                    b.text == r.text
                }
            });
            // `7848 NW 178S 7848 NW 178ST`, where the tokenizer split `178ST`:
            // the same comparison on the text without word breaks.
            let glued = |ts: &[crate::tokenize::Token]| {
                ts.iter().map(|t| t.text.as_str()).collect::<String>()
            };
            let copy = copy || glued(&self.toks[k + 1..hi]).starts_with(&glued(body));
            if copy {
                self.set(lo..k, Tag::Skip);
                return k;
            }
        }
        lo
    }

    /// A building name at the end of the delivery lines, after the street
    /// or its unit: words ending in a `[building]` word, in their own line
    /// or comma segment (`..., EAST TOWER`, line 2 `ANNEX BUILDING`) or
    /// right after a unit (`SUITE 801 EAST TOWER`). Returns the new end.
    fn building(&mut self, lo: usize, hi: usize) -> usize {
        if hi < lo + 3 || !self.lex.is_building_word(self.text(hi - 1)) {
            return hi;
        }
        let seg = self.toks[hi - 1].seg;
        let mut k = hi - 1;
        while k > lo && self.toks[k - 1].seg == seg {
            let t = self.text(k - 1);
            if has_digit(t) || self.toks[k - 1].is_hash() || self.lex.unit(t).is_some() {
                break;
            }
            k -= 1;
        }
        if hi - k < 2 || k == lo {
            return hi;
        }
        let starts_segment = self.toks[k - 1].seg != seg;
        let after_unit = has_digit(self.text(k - 1))
            && k >= lo + 2
            && (self.toks[k - 2].is_hash() || self.lex.unit(self.text(k - 2)).is_some());
        if !(starts_segment || after_unit) {
            return hi;
        }
        self.set(k..hi, Tag::Building);
        k
    }

    /// Pub 28 section 214: an attention or care-of line (`ATTN LAW DEPT`,
    /// `C/O YMF`), from the ATTN or C/O word to the end of its line or comma
    /// segment, at the start or the end of the delivery lines. Returns the
    /// range left for the address.
    fn attention(&mut self, lo: usize, hi: usize) -> (usize, usize) {
        let lex = self.lex;
        let word = |k: usize| {
            longest_at(self.toks, k, hi, |s| {
                lex.special(s).filter(|l| l.value == Special::Attention)
            })
            .map(|(_, w)| w)
        };
        let Some((k, w)) = (lo..hi).find_map(|k| word(k).map(|w| (k, w))) else {
            return (lo, hi);
        };
        // "C/O 2775 NW 49TH AVE": the address itself follows; only the word
        // is dropped.
        if k + w < hi && house_number(self.text(k + w)).is_some() {
            if let Some(range) = self.care_of_after_street(lo, hi, k, w) {
                return range;
            }
            self.set(k..k + w, Tag::Skip);
            return if k == lo { (k + w, hi) } else { (lo, hi) };
        }
        let end = (k..hi)
            .find(|&e| self.toks[e].seg != self.toks[k].seg)
            .unwrap_or(hi);
        // "C/O ACME CORP 20 QUINCEWOOD CT": the address ends the segment, so
        // the attention line stops before its house number (#127).
        if k == lo {
            if let Some(j) = self.address_start(k + w, end) {
                self.set(k..j, Tag::Attention);
                return self.attention(j, hi);
            }
        }
        if end == hi {
            // "PO BOX 23181 C/O YMF", or line 2 "ATTN: RYAN ADAIR".
            self.set(k..hi, Tag::Attention);
            (lo, k)
        } else if k == lo {
            // Line 1 "C/O ACME HOLDINGS LLC", the street on line 2.
            self.set(lo..end, Tag::Attention);
            (end, hi)
        } else {
            (lo, hi)
        }
    }

    /// The end of the comma segment that holds `k`, at most `hi`.
    fn seg_end(&self, k: usize, hi: usize) -> usize {
        (k..hi)
            .find(|&e| self.toks[e].seg != self.toks[k].seg)
            .unwrap_or(hi)
    }

    /// Whether a street address runs from `j` to `e`: a house number, at least
    /// one name word (no digits, but an ordinal is fine) and a street suffix,
    /// which may be followed by a directional: `20 QUINCEWOOD CT`, `7100
    /// ZEPHYRMILL DR S`, `500 5TH AVE`.
    fn address_at(&self, j: usize, e: usize) -> bool {
        let lex = self.lex;
        if j >= e || house_number(self.text(j)).is_none() {
            return false;
        }
        let mut last = e;
        if last > j + 2 && lex.directional(self.text(last - 1)).is_some() {
            last -= 1;
        }
        if last < j + 3 || lex.suffix(self.text(last - 1)).is_none() {
            return false;
        }
        self.toks[j + 1..last - 1]
            .iter()
            .all(|t| (!has_digit(&t.text) || is_ordinal(&t.text)) && !t.is_hash() && !t.is_dash())
    }

    /// Where the address starts in `from..e`: the last house number that
    /// begins one (see [`Self::address_at`]).
    fn address_start(&self, from: usize, e: usize) -> Option<usize> {
        (from..e).rev().find(|&j| self.address_at(j, e))
    }

    /// Words that can be a recipient name ahead of a street: no digit, hash
    /// or dash, and nothing that belongs to an address (a PO Box or route
    /// word, a unit designator, a directional, a highway prefix; `CO` is read
    /// as the company word it usually is; a single letter and a word such as
    /// `BLOCK`, `NO` or `URB` are not names).
    fn recipient_words(&self, lo: usize, hi: usize) -> bool {
        let lex = self.lex;
        lo < hi
            && hi - lo <= 8
            && (lo..hi).all(|i| {
                let t = self.text(i);
                let highway = longest_at(self.toks, i, hi, |s| lex.highway(s))
                    .is_some_and(|(_, w)| w > 1 || !t.eq_ignore_ascii_case("CO"));
                !has_digit(t)
                    && !is_letter(t)
                    && !lex.is_non_recipient_word(t)
                    && !self.toks[i].is_hash()
                    && !self.toks[i].is_dash()
                    && lex.special(t).is_none()
                    && lex.unit(t).is_none()
                    && lex.directional(t).is_none()
                    && !highway
            })
    }

    /// A department name on a later line or comma segment (`MATH DEPT`,
    /// `HUMAN RESOURCES DEPARTMENT`): two or more words, no digit, ending in
    /// `DEPT` or `DEPARTMENT`. It is the attention line, not a unit without a
    /// number with its words left over (#166). `DEPT 4` keeps being a unit, and
    /// so does a line that starts with a designator that takes a value
    /// (`SUITE B FINANCE DEPT`) or holds a special word (`ATTN ACCOUNTS DEPT`,
    /// `PO BOX`). Returns the end of the delivery lines.
    fn department_line(&mut self, lo: usize, hi: usize) -> usize {
        let lex = self.lex;
        if hi < lo + 3 {
            return hi;
        }
        let seg = self.toks[hi - 1].seg;
        let Some(start) = (lo..hi).find(|&k| self.toks[k].seg == seg) else {
            return hi;
        };
        if start == lo || hi - start < 2 {
            return hi;
        }
        let last = self.text(hi - 1);
        let department = lex.unit(last).is_some_and(|l| l.value.abbr() == "DEPT");
        let plain = (start..hi).all(|k| {
            let t = self.text(k);
            !has_digit(t)
                && !self.toks[k].is_hash()
                && !self.toks[k].is_dash()
                && !self.toks[k].paren
                && lex.special(t).is_none()
        });
        let first_unit = lex
            .unit(self.text(start))
            .is_some_and(|l| l.value.range_required());
        if !department || !plain || first_unit {
            return hi;
        }
        self.set(start..hi, Tag::Attention);
        start
    }

    /// `CO` for `C/O` at the start of a line, when an address follows the
    /// recipient words: `CO ACME INC 120 QUINCEWOOD AVE`, `CO 612 QUINCEWOOD
    /// ST` (not the county highway `CO RD 12` or `CO HWY 612`). Returns the
    /// start of what is left (#127).
    fn co_lead(&mut self, lo: usize, hi: usize) -> usize {
        let lex = self.lex;
        if lo + 1 >= hi || !self.text(lo).eq_ignore_ascii_case("CO") {
            return lo;
        }
        if longest_at(self.toks, lo, hi, |s| lex.highway(s)).is_some_and(|(_, w)| w > 1) {
            return lo;
        }
        let e = self.seg_end(lo, hi);
        let Some(j) = self.address_start(lo + 1, e) else {
            return lo;
        };
        if j == lo + 1 {
            self.set(lo..j, Tag::Skip);
        } else if self.recipient_words(lo + 1, j) {
            self.set(lo..j, Tag::Attention);
        } else {
            return lo;
        }
        j
    }

    /// Recipient words ahead of the address with no marker: `ACME FOUNDATION
    /// 500 BAYVIEW RD`, and a name ahead of a box, `ACME CO PO BOX 12345`.
    /// The words are the attention line (#127).
    fn leading_recipient(&mut self, lo: usize, hi: usize) -> usize {
        if lo >= hi || house_number(self.text(lo)).is_some() {
            return lo;
        }
        let e = self.seg_end(lo, hi);
        // A box that starts the line (`FIRM CALLER 4410`, `PO POX 1234`) has no
        // recipient ahead of it.
        if self.box_line(lo, e, false).is_some() {
            return lo;
        }
        let target = self
            .address_start(lo, e)
            .or_else(|| (lo + 1..e).find(|&k| self.box_line(k, e, false).is_some()));
        match target {
            Some(j) if j > lo && self.recipient_words(lo, j) => {
                self.set(lo..j, Tag::Attention);
                j
            }
            _ => lo,
        }
    }

    /// A care-of marker after a street, followed by a number: `12 OAK AVE` /
    /// `% 5 STAR GROUP`. The number does not start an address when the street
    /// is already there, so the marker's line is the attention line, or a copy
    /// of the street line (`% 12 OAK AVE`, dropped with
    /// [`Warning::SecondLineSkipped`]). A bare number (`% 9`) and a second
    /// address (a plain house number with a suffix, a directional or a unit
    /// after it) are left to the caller. Only a marker that ends the delivery
    /// lines, with its number in the same comma segment (#126).
    fn care_of_after_street(
        &mut self,
        lo: usize,
        hi: usize,
        k: usize,
        w: usize,
    ) -> Option<(usize, usize)> {
        let lex = self.lex;
        // A street, not a lone house number whose street follows the marker.
        if k < lo + 2 || house_number(self.text(lo)).is_none() {
            return None;
        }
        let seg = self.toks[k].seg;
        if (k..hi).any(|e| self.toks[e].seg != seg) || self.toks[k + w].seg != seg {
            return None;
        }
        let rest = k + w..hi;
        if rest.len() < 2 {
            return None;
        }
        let same = |a: &[Token], b: &[Token]| {
            a.len() == b.len()
                && a.iter()
                    .zip(b)
                    .all(|(x, y)| x.text.eq_ignore_ascii_case(&y.text))
        };
        let street = &self.toks[lo..k];
        let line = &self.toks[rest.clone()];
        if same(street, line)
            || (line.len() < street.len() && same(&street[street.len() - line.len()..], line))
        {
            self.set(k..hi, Tag::Skip);
            self.warn(Warning::SecondLineSkipped);
            return Some((lo, k));
        }
        let address = all_digits(self.text(rest.start))
            && self.toks[rest.start + 1..hi].iter().any(|t| {
                lex.suffix(&t.text).is_some()
                    || lex.directional(&t.text).is_some()
                    || lex.unit(&t.text).is_some()
            });
        if address {
            return None;
        }
        self.set(k..hi, Tag::Attention);
        Some((lo, k))
    }

    /// Pub 28 section 215: a street address and a PO Box in one record.
    /// Both are tagged and [`Warning::DualAddress`] is raised. The box may
    /// come first (`PO BOX 286` / `23320 NE HWY 315`) or after the street
    /// (`9418 CUBA RD` / `P.O. BOX 100`, `... AVE PO BOX 365`); the street
    /// needs a house number. A bare `BOX 88` counts only when it starts a
    /// later line or comma segment.
    /// Returns whether the line was one.
    fn dual(&mut self, lo: usize, hi: usize) -> bool {
        if let Some(m) = self.box_line(lo, hi, false) {
            let rest = m.end;
            if rest >= hi || self.starts_unit(rest, hi) {
                return false;
            }
            // The street needs its house number: `PO BOX 3163` / `GRAND
            // CENTRAL STATION` is a box with a postal station, not a street.
            if !(rest + 1 < hi && house_number(self.text(rest)).is_some()) {
                return false;
            }
            for (r, tag) in m.tags {
                self.set(r, tag);
            }
            self.street(rest, hi);
            self.warn(Warning::DualAddress);
            return true;
        }
        if hi < lo + 3 || house_number(self.text(lo)).is_none() {
            return false;
        }
        for k in lo + 2..hi {
            let starts_segment = self.toks[k].seg != self.toks[k - 1].seg;
            let Some(m) = self.box_line(k, hi, starts_segment) else {
                continue;
            };
            for (r, tag) in m.tags {
                self.set(r, tag);
            }
            self.units(m.end, m.end, hi, false);
            self.street(lo, k);
            self.warn(Warning::DualAddress);
            return true;
        }
        false
    }

    /// `P O BOX 8491 N W 17TH STREET`: box words typed in front of a street
    /// address whose house number they took for the box number. The street
    /// is the address and the box words are left unparsed. Only a numbered
    /// street after the number counts (a directional, an ordinal or number
    /// name, a suffix, all on the box's line); `PO BOX 12 N MAIN ST` stays a
    /// box, since a named street there is as likely the box's post office.
    /// Returns whether the line was one.
    fn stray_box(&mut self, lo: usize, hi: usize) -> bool {
        let Some(m) = self.box_line(lo, hi, false) else {
            return false;
        };
        let v = m.end - 1;
        // A plain number, with no `#` between the words and the number.
        if m.tags.len() != 2 || !all_digits(self.text(v)) {
            return false;
        }
        let end = (m.end..hi)
            .find(|&k| self.toks[k].seg != self.toks[lo].seg)
            .unwrap_or(hi);
        let Some((_, w)) = longest_at(self.toks, m.end, end, |s| self.lex.directional(s)) else {
            return false;
        };
        let name = m.end + w;
        let numbered =
            name + 2 == end && (is_ordinal(self.text(name)) || all_digits(self.text(name)));
        if !numbered || self.lex.suffix(self.text(end - 1)).is_none() {
            return false;
        }
        self.set(lo..v, Tag::Unparsed);
        self.street_from(v, hi);
        true
    }

    /// A PO Box (`PO BOX 12`, `DRAWER 9`, or with `bare` a plain `BOX 88`)
    /// and its value at `k`, without tagging.
    fn box_line(&self, k: usize, hi: usize, bare: bool) -> Option<SpecialMatch> {
        let (l, w) = longest_at(self.toks, k, hi, |s| self.lex.special(s))?;
        if !(l.value == Special::PoBox || bare && l.value == Special::Box) {
            return None;
        }
        let (v, hash) = self.value_at(k + w, hi)?;
        let mut tags = vec![(k..k + w, Tag::PoBox)];
        if hash {
            tags.push((v - 1..v, Tag::Skip));
        }
        tags.push((v..v + 1, Tag::PoBoxNumber));
        Some(SpecialMatch {
            tags,
            end: v + 1,
            units: true,
        })
    }

    fn placeholder(&mut self, lo: usize, hi: usize) -> bool {
        if self.lex.is_placeholder(&join(&self.toks[lo..hi])) {
            self.set(lo..hi, Tag::Skip);
            self.warn(Warning::Placeholder);
            return true;
        }
        false
    }

    /// A `#`-optional value at `k`: returns the value's index.
    fn value_at(&self, k: usize, hi: usize) -> Option<(usize, bool)> {
        let hash = k < hi && self.toks[k].is_hash();
        let v = if hash { k + 1 } else { k };
        (v < hi && is_unit_value(self.text(v))).then_some((v, hash))
    }

    /// General delivery, PO Box, rural route, highway contract route and
    /// military box lines. Returns whether the line was one of these.
    fn special_line(&mut self, lo: usize, hi: usize) -> bool {
        let Some(m) = self.match_special(lo, hi) else {
            return false;
        };
        for (r, tag) in m.tags {
            self.set(r, tag);
        }
        if m.units {
            self.units(m.end, m.end, hi, false);
        }
        true
    }

    /// Match a special delivery line starting at `lo`, without tagging.
    fn match_special(&self, lo: usize, hi: usize) -> Option<SpecialMatch> {
        let lex = self.lex;
        let special = longest_at(self.toks, lo, hi, |s| lex.special(s));
        let mut tags = Vec::new();
        let value = |tags: &mut Vec<(Range<usize>, Tag)>, v: usize, hash: bool, tag: Tag| {
            if hash {
                tags.push((v - 1..v, Tag::Skip));
            }
            tags.push((v..v + 1, tag));
        };

        if let Some((l, w)) = special {
            match l.value {
                // Pub 28 section 261.
                Special::GeneralDelivery => {
                    tags.push((lo..lo + w, Tag::GeneralDelivery));
                    return Some(SpecialMatch {
                        tags,
                        end: lo + w,
                        units: false,
                    });
                }
                // Pub 28 sections 281 and 283.
                Special::PoBox => {
                    if let Some((v, hash)) = self.value_at(lo + w, hi) {
                        tags.push((lo..lo + w, Tag::PoBox));
                        value(&mut tags, v, hash, Tag::PoBoxNumber);
                        return Some(SpecialMatch {
                            tags,
                            end: v + 1,
                            units: true,
                        });
                    }
                }
                // Pub 28 sections 241-244 and 251-253. Forms that are also
                // street words (RD, RTE, ROUTE) count only with a BOX after
                // the route.
                Special::RuralRoute | Special::HighwayContract => {
                    let form = join(&self.toks[lo..lo + w]);
                    let ambiguous = lex.highway(&form).is_some() || lex.suffix(&form).is_some();
                    if let Some((route, hash)) = self.value_at(lo + w, hi) {
                        let bx = self.box_part(route + 1, hi);
                        if bx.is_some() || !ambiguous {
                            tags.push((lo..lo + w, Tag::Route));
                            value(&mut tags, route, hash, Tag::RouteNumber);
                            let mut end = route + 1;
                            if let Some((word, v)) = bx {
                                tags.push((word.start..v, Tag::Skip));
                                tags.push((v..v + 1, Tag::BoxNumber));
                                end = v + 1;
                                // `RR 2 BOX 45 A`: a lone letter after a
                                // numeric box is part of it (#95).
                                if end < hi
                                    && all_digits(self.text(v))
                                    && is_letter(self.text(end))
                                    && self.toks[end].seg == self.toks[v].seg
                                {
                                    tags.push((end..end + 1, Tag::BoxLetter));
                                    end += 1;
                                }
                            }
                            return Some(SpecialMatch {
                                tags,
                                end,
                                units: true,
                            });
                        }
                    }
                }
                Special::Box => {
                    if let Some((v, hash)) = self.value_at(lo + w, hi) {
                        // Section 238.1 writes PSC 103 BOX 2877; the reverse
                        // (`BOX 2877 PSC 103`) is read the same way.
                        if let Some((_, mw)) = longest_at(self.toks, v + 1, hi, |s| lex.military(s))
                        {
                            if let Some((num, nhash)) = self.value_at(v + 1 + mw, hi) {
                                tags.push((lo..lo + w, Tag::Skip));
                                value(&mut tags, v, hash, Tag::MilitaryBoxNumber);
                                tags.push((v + 1..v + 1 + mw, Tag::MilitaryKind));
                                value(&mut tags, num, nhash, Tag::MilitaryNumber);
                                return Some(SpecialMatch {
                                    tags,
                                    end: num + 1,
                                    units: false,
                                });
                            }
                        }
                        // `BOX 123456` alone on the line is a PO Box.
                        if v + 1 == hi {
                            tags.push((lo..lo + w, Tag::PoBox));
                            value(&mut tags, v, hash, Tag::PoBoxNumber);
                            return Some(SpecialMatch {
                                tags,
                                end: hi,
                                units: false,
                            });
                        }
                    }
                }
                Special::Attention => {}
            }
        }

        // Pub 28 sections 238.1 and 239: TYPE ## BOX ##.
        let (_, w) = longest_at(self.toks, lo, hi, |s| lex.military(s))?;
        let (num, hash) = self.value_at(lo + w, hi)?;
        let (word, v) = self.box_part(num + 1, hi)?;
        tags.push((lo..lo + w, Tag::MilitaryKind));
        value(&mut tags, num, hash, Tag::MilitaryNumber);
        tags.push((word.start..v, Tag::Skip));
        tags.push((v..v + 1, Tag::MilitaryBoxNumber));
        Some(SpecialMatch {
            tags,
            end: v + 1,
            units: false,
        })
    }

    /// `BOX 152` (or `PO BOX`, `#`) at `k`: the box word's range and the
    /// value's index.
    fn box_part(&self, k: usize, hi: usize) -> Option<(Range<usize>, usize)> {
        let lex = self.lex;
        let (_, w) = longest_at(self.toks, k, hi, |s| {
            lex.special(s)
                .filter(|l| matches!(l.value, Special::Box | Special::PoBox))
        })?;
        let (v, _) = self.value_at(k + w, hi)?;
        Some((k..k + w, v))
    }

    /// A street address: number, highway or name, suffix, directionals and
    /// up to two units.
    fn street(&mut self, lo: usize, hi: usize) {
        // "APT 1B 626 E KILBOURN AVE": a unit before the street. A unit
        // found after the street becomes the second one.
        let Some(start) = self.leading_unit(lo, hi) else {
            return self.street_from(lo, hi);
        };
        self.street_from(start, hi);
        for t in &mut self.tags[start..hi] {
            match *t {
                Tag::UnitType(0) => *t = Tag::UnitType(1),
                Tag::UnitNumber(0) => *t = Tag::UnitNumber(1),
                _ => {}
            }
        }
    }

    /// A unit (`APT 1B`, `# 5`) at `lo` followed by a house number: tags it
    /// and returns where the street starts.
    fn leading_unit(&mut self, lo: usize, hi: usize) -> Option<usize> {
        let (ty, k) = if self.toks[lo].is_hash() {
            (lo..lo, lo)
        } else {
            let (_, w) = longest_at(self.toks, lo, hi, |s| self.lex.unit(s))?;
            (lo..lo + w, lo + w)
        };
        let (v, hash) = self.value_at(k, hi)?;
        let start = v + 1;
        if start + 1 >= hi || house_number(self.text(start)).is_none() {
            return None;
        }
        self.set(ty, Tag::UnitType(0));
        if hash {
            self.set(v - 1..v, Tag::Skip);
        }
        self.set(v..v + 1, Tag::UnitNumber(0));
        Some(start)
    }

    /// Whether the number word at `lo` (`ONE` to `TWENTY`) is the house number:
    /// a name and a street suffix follow in its segment, with at most five
    /// words after the suffix (a postdirectional, a unit). Not when the first
    /// name word makes a numbered street of it (`ONE MILE RD`, `THREE FORKS
    /// RD`, from `[numbered_street]`) or is a unit designator or a highway
    /// prefix (#129).
    fn spelled_house_number(&self, lo: usize, hi: usize) -> bool {
        let lex = self.lex;
        if spelled_number(self.text(lo)).is_none() || hi < lo + 3 {
            return false;
        }
        let e = self.seg_end(lo, hi);
        let dir = longest_at(self.toks, lo + 1, e, |s| lex.directional(s)).map_or(0, |(_, w)| w);
        let n0 = lo + 1 + dir;
        if n0 + 1 >= e {
            return false;
        }
        let first = self.text(n0);
        if lex.is_numbered_street_word(first)
            || lex.unit(first).is_some()
            || lex.highway(first).is_some()
            || lex.suffix(first).is_some()
            || has_digit(first)
        {
            return false;
        }
        let Some(s) = (n0 + 1..e).find(|&s| lex.suffix(self.text(s)).is_some()) else {
            return false;
        };
        e - s - 1 <= 5
    }

    /// A second plain house number at `k`, right after the first
    /// (`1309 1329 E VINE ST`): both are three or more digits, and a whole
    /// street follows on the line: an optional directional, at least one
    /// name word, and the suffix ending the line. Rural grid streets named
    /// by a number and a direction (`2900 N`, `1575 NORTH AVE`,
    /// `275 NORTH RD E`) lack that shape and stay in the name, and so does a
    /// numbered street with a split ordinal (`139 TH AVE`).
    fn second_house_number(&self, k: usize, hi: usize) -> bool {
        let long = |t: &str| all_digits(t) && t.len() >= 3;
        let line_end = (k..hi)
            .find(|&e| self.toks[e].seg != self.toks[k].seg)
            .unwrap_or(hi);
        if k < 1 || k + 2 >= line_end || !long(self.text(k - 1)) || !long(self.text(k)) {
            return false;
        }
        let dir = longest_at(self.toks, k + 1, line_end, |s| self.lex.directional(s))
            .map_or(0, |(_, w)| w);
        let name = k + 1 + dir;
        name + 1 < line_end
            && self.lex.suffix(self.text(line_end - 1)).is_some()
            && self.lex.suffix(self.text(name)).is_none()
            && !ORDINAL_SUFFIXES.contains(&self.text(name))
    }

    fn street_from(&mut self, lo: usize, hi: usize) {
        let mut i = lo;
        let t0 = self.text(i);
        if is_glued_ordinal(t0) {
            // "409742ND SQ": 4097 42ND or 40974 2ND. Don't guess.
            self.warn(Warning::AmbiguousStreetNumber);
            self.set(lo..hi, Tag::Unparsed);
            return;
        }
        // "31967,32037,32067, PUNTA GORDA": a list of house numbers, each in
        // its own comma segment.
        let numbers = (lo..hi)
            .take_while(|&k| {
                all_digits(self.text(k)) && (k == lo || self.toks[k].seg != self.toks[k - 1].seg)
            })
            .count();
        if numbers >= 2 {
            self.warn(Warning::MultipleAddresses);
            self.set(lo..lo + numbers, Tag::Unparsed);
            i += numbers;
        } else if is_slash_pair(t0) {
            // "5210/5212 BRISTO ST"
            self.warn(Warning::MultipleAddresses);
            self.set(i..i + 1, Tag::Unparsed);
            i += 1;
        } else if hi == lo + 1 && all_digits(t0) && !t0.bytes().all(|c| c == b'0') {
            // "4871" alone: a house number and no street (#130).
            self.set(i..i + 1, Tag::StreetNumber);
            self.warn(Warning::MissingStreetName);
            i += 1;
        } else if self.spelled_house_number(lo, hi) {
            // "ONE COMMERCE PLAZA": the number word is the house number; the
            // assembler writes it as a digit.
            self.set(i..i + 1, Tag::StreetNumber);
            i += 1;
        } else if let Some(shape) = house_number(t0).filter(|_| hi > lo + 1) {
            if t0.bytes().all(|c| c == b'0') {
                self.set(i..i + 1, Tag::Skip);
                self.zero_number = true;
                self.warn(Warning::ZeroStreetNumber);
            } else {
                self.set(i..i + 1, Tag::StreetNumber);
                if shape == NumberShape::Range {
                    self.warn(Warning::MultipleAddresses);
                }
            }
            i += 1;
            if i < hi && is_fraction(self.text(i)) {
                self.set(i..i + 1, Tag::StreetNumber);
                i += 1;
            } else if i < hi && is_grid_number(t0) && is_grid_number(self.text(i)) {
                // "N165 W2123": a grid number written in two parts.
                self.set(i..i + 1, Tag::StreetNumber);
                i += 1;
            } else if i + 1 < hi && self.number_letter(i) {
                // "428 B SOUTH MAIN ST": the letter belongs to the number.
                self.set(i..i + 1, Tag::StreetNumber);
                self.decide(Decision::NumberLetter);
                i += 1;
            }
            // "1309 1329 E VINE ST": more house numbers. The first is the
            // address's; the rest are left unparsed.
            while self.second_house_number(i, hi) {
                self.set(i..i + 1, Tag::Unparsed);
                self.warn(Warning::MultipleAddresses);
                i += 1;
            }
        }
        if i >= hi {
            return;
        }

        if let Some(h) = self.highway_at(i, hi) {
            let floor = h.route + 1;
            // The route anchors the units after it, as a name does (`HWY A1A`
            // then a line `405` is unit 405).
            let j = self.units(floor, h.route.saturating_sub(1), hi, true);
            self.set(h.pre.clone(), Tag::PreDir);
            self.set(h.state.clone(), Tag::HighwayState);
            self.set(h.prefix.clone(), Tag::HighwayPrefix);
            self.set(h.route..h.route + 1, Tag::HighwayRoute);
            // `SR 60` under a Florida hint: a spelling only the hinted
            // state's data has.
            let hinted = self.places.is_some_and(|c| c.hinted) && !h.prefix.is_empty();
            if hinted
                && self
                    .lex
                    .highway(&join(&self.toks[h.prefix.clone()]))
                    .is_none()
            {
                self.decide(Decision::DefaultState);
            }
            // Words after the route are the street's only on the route's
            // line or comma segment; the rest is left unparsed.
            let seg = self.toks[h.route].seg;
            let line_end = (floor..j).find(|&k| self.toks[k].seg != seg).unwrap_or(j);
            self.street_tail(floor, line_end);
            return;
        }

        let j = self.units(i, i, hi, true);
        // The name and suffix come from the first line; whatever is left of
        // a later line ("..., BLDG 5 ROOM") is not part of the name.
        let mut line_end = (i..j)
            .find(|&k| self.toks[k].seg != self.toks[i].seg)
            .unwrap_or(j);
        // "2272 GOODWOOD BLVD., SE": a postdirectional after a comma.
        let rest = line_end..j;
        if !rest.is_empty()
            && self.toks[rest.clone()]
                .iter()
                .all(|t| t.seg == self.toks[rest.start].seg)
            && longest_at(self.toks, rest.start, j, |s| self.lex.directional(s))
                .is_some_and(|(_, w)| w == rest.len())
        {
            line_end = j;
        }
        if self.street_continues(i, line_end, j) {
            line_end = j;
        }
        self.street_body(i, line_end, hi.min(line_end));
    }

    /// A street cut across lines (`8725 NW` / `18 TER`, `5424 EDGEWATER` /
    /// `AVE`): the first line's part `i..e` has no suffix, and the rest
    /// `e..j`, one line or comma segment, is a suffix with at most a number
    /// before it and a directional after it.
    fn street_continues(&self, i: usize, e: usize, j: usize) -> bool {
        if i >= e || e >= j || self.lex.suffix(self.text(e - 1)).is_some() {
            return false;
        }
        let rest = &self.toks[e..j];
        if rest.iter().any(|t| t.seg != rest[0].seg) || rest[0].seg == self.toks[e - 1].seg {
            return false;
        }
        let mut k = j;
        if let Some((_, w)) = longest_ending(self.toks, e, k, |s| self.lex.directional(s)) {
            k -= w;
        }
        let is_number = |t: &str| all_digits(t) || is_ordinal(t);
        match k - e {
            1 => self.lex.suffix(self.text(e)).is_some(),
            2 => is_number(self.text(e)) && self.lex.suffix(self.text(e + 1)).is_some(),
            _ => false,
        }
    }

    /// Whether the single letter at `k` belongs to the house number before
    /// it (`428 B SOUTH MAIN ST`): not a directional itself (`123 N MAIN`),
    /// and followed by a directional. A name word after it would make the
    /// letter an initial (`820 A PHILIP RANDOLPH BLVD`, `9058 T BIRD RD`).
    fn number_letter(&self, k: usize) -> bool {
        let t = self.text(k);
        is_letter(t)
            && self.lex.directional(t).is_none()
            && self.lex.directional(self.text(k + 1)).is_some()
            // "U S ROUTE 40" is the US highway, not number 20192U.
            && !(t == "U" && self.text(k + 1) == "S")
    }

    /// Whether the tokens in `r` are the penthouse designator.
    fn is_penthouse(&self, r: &Range<usize>) -> bool {
        r.len() == 1
            && self
                .lex
                .unit(self.text(r.start))
                .is_some_and(|u| u.value.abbr() == "PH")
    }

    /// Pub 28 section 237 and Appendix F: a highway prefix and route right
    /// after the house number (and an optional predirectional). Appendix F
    /// also names a state before the prefix (`KY STATE HIGHWAY 1`), or before
    /// the route alone (`KENTUCKY 440`); those are tried last, so `NE HWY 5`
    /// keeps NE as the predirectional.
    fn highway_at(&self, i: usize, hi: usize) -> Option<HighwayAt> {
        let lex = self.lex;
        // A state data may add prefix spellings (`SR` in Florida).
        let state = self.places.map(|c| c.state);
        let try_at = |p: usize| {
            let (l, w) = longest_at(self.toks, p, hi, |s| match state {
                Some(st) => lex.highway_in(st, s),
                None => lex.highway(s),
            })?;
            let route = p + w;
            // Appendix F allows letter routes (`STATE ROUTE MM`); taken only
            // after a county prefix (`COUNTY ROAD J`), where a letter is
            // otherwise easy to read as a unit.
            let county = matches!(l.value.standard(), "COUNTY ROAD" | "COUNTY HIGHWAY");
            let letters = |t: &str| t.len() <= 2 && t.bytes().all(|c| c.is_ascii_alphabetic());
            let r = self.text(route);
            let ok =
                route < hi && (is_route_value(r) || is_lettered_route(r) || county && letters(r));
            ok.then_some((p..p + w, route))
        };
        if let Some((prefix, route)) = try_at(i) {
            return Some(HighwayAt {
                pre: i..i,
                state: i..i,
                prefix,
                route,
            });
        }
        if let Some((_, w)) = longest_at(self.toks, i, hi, |s| lex.directional(s)) {
            if let Some((prefix, route)) = try_at(i + w) {
                return Some(HighwayAt {
                    pre: i..i + w,
                    state: i + w..i + w,
                    prefix,
                    route,
                });
            }
        }
        let (_, w) = longest_at(self.toks, i, hi, |s| self.highway_state(s))?;
        let state = i..i + w;
        if let Some((prefix, route)) = try_at(i + w) {
            return Some(HighwayAt {
                pre: i..i,
                state,
                prefix,
                route,
            });
        }
        // Bare `KY 1207`: digits only, and not a directional that happens to
        // be a state code (`NE 5TH ST`). A state code that is also a
        // designator counts too (`5100 FL 40 SUITE 100`): this is the start of
        // the street, and read as a floor it would leave no street name.
        let route = i + w;
        let word = join(&self.toks[state.clone()]);
        let bare = route < hi && all_digits(self.text(route)) && lex.directional(&word).is_none();
        bare.then_some(HighwayAt {
            pre: i..i,
            state,
            prefix: route..route,
            route,
        })
    }

    /// A state code or full name (not a traditional abbreviation such as
    /// KENT, nor a military code) inside a highway name.
    fn highway_state(&self, s: &str) -> Option<()> {
        let l = self.lex.state(s)?;
        (l.kind != MatchKind::Variant && l.value.kind() != StateKind::Military).then_some(())
    }

    /// After a highway route: a postdirectional and a suffix, anything else
    /// is part of the name (`HWY 66 FRONTAGE RD`).
    fn street_tail(&mut self, i: usize, j: usize) {
        let mut j = j;
        if let Some((_, w)) = longest_ending(self.toks, i, j, |s| self.lex.directional(s)) {
            self.set(j - w..j, Tag::PostDir);
            j -= w;
        }
        if j > i && self.lex.suffix(self.text(j - 1)).is_some() {
            self.set(j - 1..j, Tag::Suffix);
            j -= 1;
        }
        self.set(i..j, Tag::Name);
    }

    /// Predirectional, name, suffix and postdirectional in `i..j` (Pub 28
    /// section 233). `hi` is the end of the whole delivery line.
    fn street_body(&mut self, i: usize, j: usize, hi: usize) {
        let lex = self.lex;
        let (mut i, mut j) = (i, j);
        if i >= j {
            return;
        }
        // Postdirectional, unless it is a letter naming the street right
        // after a lone suffix word ("AVENUE N", like "AVENUE G").
        if j >= i + 2 {
            if let Some((_, w)) = longest_ending(self.toks, i + 1, j, |s| lex.directional(s)) {
                let k = j - w;
                let letter = self.text(k).len() == 1;
                let lone_suffix = k == i + 1 && lex.suffix(self.text(i)).is_some();
                if !(letter && lone_suffix) {
                    self.set(k..j, Tag::PostDir);
                    j = k;
                }
            }
        }
        // Suffix, when a name is left before it.
        let mut suffix_taken = false;
        if j >= i + 2 && lex.suffix(self.text(j - 1)).is_some() {
            self.set(j - 1..j, Tag::Suffix);
            j -= 1;
            suffix_taken = true;
        }
        // Predirectional, when a name is left after it.
        if let Some((_, w)) = longest_at(self.toks, i, j, |s| lex.directional(s)) {
            if i + w < j {
                self.set(i..i + w, Tag::PreDir);
                i += w;
            }
        }
        self.set(i..j, Tag::Name);
        // A name with no suffix at the very end may be cut off ("CUTOF").
        if !suffix_taken && j == hi && j > i && self.tags[j - 1] == Tag::Name {
            self.incomplete = Some(j - 1);
        }
    }

    /// Whether a street suffix (with a name before it) ends right before
    /// token `k`, allowing a postdirectional in between. Highway words are
    /// excluded: after HWY a number is the route, not a unit. `ROAD` and `LOOP`
    /// are highway words that are suffixes after a name (`MAPLE COVE LOOP 412`,
    /// #145); `LOOP 410` at the start of the street is still a route.
    fn suffix_before(&self, name_lo: usize, k: usize) -> bool {
        let lex = self.lex;
        let mut s = k;
        if s > name_lo && lex.directional(self.text(s - 1)).is_some() {
            s -= 1;
        }
        if s == 0 || s <= name_lo {
            return false;
        }
        let sfx = s - 1;
        let word = self.text(sfx);
        let highway = lex
            .highway(word)
            .is_some_and(|h| !matches!(h.value.standard(), "ROAD" | "LOOP"));
        // A leading directional is the predirectional, not the name:
        // "147 SE AVENUE A" has no name before AVENUE, so A is not a unit.
        let mut name_start = name_lo;
        if lex.directional(self.text(name_lo)).is_some() {
            name_start += 1;
        }
        lex.suffix(word).is_some() && !highway && sfx > name_start
    }

    /// Whether `BAY` at `k` ends the street's name rather than naming a unit
    /// (`HERON BAY # 2B`, `OYSTER BAY 4`): a name word (no digit) comes before it
    /// in the street's own segment and no street suffix does. `BAY` is a unit (an
    /// industrial bay) after a suffix (`MAIN ST BAY 4`) or on a later line
    /// (#144).
    fn bay_in_name(&self, name_lo: usize, k: usize) -> bool {
        k > name_lo
            && k < self.toks.len()
            && self.text(k) == "BAY"
            && self.toks[k].seg == self.toks[name_lo].seg
            && !self.toks[k - 1].is_hash()
            && !has_digit(self.text(k - 1))
            && !self.suffix_before(name_lo, k)
    }

    /// Whether the value at `last` follows a street name that ends in `BAY`,
    /// with a postdirectional between them or not (`HERON BAY 2B`, `HERON BAY
    /// W 2B`).
    fn bay_before_value(&self, name_lo: usize, last: usize) -> bool {
        let Some(mut k) = last.checked_sub(1) else {
            return false;
        };
        if k > name_lo && self.lex.directional(self.text(k)).is_some() {
            k -= 1;
        }
        self.bay_in_name(name_lo, k)
    }

    /// Whether tokens `last - 1` and `last` are two numbers right after a
    /// designator or `#`, one unit value written in two parts: `STE 180
    /// 417020`, `FL 2 270` (#128).
    fn number_pair(&self, floor: usize, last: usize) -> bool {
        if last < floor + 2 {
            return false;
        }
        let v = last - 1;
        let seg = self.toks[last].seg;
        all_digits(self.text(last))
            && all_digits(self.text(v))
            && self.toks[v].seg == seg
            && self.toks[v - 1].seg == seg
            && (self.toks[v - 1].is_hash()
                || longest_ending(self.toks, floor, v, |s| {
                    self.lex.unit(s).filter(|l| l.kind != MatchKind::Observed)
                })
                .is_some())
    }

    /// Whether tokens `last - 1` and `last` are one unit value written in two
    /// parts, a letter and a number in either order, right after a designator
    /// or `#`: `APT E 1003`, `UNIT 210 C`, and `# V 21`, the form the USPS
    /// emitter writes for a bare `DR V 21`.
    fn split_value(&self, floor: usize, last: usize) -> bool {
        if last < floor + 2 {
            return false;
        }
        let (a, b) = (self.text(last - 1), self.text(last));
        let pair = is_letter(a) && all_digits(b) || all_digits(a) && is_letter(b);
        let v = last - 1;
        let seg = self.toks[last].seg;
        let one_seg = self.toks[v].seg == seg && self.toks[v - 1].seg == seg;
        pair && one_seg
            && (self.toks[v - 1].is_hash()
                || longest_ending(self.toks, floor, v, |s| self.lex.unit(s)).is_some())
    }

    /// `# 2 5`, `# B B5`: up to three short tokens in one segment after a
    /// `#` are one unit value. Returns where the run starts (`last` is its
    /// final token), or `None` for a single token.
    fn hash_run(&self, floor: usize, last: usize) -> Option<usize> {
        let seg = self.toks[last].seg;
        (last.saturating_sub(2).max(floor + 1)..last).find(|&s| {
            self.toks[s - 1].is_hash()
                && (s..=last).all(|k| self.toks[k].seg == seg && !self.toks[k].paren)
                && is_bare_unit((s..=last).map(|k| self.text(k)))
        })
    }

    /// `UNIT 3 & 4`, `SUITE 5 AND 6`: two unit values joined by `&` or `AND`
    /// in one segment, right after a designator or `#`. Returns where the
    /// pair starts (`last` is its final token).
    fn and_pair(&self, floor: usize, last: usize) -> Option<usize> {
        if last < floor + 3 {
            return None;
        }
        let s = last - 2;
        let seg = self.toks[last].seg;
        let joined = self.lex.is_value_joiner(self.text(last - 1));
        let after_designator = self.toks[s - 1].is_hash()
            || longest_ending(self.toks, floor, s, |u| {
                self.lex.unit(u).filter(|l| l.kind != MatchKind::Observed)
            })
            .is_some();
        (joined
            && self.toks[last - 1].seg == seg
            && self.toks[s].seg == seg
            && is_unit_value(self.text(s))
            && is_unit_value(self.text(last))
            && after_designator)
            .then_some(s)
    }

    /// `UNIT 12 BLU SPA`: one to three words after a whole unit (a designator
    /// or `#`, then a value with a digit) in one segment are the tenant or
    /// business name, not part of the unit. Returns where the words start.
    fn words_after_unit(&self, floor: usize, hi: usize) -> Option<usize> {
        let lex = self.lex;
        for k in 1..=3usize {
            if hi < floor + k + 2 {
                break;
            }
            let start = hi - k;
            let seg = self.toks[hi - 1].seg;
            let word = |t: &Token| {
                t.seg == seg
                    && !t.paren
                    && t.text.len() >= 3
                    && t.text.bytes().all(|c| c.is_ascii_alphabetic())
                    && lex.unit(&t.text).is_none()
                    && lex.suffix(&t.text).is_none()
                    && lex.directional(&t.text).is_none()
                    && lex.state(&t.text).is_none()
            };
            if !self.toks[start..hi].iter().all(word) {
                break;
            }
            let value = start - 1;
            if self.toks[value].seg != seg
                || !is_unit_value(self.text(value))
                || !has_digit(self.text(value))
            {
                continue;
            }
            let designator = self.toks[value - 1].seg == seg
                && (self.toks[value - 1].is_hash()
                    || lex.unit(self.text(value - 1)).is_some_and(|l| {
                        l.kind != MatchKind::Observed && l.value.range_required()
                    }));
            if designator {
                return Some(start);
            }
        }
        None
    }

    /// `SUITE TWO`, `APT NINE`: a spelled-out number right after a designator
    /// that takes a value (#129).
    fn spelled_after_designator(&self, floor: usize, last: usize) -> bool {
        last > floor
            && spelled_number(self.text(last)).is_some()
            && self.toks[last].seg == self.toks[last - 1].seg
            && longest_ending(self.toks, floor, last, |s| {
                self.lex
                    .unit(s)
                    .filter(|l| l.kind != MatchKind::Observed && l.value.range_required())
            })
            .is_some()
    }

    /// `APT TD`, `UNIT AB`: two letters right after a designator that always
    /// takes a value. Others are street words (`FRONT ST`, `UPPER RD`), and a suffix
    /// or directional after the designator ends a street (`KEY RD`).
    fn letters_after_designator(&self, floor: usize, last: usize) -> bool {
        let t = self.text(last);
        last > floor
            && t.len() == 2
            && t.bytes().all(|c| c.is_ascii_alphabetic())
            && self.lex.suffix(t).is_none()
            && self.lex.directional(t).is_none()
            && self.toks[last].seg == self.toks[last - 1].seg
            && longest_ending(self.toks, floor, last, |s| {
                self.lex
                    .unit(s)
                    .filter(|l| l.kind != MatchKind::Observed && l.value.range_required())
            })
            .is_some()
    }

    /// Up to two units at the end of `floor..hi`, read from the right.
    /// `name_lo` is where the street name starts (for the bare-unit rule).
    /// Returns the new end of the street.
    fn units(&mut self, floor: usize, name_lo: usize, hi: usize, bare: bool) -> usize {
        let lex = self.lex;
        let mut j = hi;
        let mut found: Vec<(Range<usize>, Range<usize>)> = Vec::new();
        while found.len() < 2 && j > floor {
            let last = j - 1;
            let t = self.text(last);
            // "(110)" is a unit; "(OFF)" is not.
            if self.toks[last].paren {
                if is_unit_value(t) {
                    found.push((last..last, last..j));
                } else {
                    self.set(last..j, Tag::Unparsed);
                }
                j = last;
                continue;
            }
            // "UNIT 12 BLU SPA": a business name after a whole unit.
            if found.is_empty() && j == hi {
                if let Some(w) = self.words_after_unit(floor, hi) {
                    self.set(w..hi, Tag::Unparsed);
                    j = w;
                    continue;
                }
            }
            // A designator cut off at the line limit: "... DR UNI".
            if found.is_empty()
                && j == hi
                && is_cut_designator(t, &lex)
                && self.suffix_before(name_lo, last)
            {
                self.set(last..j, Tag::Unparsed);
                self.incomplete = Some(last);
                j = last;
                continue;
            }
            // A designator spelling the lexicon knows only as observed, cut off
            // at the line limit: "... AVE NW SUIT" (#128).
            if found.is_empty()
                && j == hi
                && t.len() >= 3
                && lex.suffix(t).is_none()
                && lex
                    .unit(t)
                    .is_some_and(|l| l.kind == MatchKind::Observed && l.value.range_required())
                && self.suffix_before(name_lo, last)
            {
                self.warn(Warning::MissingUnitNumber);
                self.incomplete = Some(last);
                found.push((last..j, j..j));
                j = last;
                continue;
            }
            // "#" with nothing after it.
            if self.toks[last].is_hash() {
                self.set(last..j, Tag::Skip);
                self.warn(Warning::MissingUnitNumber);
                self.incomplete = Some(last);
                found.push((last..last, last..last));
                j = last;
                continue;
            }
            // "STE 1500" before " - ": a dash between the street and its
            // unit (`3RD AVENUE - SUITE 1500`).
            if !found.is_empty() && self.toks[last].is_dash() {
                self.set(last..j, Tag::Skip);
                j = last;
                continue;
            }
            // "# 309", "UNIT 203", "LOT H28", and a word after '#': "# REAR".
            if (is_unit_value(t)
                || self.spelled_after_designator(floor, last)
                || is_unit_pair(t)
                || (last > floor && self.toks[last - 1].is_hash() && is_unit_word(t))
                || self.letters_after_designator(floor, last))
                && last > floor
            {
                let start = if self.split_value(floor, last) || self.number_pair(floor, last) {
                    last - 1
                } else {
                    self.hash_run(floor, last)
                        .or_else(|| self.and_pair(floor, last))
                        .unwrap_or(last)
                };
                if self.toks[start - 1].is_hash() {
                    self.set(start - 1..start, Tag::Skip);
                    // "UNIT # 4": the designator before the '#' is this unit's,
                    // unless an ordinal after the street's suffix comes first:
                    // "RD 2ND FLOOR # 260" is floor 2ND and unit 260 (the next
                    // round takes the floor); "SW 11TH APT # 2" is not.
                    let hash = start - 1;
                    let designator = longest_ending(self.toks, floor, hash, |s| lex.unit(s))
                        .filter(|&(_, w)| {
                            let v = hash - w;
                            let floor_first = v > name_lo + 1
                                && is_ordinal(self.text(v - 1))
                                && self.suffix_before(name_lo, v - 1);
                            !floor_first && !self.bay_in_name(name_lo, v)
                        });
                    match designator {
                        Some((_, w)) => {
                            found.push((hash - w..hash, start..j));
                            j = hash - w;
                        }
                        None => {
                            found.push((hash..hash, start..j));
                            j = hash;
                        }
                    }
                    continue;
                }
                // "SUITE NO. 407", "APT NO 5": a filler word between the
                // designator and its value.
                if start > floor + 1 && lex.is_number_filler(self.text(start - 1)) {
                    if let Some((_, w)) =
                        longest_ending(self.toks, floor, start - 1, |s| lex.unit(s))
                    {
                        self.set(start - 1..start, Tag::Skip);
                        found.push((start - 1 - w..start - 1, start..j));
                        j = start - 1 - w;
                        continue;
                    }
                }
                if let Some((u, w)) = longest_ending(self.toks, floor, start, |s| lex.unit(s)) {
                    // A directional after a designator that does not always
                    // take a value is the street's postdirectional:
                    // `OCEAN FRONT W` is not unit `FRNT W`.
                    let street_word = lex.directional(t).is_some()
                        && !(u.kind != MatchKind::Observed && u.value.range_required());
                    if !street_word && !self.bay_in_name(name_lo, start - w) {
                        found.push((start - w..start, start..j));
                        j = start - w;
                        continue;
                    }
                }
            }
            // "BOX 3300", "NO 65", "NUM 230", "LOC 12" after a street's suffix:
            // a unit written with a word that is not a designator in Pub 28;
            // the word is dropped and the value is a unit with no type (#128).
            if found.is_empty()
                && j == hi
                && last > name_lo + 1
                && has_digit(t)
                && is_unit_value(t)
                && lex.is_unit_marker(self.text(last - 1))
                && self.toks[last - 1].seg == self.toks[last].seg
                && self.suffix_before(name_lo, last - 1)
            {
                self.set(last - 1..last, Tag::Skip);
                found.push((last..last, last..j));
                self.decide(Decision::BareUnit);
                j = last - 1;
                continue;
            }
            // A later line or comma segment that is only a number: "403" as
            // line 2 of `2309 1ST AVE NO`. A unit with no known designator.
            // A name of two words or more must come first: `1921 NW` / `46`
            // is a street cut across lines, not NW with unit 46.
            let alone = last > name_lo + 1
                && self.toks[last].seg != self.toks[last - 1].seg
                && (last + 1 == self.toks.len() || self.toks[last + 1].seg != self.toks[last].seg);
            if found.is_empty() && j == hi && alone && all_digits(t) {
                found.push((last..last, last..j));
                self.decide(Decision::BareUnit);
                j = last;
                continue;
            }
            // An ordinal before the designator: "3RD FLOOR".
            if let Some((u, w)) = longest_ending(self.toks, floor + 1, j, |s| lex.unit(s)) {
                let v = j - w - 1;
                // "THIRD FLOOR": a spelled ordinal counts before a floor word.
                let spelled = u.value.abbr() == "FL" && spelled_ordinal(self.text(v)).is_some();
                if v > name_lo && (is_ordinal(self.text(v)) || spelled) {
                    found.push((j - w..j, v..v + 1));
                    j = v;
                    continue;
                }
            }
            // A designator with nothing after it: "... TRL UNIT". An observed
            // spelling is only trusted with a value (`GULF TO BAY` is a
            // street, `BAY 4` a unit).
            if let Some((u, w)) = longest_ending(self.toks, floor + 1, j, |s| {
                lex.unit(s).filter(|l| l.kind != MatchKind::Observed)
            }) {
                if j - w > name_lo + 1 {
                    // A penthouse right after a designator is its number
                    // (`APT PH 5213`, `SUITE PH`).
                    if let Some((ty, num)) = found.last_mut() {
                        if u.value.abbr() != "PH" && ty.start == j && self.is_penthouse(ty) {
                            let end = if num.start == num.end {
                                ty.end
                            } else {
                                num.end
                            };
                            *num = ty.start..end;
                            *ty = j - w..j;
                            j -= w;
                            continue;
                        }
                    }
                    // "PH FLOOR" is the penthouse floor: one unit, PH, and
                    // the floor word is dropped.
                    let ph = j - w - 1..j - w;
                    if found.is_empty()
                        && u.value.abbr() == "FL"
                        && j - w > name_lo + 2
                        && self.is_penthouse(&ph)
                    {
                        self.set(j - w..j, Tag::Skip);
                        found.push((ph.clone(), ph.end..ph.end));
                        j = ph.start;
                        continue;
                    }
                    // "STE STE C": the same designator written twice (#128).
                    if let Some((ty, _)) = found.last() {
                        let again = ty.start == j
                            && lex
                                .unit(&join(&self.toks[ty.clone()]))
                                .is_some_and(|l| l.value.abbr() == u.value.abbr());
                        if again {
                            self.set(j - w..j, Tag::Skip);
                            j -= w;
                            continue;
                        }
                    }
                    if u.value.range_required() {
                        self.warn(Warning::MissingUnitNumber);
                        self.incomplete = Some(last);
                    }
                    found.push((j - w..j, j..j));
                    j -= w;
                    continue;
                }
            }
            // A bare unit after the suffix: "DR 706", "DR B", "DR V 21". A
            // directional letter right after the suffix on its line is the
            // postdirectional: "DR E 203" is DR E, unit 203; a line "E 203"
            // is the unit.
            if bare && found.is_empty() {
                // "BLVD 250 3440": two numbers after the suffix, one unit (#128).
                if last > floor + 1
                    && all_digits(t)
                    && all_digits(self.text(last - 1))
                    && self.toks[last - 1].seg == self.toks[last].seg
                    && self.suffix_before(name_lo, last - 1)
                {
                    found.push((last - 1..last - 1, last - 1..j));
                    self.decide(Decision::BareUnit);
                    j = last - 1;
                    continue;
                }
                if last > floor
                    && all_digits(t)
                    && is_letter(self.text(last - 1))
                    && !(last >= 2
                        && lex.directional(self.text(last - 1)).is_some()
                        && self.toks[last - 1].seg == self.toks[last - 2].seg)
                    && self.suffix_before(name_lo, last - 1)
                {
                    found.push((last - 1..last - 1, last - 1..j));
                    self.decide(Decision::BareUnit);
                    j = last - 1;
                    continue;
                }
                // A directional letter here is the postdirectional ("PARK AVE S").
                let dir = lex.directional(t).is_some();
                if is_unit_value(t)
                    && !dir
                    && (self.suffix_before(name_lo, last) || self.bay_before_value(name_lo, last))
                {
                    found.push((last..last, last..j));
                    self.decide(Decision::BareUnit);
                    j = last;
                    continue;
                }
            }
            break;
        }
        // Found right to left; the leftmost is the first unit.
        let n = found.len();
        for (k, (ty, num)) in found.into_iter().enumerate() {
            let which = u8::from(n == 2 && k == 0);
            self.set(ty, Tag::UnitType(which));
            self.set(num, Tag::UnitNumber(which));
        }
        j
    }
}
