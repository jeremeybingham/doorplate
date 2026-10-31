//! Tokenizer (pipeline step 2).
//!
//! Splits cleaned text into tokens that keep their byte span in the
//! original input. Commas and semicolons separate *segments* (address lines
//! or parts of one), which the tagger uses as strong boundaries.
//!
//! Punctuation rules, from Pub 28 and the shapes seen in county address data:
//! - `#` is always its own token: `#309` -> `#` `309`.
//! - Parentheses are dropped from the text but kept in the span, and the
//!   token is marked `paren`: `(110)` -> `110`.
//! - A hyphen alone is a separator token (`N/A - MAGNOLIA AVE`). Leading and
//!   trailing hyphens are dropped (`-UNIT`, `FL-`); inner ones are kept
//!   (`C-22`, `1204-1206`).
//! - Periods are dropped except between digits (`ST.` -> `ST`, `39.2`). A
//!   period after an abbreviation of two letters or more, with letters right
//!   after it, separates words: `ST.CLOUD` -> `ST` `CLOUD` (initials such as
//!   `P.O.` and `U.S.A.` stay joined).
//! - Trailing colons and quotes are dropped.
//!
//! Glued tokens are split when the pieces are unambiguous:
//! - house number run into a name: `101BRADDOCK` -> `101` `BRADDOCK`, but
//!   not an ordinal (`42ND`) or a one-letter suffix (`12A`);
//! - a number run into the suffix `ST` or `RD` when that is not the number's
//!   ordinal ending: `178ST` -> `178` `ST` (178's ordinal is `178TH`), but
//!   `21ST` and `3RD` stay whole;
//! - a name run into a ZIP: `TAMPA33616` -> `TAMPA` `33616`;
//! - a highway prefix run into its route: `I10`, `IH280` (Pub 28 Appendix F);
//! - a unit designator run into its number: `APT107`, `APT3D`, or joined by
//!   punctuation: `APT.1285`, `STE.200`, `APT:201`, `UNIT-4`;
//! - a street suffix run into a unit designator, before a number:
//!   `CTAPT 107` -> `CT` `APT` `107`;
//! - a street suffix run into a city a state data knows, when the city ends
//!   the segment or comes before a state or ZIP:
//!   `WILSON STREETDADE CITY FL` -> `STREET` `DADE` `CITY`.

use crate::classify::{house_number, is_ordinal, is_unit_value, zip_parts, ORDINAL_SUFFIXES};
use crate::clean::Cleaned;
use crate::lexicon::{Lexicons, MatchKind, Special, MAX_PLACE_WORDS};
use crate::types::{FieldName, Span};

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Token {
    /// Normalized text: uppercase, punctuation handled as above.
    pub text: String,
    /// Span in the original input, including any stripped punctuation.
    pub span: Span,
    /// Comma-separated segment index, counted across the whole input.
    pub seg: usize,
    /// Written inside parentheses.
    pub paren: bool,
}

impl Token {
    pub fn is_dash(&self) -> bool {
        self.text == "-"
    }

    pub fn is_hash(&self) -> bool {
        self.text == "#"
    }
}

/// Tokenize one input string (a single line, or one field). `seg0` is the
/// first segment index to use, so fields can share one numbering.
pub(crate) fn tokenize(
    cleaned: &Cleaned,
    field: Option<FieldName>,
    seg0: usize,
    lex: &Lexicons,
) -> Vec<Token> {
    let text = cleaned.text.as_str();
    let bytes = text.as_bytes();
    // Raw pieces: (start, end, segment) in cleaned byte offsets.
    let mut pieces = Vec::new();
    let mut seg = seg0;
    let mut start = None;
    for (i, &b) in bytes.iter().enumerate() {
        let sep = b == b' ' || b == b',' || b == b';';
        if sep {
            if let Some(s) = start.take() {
                pieces.push((s, i, seg));
            }
            if b != b' ' {
                seg += 1;
            }
        } else if start.is_none() {
            start = Some(i);
        }
    }
    if let Some(s) = start {
        pieces.push((s, bytes.len(), seg));
    }

    let mut out = Vec::new();
    let mut in_paren = false;
    for (k, &(a, b, seg)) in pieces.iter().enumerate() {
        let next_starts_numeric = pieces.get(k + 1).is_some_and(|&(na, _, nseg)| {
            nseg == seg
                && text[na..]
                    .chars()
                    .next()
                    .is_some_and(|c| c.is_ascii_digit() || c == '#')
        });
        // The words after this piece in its segment, for a city glued to
        // the street.
        let after: Vec<&str> = pieces[k + 1..]
            .iter()
            .take_while(|&&(_, _, s)| s == seg)
            .map(|&(na, nb, _)| text[na..nb].trim_matches(|c: char| !c.is_alphanumeric()))
            .collect();
        let later = || {
            pieces[k + 1..]
                .iter()
                .filter(|&&(_, _, s)| s > seg)
                .map(|&(na, nb, _)| text[na..nb].trim_matches(|c: char| !c.is_alphanumeric()))
        };
        // The next segment starts with a state or a ZIP: the glued city's end.
        let later_seg = later()
            .next()
            .is_some_and(|w| lex.state(w).is_some() || zip_parts(w).is_some());
        let later_anchor = later().any(|w| lex.state(w).is_some() || zip_parts(w).is_some());
        let mut p = Piece {
            cleaned,
            field,
            seg,
            after: &after,
            later_seg,
            later_anchor,
            out: &mut out,
        };
        let raw = &text[a..b];
        let opens = raw.starts_with('(');
        let closes = raw.ends_with(')');
        let paren = in_paren || opens;
        if opens {
            in_paren = true;
        }
        if closes {
            in_paren = false;
        }
        p.piece(a, b, paren, next_starts_numeric, lex);
    }
    join_split_grid_number(&mut out, lex);
    join_lost_fraction(&mut out, lex);
    join_directional_comma(&mut out, lex);
    drop_unit_separators(&mut out, lex);
    join_unit_hyphen(&mut out, lex);
    out
}

/// The hyphen's index in `STREET-SUITE`: a street suffix, one hyphen, a unit designator, both
/// Pub 28 spellings (#308).
fn suffix_hyphen_designator(t: &str, lex: &Lexicons) -> Option<usize> {
    let (left, right) = t.split_once('-')?;
    let word = |w: &str| w.len() >= 2 && w.bytes().all(|c| c.is_ascii_alphabetic());
    let suffix = lex
        .suffix(left)
        .is_some_and(|l| l.kind != MatchKind::Observed);
    let designator = lex
        .unit(right)
        .is_some_and(|l| l.kind != MatchKind::Observed);
    (word(left) && word(right) && suffix && designator).then_some(left.len())
}

/// The slash's index in `ST/`, `ROAD/APT`, `ST/36`: a street suffix, then a slash (#308).
fn suffix_slash(t: &str, after: &[&str], lex: &Lexicons) -> Option<usize> {
    let (left, right) = t.split_once('/')?;
    // What follows the slash: the rest of this token, else the next word.
    let next = if right.is_empty() {
        after.first().copied()?
    } else {
        right
    };
    if !unit_like(next.trim_matches(|c: char| !c.is_alphanumeric()), lex) {
        return None;
    }
    let word = left.len() >= 2 && left.bytes().all(|c| c.is_ascii_alphabetic());
    let suffix = lex
        .suffix(left)
        .is_some_and(|l| l.kind != MatchKind::Observed);
    (word && suffix && !right.contains('/')).then_some(left.len())
}

/// A word that can start a unit after a separator: a unit designator, a box word, or a value
/// with a digit that is not an ordinal (`36`, `3A`, `2624`; not `1ST`) (#308).
fn unit_like(w: &str, lex: &Lexicons) -> bool {
    lex.unit(w).is_some_and(|l| l.kind != MatchKind::Observed)
        || lex.is_bare_box_word(w)
        || lex
            .special(w)
            .is_some_and(|l| matches!(l.value, Special::Box | Special::PoBox))
        || (w.bytes().any(|c| c.is_ascii_digit()) && !is_ordinal(w))
}

/// A dash or slash between a street suffix and a unit is a separator (`ST - 2210`, `ST / APT 4C`,
/// `ROAD / PO BOX 5`): the token is dropped, and what follows reads as a unit or a box. Only
/// when what follows is a unit designator, a box word, or a value with a digit that is not an
/// ordinal (`ST/1ST AVE` is two streets, `- 6TH FLOOR` already works) (#308).
fn drop_unit_separators(out: &mut Vec<Token>, lex: &Lexicons) {
    let mut k = 1;
    while k + 1 < out.len() {
        let (prev, sep, next) = (&out[k - 1], &out[k], &out[k + 1]);
        // Almost no token is a separator: test it before any lookup (#390).
        if sep.text != "-" && sep.text != "/" {
            k += 1;
            continue;
        }
        let after_suffix = prev.seg == sep.seg
            && lex
                .suffix(&prev.text)
                .is_some_and(|l| l.kind != MatchKind::Observed);
        let unit_next = unit_like(&next.text, lex);
        if after_suffix && next.seg == sep.seg && unit_next {
            out.remove(k);
        } else {
            k += 1;
        }
    }
}

/// A spaced hyphen inside a unit (#309). After a unit designator or `#`, `APT - 1` is `APT 1`
/// (the hyphen is dropped), and `SUITE 12 - 340` is the one value `12-340`, as `SUITE 12-340`
/// already was. The values have a digit and are not ordinals (`STE 4 - 6TH FLOOR` is a unit
/// and a floor), all in one segment, and the last one ends it (`UNIT 2 - 7101 HORNE` is a unit
/// and a house number).
fn join_unit_hyphen(out: &mut Vec<Token>, lex: &Lexicons) {
    let designator = |t: &Token| {
        t.is_hash()
            || lex
                .unit(&t.text)
                .is_some_and(|l| l.kind != MatchKind::Observed)
    };
    let value = |t: &Token| {
        t.text.bytes().any(|c| c.is_ascii_digit()) && is_unit_value(&t.text) && !is_ordinal(&t.text)
    };
    let mut k = 1;
    while k + 1 < out.len() {
        let same = out[k - 1].seg == out[k].seg && out[k].seg == out[k + 1].seg;
        // The value ends its segment: `UNIT 2 - 7101 HORNE` is a unit number and a house
        // number (a Canadian form), not one unit value.
        let ends = out.get(k + 2).map_or(true, |t| t.seg != out[k].seg);
        if same && ends && out[k].is_dash() {
            // `SUITE 12 - 340`: designator, value, hyphen, value.
            if k >= 2
                && out[k - 2].seg == out[k].seg
                && designator(&out[k - 2])
                && value(&out[k - 1])
                && value(&out[k + 1])
            {
                let next = out.remove(k + 1);
                out.remove(k);
                out[k - 1].text.push('-');
                out[k - 1].text.push_str(&next.text);
                out[k - 1].span.end = next.span.end;
                continue;
            }
            // `APT - 1`: designator, hyphen, value.
            if designator(&out[k - 1]) && value(&out[k + 1]) {
                out.remove(k);
                continue;
            }
        }
        k += 1;
    }
}

/// The hyphen of `1174-1/2`: digits, a hyphen, then a fraction.
fn fraction_hyphen(t: &str) -> Option<usize> {
    let (num, frac) = t.split_once('-')?;
    let (a, b) = frac.split_once('/')?;
    let digits = |s: &str| !s.is_empty() && s.bytes().all(|c| c.is_ascii_digit());
    (digits(num) && digits(a) && digits(b)).then_some(num.len())
}

/// `N 10129 MAPLE RD`: a lone compass letter and a number of three digits or
/// more that open the line, with a street word after them, are one grid-style
/// house number (`N10129`) split by a space. A directional after the digits
/// (`E 1000 N`, a Utah street) or no word at all keeps them apart.
fn join_split_grid_number(out: &mut Vec<Token>, lex: &Lexicons) {
    if out.len() < 3
        || !matches!(out[0].text.as_str(), "N" | "S" | "E" | "W")
        || out[1].text.len() < 3
        || !out[1].text.bytes().all(|c| c.is_ascii_digit())
        || out[0].seg != out[1].seg
        || out[0].seg != out[2].seg
        || out[0].span.field != out[1].span.field
        || lex.directional(&out[2].text).is_some()
        || !out[2].text.bytes().any(|c| c.is_ascii_alphabetic())
    {
        return;
    }
    let digits = out.remove(1);
    out[0].text.push_str(&digits.text);
    out[0].span.end = digits.span.end;
}

/// `31 1 2 ELM PLACE`, `838 21 1 2 RD`: a half or quarter written without its slash (`1 2`,
/// `1 4`, `3 4`), right after the house number or after a whole-number street name, with a
/// plain word next. The two digits are one fraction, `1/2` (#247). The line must open with the
/// house number, and a unit designator or box word next (`5 1 2 STE 100`) keeps the digits
/// apart.
fn join_lost_fraction(out: &mut Vec<Token>, lex: &Lexicons) {
    if house_number(out.first().map_or("", |t| t.text.as_str())).is_none() {
        return;
    }
    let half_at = |k: usize| {
        matches!(
            (
                out.get(k).map(|t| t.text.as_str()),
                out.get(k + 1).map(|t| t.text.as_str())
            ),
            (Some("1"), Some("2")) | (Some("1"), Some("4")) | (Some("3"), Some("4"))
        )
    };
    // The whole number of a street name (`21` in `838 21 1 2 RD`) may come first.
    let whole = out.get(1).is_some_and(|t| {
        (1..=3).contains(&t.text.len()) && t.text.bytes().all(|c| c.is_ascii_digit())
    });
    let k = if half_at(1) {
        1
    } else if whole && half_at(2) {
        2
    } else {
        return;
    };
    let Some(word) = out.get(k + 2) else {
        return;
    };
    // A bare suffix and nothing after it (`12 1 2 ST`) has no street name to count; after a
    // whole number it is the suffix of `21 1/2 RD`.
    let bare_suffix = k == 1
        && out.get(k + 3).map_or(true, |t| t.seg != word.seg)
        && lex
            .suffix(&word.text)
            .is_some_and(|l| l.kind != MatchKind::Observed);
    let plain = word.text.len() >= 2
        && !bare_suffix
        && word.text.bytes().all(|c| c.is_ascii_alphabetic())
        && lex
            .unit(&word.text)
            .map_or(true, |l| l.kind == MatchKind::Observed)
        && !lex.is_bare_box_word(&word.text);
    let same = out[..=k + 2]
        .iter()
        .all(|t| t.seg == out[0].seg && t.span.field == out[0].span.field);
    if plain && same {
        let denom = out.remove(k + 1);
        out[k].text.push('/');
        out[k].text.push_str(&denom.text);
        out[k].span.end = denom.span.end;
    }
}

/// `3324 N, ANDREWS AVE`: a comma right after a lone directional that follows
/// the house number, with a street ending in a suffix after it, is stray
/// punctuation. The directional and the street share a segment, so the
/// directional is read as the predirectional. `123 N, MIAMI BEACH` (no suffix
/// word ends the next segment) is untouched.
fn join_directional_comma(out: &mut [Token], lex: &Lexicons) {
    if out.len() < 4
        || house_number(&out[0].text).is_none()
        || lex.directional(&out[1].text).is_none()
        || out[1].seg != out[0].seg
        || out[2].seg != out[1].seg + 1
    {
        return;
    }
    let next = out[2].seg;
    let street = out.iter().filter(|t| t.seg == next).count();
    let last = out.iter().rev().find(|t| t.seg == next);
    if street < 2 || !last.is_some_and(|t| lex.suffix(&t.text).is_some()) {
        return;
    }
    let joined = out[1].seg;
    for t in out.iter_mut().skip(2) {
        t.seg = if t.seg == next { joined } else { t.seg - 1 };
    }
}

struct Piece<'a> {
    cleaned: &'a Cleaned,
    field: Option<FieldName>,
    seg: usize,
    /// The words after this piece in its segment.
    after: &'a [&'a str],
    /// Whether another segment follows this one.
    later_seg: bool,
    /// Whether a later segment holds a state or a ZIP.
    later_anchor: bool,
    out: &'a mut Vec<Token>,
}

impl Piece<'_> {
    /// The words before this piece in its segment, nearest last.
    fn before(&self) -> Vec<&str> {
        let mut words: Vec<&str> = self
            .out
            .iter()
            .rev()
            .take_while(|t| t.seg == self.seg)
            .take(MAX_PLACE_WORDS)
            .map(|t| t.text.as_str())
            .collect();
        words.reverse();
        words
    }

    fn span(&self, a: usize, b: usize) -> Option<Span> {
        let (start, end) = self.cleaned.original_range(a, b)?;
        Some(Span {
            field: self.field,
            start,
            end,
        })
    }

    fn emit(&mut self, text: String, a: usize, b: usize, paren: bool) {
        if text.is_empty() {
            return;
        }
        if let Some(span) = self.span(a, b) {
            self.out.push(Token {
                text,
                span,
                seg: self.seg,
                paren,
            });
        }
    }

    /// One whitespace/comma-delimited piece, `cleaned.text[a..b]`.
    fn piece(&mut self, a: usize, b: usize, paren: bool, next_numeric: bool, lex: &Lexicons) {
        let text = &self.cleaned.text;
        let raw = &text[a..b];
        if raw.bytes().all(|c| c == b'-') {
            self.emit("-".to_string(), a, b, paren);
            return;
        }
        // A line of only asterisks stays, so it reads as a placeholder.
        if raw.bytes().all(|c| c == b'*') {
            self.emit("*".to_string(), a, b, paren);
            return;
        }
        // Trim wrapping punctuation from the text, but keep the whole piece
        // in the span when it is a single token.
        // Asterisks too: Pub 28 section 354 drops them (`**Private Address**`),
        // and a stray backtick (`1719\``).
        let trim: &[char] = &['(', ')', '-', ':', '"', '\'', '.', '[', ']', '*', '`'];
        let lead = raw.len() - raw.trim_start_matches(trim).len();
        let inner = raw.trim_matches(trim);
        if inner.is_empty() {
            return;
        }
        let ia = a + lead;
        let ib = ia + inner.len();
        // `%JOHN SMITH`: a leading percent sign (in care of) is a word of its
        // own. `100%` and `50%OFF` mid-word are untouched.
        if inner.len() > 1
            && inner.starts_with('%')
            && inner[1..].chars().next().is_some_and(char::is_alphabetic)
        {
            self.emit("%".to_string(), ia, ia + 1, paren);
            self.sub(ia + 1, ib, a, b, paren, next_numeric, lex);
            return;
        }
        // Split around '#'.
        if inner.contains('#') {
            let mut s = ia;
            for (i, c) in text[ia..ib].char_indices() {
                if c == '#' {
                    self.sub(s, ia + i, a, b, paren, next_numeric, lex);
                    self.emit("#".to_string(), ia + i, ia + i + 1, paren);
                    s = ia + i + 1;
                }
            }
            self.sub(s, ib, a, b, paren, next_numeric, lex);
        } else {
            self.sub(ia, ib, a, b, paren, next_numeric, lex);
        }
    }

    /// A sub-piece `[s, e)` of the piece `[pa, pb)`. When it is the whole
    /// trimmed piece, the span covers the untrimmed piece.
    #[allow(clippy::too_many_arguments)]
    fn sub(
        &mut self,
        s: usize,
        e: usize,
        pa: usize,
        pb: usize,
        paren: bool,
        next_numeric: bool,
        lex: &Lexicons,
    ) {
        if s >= e {
            return;
        }
        let t = &self.cleaned.text[s..e];
        let t = t.trim_matches(|c| c == '-' || c == '.');
        if t.is_empty() {
            return;
        }
        let s2 = s + self.cleaned.text[s..e].find(t).unwrap_or(0);
        let e2 = s2 + t.len();
        let whole = self.cleaned.text[pa..pb].trim_matches(|c: char| !c.is_alphanumeric()) == t
            && !self.cleaned.text[pa..pb].contains('#');
        let (sa, sb) = if whole { (pa, pb) } else { (s2, e2) };

        // A hyphenated route: `GA-25`, `US-385`, `CR-48`, `I-65` (Appendix F
        // writes these with a space). Only after a highway prefix or a state
        // code that is not also a directional (`NE-2` stays whole); SR is
        // left to state data.
        // `1174-1/2`: a hyphen before a fraction is a space (`1174 1/2`).
        if let Some(cut) = fraction_hyphen(t) {
            self.emit(t[..cut].to_string(), s2, s2 + cut, paren);
            self.emit(t[cut + 1..].to_string(), s2 + cut + 1, e2, paren);
            return;
        }
        if let Some(cut) = route_hyphen(t, lex) {
            self.emit(t[..cut].to_string(), s2, s2 + cut, paren);
            self.emit(t[cut + 1..].to_string(), s2 + cut + 1, e2, paren);
            return;
        }
        // `STREET-SUITE 303`, `CT-UNIT 4`: a street suffix, a hyphen glued to a unit
        // designator (#308). The pieces are words of their own.
        if let Some(cut) = suffix_hyphen_designator(t, lex) {
            self.emit(t[..cut].to_string(), s2, s2 + cut, paren);
            self.sub(s2 + cut + 1, e2, pa, pb, paren, next_numeric, lex);
            return;
        }
        // `ST/ 36`, `ROAD/APT 7L`: a street suffix glued to a slash. The slash is a token of
        // its own, dropped later when a unit follows (`drop_unit_separators`).
        if let Some(cut) = suffix_slash(t, self.after, lex) {
            self.emit(t[..cut].to_string(), s2, s2 + cut, paren);
            self.emit("/".to_string(), s2 + cut, s2 + cut + 1, paren);
            self.sub(s2 + cut + 1, e2, pa, pb, paren, next_numeric, lex);
            return;
        }
        // A unit designator joined to its value by punctuation: `APT.1285`,
        // `STE.200`, `APT:201`, `UNIT-4`.
        if let Some(cut) = unit_punct(t, lex) {
            self.emit(t[..cut].to_string(), s2, s2 + cut, paren);
            self.sub(s2 + cut + 1, e2, pa, pb, paren, next_numeric, lex);
            return;
        }
        // `ST.CLOUD`, `FT.MYERS`: a period after two letters or more, with a
        // letter after it, ends a word.
        if let Some(cut) =
            word_period(t).filter(|&c| !known_word(&format!("{}{}", &t[..c], &t[c + 1..]), lex))
        {
            self.sub(s2, s2 + cut, pa, pb, paren, next_numeric, lex);
            self.sub(s2 + cut + 1, e2, pa, pb, paren, next_numeric, lex);
            return;
        }
        // A value right after '#' or a unit designator is that unit's: `# 2WD`
        // is not house number 2 and a name, `APT I4` is not highway I4.
        let unit_value = self
            .out
            .last()
            .is_some_and(|p| p.seg == self.seg && (p.is_hash() || lex.unit(&p.text).is_some()));
        // A route right after a highway prefix may end in letters
        // (Appendix F: `ROUTE 1150EE`).
        let after_prefix = self
            .out
            .last()
            .is_some_and(|p| p.seg == self.seg && lex.highway(&p.text).is_some());
        if t.bytes().all(|c| c.is_ascii_alphanumeric()) {
            let cut = glue_split(t, next_numeric, unit_value, after_prefix, lex).or_else(|| {
                glue_place(
                    t,
                    self.before(),
                    self.after,
                    self.later_seg,
                    self.later_anchor,
                    lex,
                )
            });
            if let Some(cut) = cut {
                self.emit(t[..cut].to_string(), s2, s2 + cut, paren);
                self.emit(t[cut..].to_string(), s2 + cut, e2, paren);
                return;
            }
        }
        self.emit(normalize(t), sa, sb, paren);
    }
}

/// Drop periods except between digits; drop quotes.
fn normalize(t: &str) -> String {
    let b = t.as_bytes();
    let mut out = String::with_capacity(t.len());
    for (i, c) in t.char_indices() {
        match c {
            '.' => {
                let digit_before = i > 0 && b[i - 1].is_ascii_digit();
                let digit_after = b.get(i + 1).is_some_and(u8::is_ascii_digit);
                if digit_before && digit_after {
                    out.push('.');
                }
            }
            '"' | '\'' => {}
            _ => out.push(c),
        }
    }
    out
}

/// The hyphen's index in a hyphenated route such as `GA-25`, if `t` is one.
fn route_hyphen(t: &str, lex: &Lexicons) -> Option<usize> {
    let (letters, route) = t.split_once('-')?;
    let ok_letters = !letters.is_empty()
        && letters.len() <= 3
        && letters.bytes().all(|c| c.is_ascii_alphabetic());
    let ok_route = route.bytes().next().is_some_and(|c| c.is_ascii_digit())
        && route.bytes().all(|c| c.is_ascii_alphanumeric());
    if !(ok_letters && ok_route) {
        return None;
    }
    let state = lex
        .state(letters)
        .is_some_and(|l| l.kind != MatchKind::Variant)
        && lex.directional(letters).is_none();
    (lex.highway(letters).is_some() || state).then_some(letters.len())
}

/// The index of the first period in `t` that has two letters or more right
/// before it (back to the start or another period) and a letter right after.
/// The caller keeps the token whole when the pieces join into a known word
/// (`BLV.D` is `BLVD`).
fn word_period(t: &str) -> Option<usize> {
    let b = t.as_bytes();
    let mut start = 0;
    for (i, &c) in b.iter().enumerate() {
        if c != b'.' {
            continue;
        }
        let before = &b[start..i];
        if before.len() >= 2
            && before.iter().all(u8::is_ascii_alphabetic)
            && b.get(i + 1).is_some_and(u8::is_ascii_alphabetic)
        {
            return Some(i);
        }
        start = i + 1;
    }
    None
}

/// The index of the punctuation in `APT.1285`, `STE.200`, `APT:201`,
/// `UNIT-4`, `BOX.2351`: a unit designator or box word, one of `.` `:` `-`,
/// then the value; and `NO.9`, `NUM.12` (the number word, period only).
fn unit_punct(t: &str, lex: &Lexicons) -> Option<usize> {
    let cut = t.find(['.', ':', '-'])?;
    let (letters, rest) = (&t[..cut], &t[cut + 1..]);
    let ok = letters.len() >= 2
        && letters.bytes().all(|c| c.is_ascii_alphabetic())
        && rest
            .bytes()
            .next()
            .is_some_and(|c| c.is_ascii_alphanumeric())
        && (lex.unit(letters).is_some()
            || lex
                .special(letters)
                .is_some_and(|l| matches!(l.value, Special::Box | Special::PoBox))
            // `NO.9`, `NUM.12`: the number word, with a period only (#293).
            || (t.as_bytes()[cut] == b'.' && lex.is_number_filler(letters)));
    ok.then_some(cut)
}

/// Where to split a glued alphanumeric token, if anywhere.
fn glue_split(
    t: &str,
    next_numeric: bool,
    after_unit: bool,
    after_prefix: bool,
    lex: &Lexicons,
) -> Option<usize> {
    let digits_lead = t.bytes().take_while(u8::is_ascii_digit).count();
    let alpha_lead = t.bytes().take_while(u8::is_ascii_alphabetic).count();
    let n = t.len();
    // A value right after a unit designator is whole (`# 2WD`, `APT I4`).
    if after_unit && (digits_lead > 0 || alpha_lead < n) {
        return None;
    }
    if digits_lead > 0 && digits_lead < n {
        let rest = &t[digits_lead..];
        // 101BRADDOCK; not 12A, 42ND, 1ST.
        // A route after a highway prefix keeps up to two letters (`1150EE`).
        if rest.len() >= 2
            && !(after_prefix && rest.len() <= 2)
            && rest.bytes().all(|c| c.is_ascii_alphabetic())
            && !ORDINAL_SUFFIXES.contains(&rest)
            && !is_ordinal(t)
        {
            return Some(digits_lead);
        }
        // 178ST, 54RD: an ordinal ending the number does not take is the
        // street suffix. Four digits or more stay whole (`409722ST` may be
        // a house number run into the street; see `is_glued_ordinal`).
        if digits_lead <= 3
            && matches!(rest, "ST" | "RD")
            && ordinal_ending(&t[..digits_lead]) != Some(rest)
        {
            return Some(digits_lead);
        }
        return None;
    }
    if alpha_lead > 0 && alpha_lead < n {
        let (letters, rest) = t.split_at(alpha_lead);
        let rest_digits = rest.bytes().all(|c| c.is_ascii_digit());
        // TAMPA33616
        if rest_digits && letters.len() >= 2 && (rest.len() == 5 || rest.len() == 9) {
            return Some(alpha_lead);
        }
        // I10, IH280, CR1185 (a route may end in a letter: 60E).
        let route = rest.bytes().next().is_some_and(|c| c.is_ascii_digit());
        if route && lex.highway(letters).is_some() {
            return Some(alpha_lead);
        }
        // APT107, APT3D
        let unit_value = rest.bytes().next().is_some_and(|c| c.is_ascii_digit())
            && rest.bytes().all(|c| c.is_ascii_alphanumeric());
        if unit_value && letters.len() >= 2 && lex.unit(letters).is_some() {
            return Some(alpha_lead);
        }
        return None;
    }
    if alpha_lead == n && next_numeric && n >= 4 && !known_word(t, lex) {
        // CTAPT 107, DRUNIT 142: a suffix followed by a designator.
        for cut in 2..n - 1 {
            let (l, r) = t.split_at(cut);
            if r.len() >= 2 && lex.suffix(l).is_some() && lex.unit(r).is_some() {
                return Some(cut);
            }
        }
    }
    None
}

/// The ordinal ending English writes after the number `n`: `ST`, `ND`,
/// `RD` or `TH` (11 to 13 take `TH`).
fn ordinal_ending(n: &str) -> Option<&'static str> {
    let b = n.as_bytes();
    let last = *b.last()?;
    let tens = b.len() >= 2 && b[b.len() - 2] == b'1';
    Some(match (tens, last) {
        (false, b'1') => "ST",
        (false, b'2') => "ND",
        (false, b'3') => "RD",
        _ => "TH",
    })
}

/// `STREETDADE` before `CITY FL`: where a street suffix ends and a city the
/// state data know begins. The city is the rest of the word plus some of
/// the words after it, and must come before a state, a ZIP or another
/// segment (with none of these the tagger could not use the split). Never
/// splits a word that starts a place itself, or ends one with the words
/// before it (`PICO RIVERA` is not `RIV` `ERA`).
///
/// With the national place list almost any word ends in a place name, so the
/// anchor has to be real:
/// - a state or ZIP in the same segment ends the city only when nothing but
///   a ZIP follows it (`DE LA REINA` is not Delaware, `CT` in
///   `CREEKWOOD CT, MIAMI` is not Connecticut), and only when no later
///   segment holds the state or ZIP;
/// - the end of the segment ends it only when the next segment starts with a
///   state or a ZIP (`STRAND, MIAMI, FL` is not `ST` `RAND`), and the city's
///   last word is not a street suffix.
fn glue_place(
    t: &str,
    before: Vec<&str>,
    rest: &[&str],
    later_seg: bool,
    later_anchor: bool,
    lex: &Lexicons,
) -> Option<usize> {
    let n = t.len();
    if n < 5 || !t.bytes().all(|c| c.is_ascii_alphabetic()) || known_word(t, lex) {
        return None;
    }
    // This word ends a place that began earlier in the segment.
    for from in 0..before.len() {
        let mut name = before[from..].join(" ");
        name.push(' ');
        name.push_str(t);
        if lex.is_place(&name) {
            return None;
        }
    }
    let after = &rest[..rest.len().min(MAX_PLACE_WORDS)];
    // The city starting with `first`, ending before word `j` of `after`.
    let city_at = |first: &str| {
        (0..=after.len().min(MAX_PLACE_WORDS - 1)).any(|j| {
            let ends = match after.get(j) {
                // A segment-end anchor takes no street suffix as the city's
                // last word (`DALEWOOD WAY,` is not `DALE` `WOOD WAY`).
                None => {
                    later_seg
                        && j == rest.len()
                        && !after[..j].last().is_some_and(|w| lex.suffix(w).is_some())
                }
                Some(w) => {
                    (lex.state(w).is_some() || zip_parts(w).is_some())
                        && !later_anchor
                        && (j + 1 == rest.len()
                            || (j + 2 == rest.len() && zip_parts(rest[j + 1]).is_some()))
                        && suffix_state_confirmed(w, rest.get(j + 1).copied(), lex)
                }
            };
            let mut city = first.to_string();
            for w in &after[..j] {
                city.push(' ');
                city.push_str(w);
            }
            ends && lex.is_place(&city)
        })
    };
    if city_at(t) {
        return None;
    }
    (2..n - 2).find(|&cut| lex.suffix(&t[..cut]).is_some() && city_at(&t[cut..]))
}

/// A state code that is also a street suffix (`CT`, `KY`, `MT`, `WY`, `LA`) ends
/// a glued city only when a ZIP of that state follows it: a bare `CT` after a
/// word is the suffix (`PINEBRIAR CT` is not `PINE` `BRIAR` in Connecticut), as
/// the tagger decides for the same collision. Any other anchor stands.
fn suffix_state_confirmed(w: &str, zip: Option<&str>, lex: &Lexicons) -> bool {
    if lex.state(w).is_none() || lex.suffix(w).is_none() {
        return true;
    }
    let state = lex.state(w).map(|l| l.value.code());
    zip.and_then(zip_parts)
        .and_then(|(z5, _)| lex.zip_places(z5))
        .is_some_and(|z| Some(z.main().state()) == state)
}

fn known_word(t: &str, lex: &Lexicons) -> bool {
    lex.suffix(t).is_some()
        || lex.unit(t).is_some()
        || lex.directional(t).is_some()
        || lex.state(t).is_some()
        || lex.special(t).is_some()
        || lex.highway(t).is_some()
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use crate::clean::clean;

    fn toks(s: &str) -> Vec<String> {
        tokenize(&clean(s), None, 0, &Lexicons::builtin())
            .into_iter()
            .map(|t| t.text)
            .collect()
    }

    #[test]
    fn punctuation() {
        assert_eq!(
            toks("4158 Inverrary Dr #309"),
            ["4158", "INVERRARY", "DR", "#", "309"]
        );
        assert_eq!(toks("112 PAUL ST (110)"), ["112", "PAUL", "ST", "110"]);
        assert_eq!(
            toks("3151 COOPER ST -UNIT 15"),
            ["3151", "COOPER", "ST", "UNIT", "15"]
        );
        assert_eq!(toks("N/A - MAGNOLIA AVE"), ["N/A", "-", "MAGNOLIA", "AVE"]);
        assert_eq!(toks("CHATHAM DRIVE:"), ["CHATHAM", "DRIVE"]);
        assert_eq!(
            toks("St. Petersburg, FL- 33701"),
            ["ST", "PETERSBURG", "FL", "33701"]
        );
        assert_eq!(toks("P.O. Box 7"), ["PO", "BOX", "7"]);
        assert_eq!(toks("ST.CLOUD FT.MYERS"), ["ST", "CLOUD", "FT", "MYERS"]);
        assert_eq!(toks("U.S.A. N.W. P.O.BOX"), ["USA", "NW", "POBOX"]);
        assert_eq!(toks("HARBOR BLV.D CR.N"), ["HARBOR", "BLVD", "CR", "N"]);
        assert_eq!(toks("PO.BOX.2351"), ["PO", "BOX", "2351"]);
        assert_eq!(toks("39.2 RD"), ["39.2", "RD"]);
        assert_eq!(toks("C-22 1204-1206"), ["C-22", "1204-1206"]);
    }

    #[test]
    fn glued() {
        assert_eq!(toks("101BRADDOCK LN"), ["101", "BRADDOCK", "LN"]);
        assert_eq!(toks("42ND ST 12A"), ["42ND", "ST", "12A"]);
        assert_eq!(toks("TAMPA33616"), ["TAMPA", "33616"]);
        assert_eq!(toks("I10 IH280"), ["I", "10", "IH", "280"]);
        assert_eq!(
            toks("BIRD BAY CTAPT 107"),
            ["BIRD", "BAY", "CT", "APT", "107"]
        );
        assert_eq!(toks("ORLANDO DRUNIT 142"), ["ORLANDO", "DR", "UNIT", "142"]);
        assert_eq!(toks("APT107"), ["APT", "107"]);
        assert_eq!(toks("ACCESS UNDETERMINED"), ["ACCESS", "UNDETERMINED"]);
        assert_eq!(toks("409742ND SQ"), ["409742ND", "SQ"]);
        assert_eq!(toks("NE 178ST"), ["NE", "178", "ST"]);
        assert_eq!(toks("NW 54RD 112ST"), ["NW", "54", "RD", "112", "ST"]);
        assert_eq!(
            toks("21ST 3RD 11ST 101ST"),
            ["21ST", "3RD", "11", "ST", "101ST"]
        );
        assert_eq!(toks("409722ST"), ["409722ST"]);
    }

    #[test]
    fn percent_sign_in_care_of() {
        assert_eq!(toks("%JOHN SMITH"), ["%", "JOHN", "SMITH"]);
        assert_eq!(toks("% JOHN"), ["%", "JOHN"]);
        assert_eq!(toks("100% MAIN"), ["100%", "MAIN"]);
        assert_eq!(toks("%1"), ["%1"]);
    }

    #[test]
    fn designator_joined_to_its_value() {
        assert_eq!(toks("APT.1285"), ["APT", "1285"]);
        assert_eq!(toks("STE.200 APT:201"), ["STE", "200", "APT", "201"]);
        assert_eq!(toks("UNIT-4 APT.D"), ["UNIT", "4", "APT", "D"]);
        assert_eq!(toks("APT3D"), ["APT", "3D"]);
        // Not a designator: a route, a name with a period, a hyphenated value.
        assert_eq!(toks("GA-25"), ["GA", "25"]);
        assert_eq!(toks("ST.LUCIE"), ["ST", "LUCIE"]);
        assert_eq!(toks("C-22"), ["C-22"]);
    }

    #[test]
    fn glued_city() {
        assert_eq!(
            toks("13551 WILSON STREETDADE CITY FL 33525"),
            ["13551", "WILSON", "STREET", "DADE", "CITY", "FL", "33525"]
        );
        assert_eq!(
            toks("1 OAK AVETITUSVILLE, FL"),
            ["1", "OAK", "AVE", "TITUSVILLE", "FL"]
        );
        // Nothing after the city to anchor it, or no suffix before it.
        assert_eq!(
            toks("13551 WILSON STREETDADE CITY"),
            ["13551", "WILSON", "STREETDADE", "CITY"]
        );
        assert_eq!(toks("1 PARKLAND DR"), ["1", "PARKLAND", "DR"]);
    }

    #[test]
    fn a_suffix_that_is_a_state_ends_no_glued_city_without_its_zip() {
        // `CT` is the suffix COURT unless a Connecticut ZIP follows (#143).
        for street in ["PINEBRIAR", "TRELLIS", "STORCH", "COURTNEY", "FIELDSTONE"] {
            assert_eq!(
                toks(&format!("1305 {street} CT")),
                ["1305", street, "CT"],
                "{street}"
            );
        }
        for suffix in ["WY", "KY", "MT"] {
            assert_eq!(
                toks(&format!("1305 PINEBRIAR {suffix}")).len(),
                3,
                "{suffix}"
            );
        }
        // With a ZIP of that state the glued city still splits.
        assert_eq!(
            toks("123 MAIN STHARTFORD CT 06103"),
            ["123", "MAIN", "ST", "HARTFORD", "CT", "06103"]
        );
        // A ZIP of another state does not make it Connecticut.
        assert_eq!(toks("1305 PINEBRIAR CT 33601").len(), 4);
    }

    #[test]
    fn segments_and_spans() {
        let input = "26166 Paysandu Dr, PUNTA GORDA, FL- 33983";
        let t = tokenize(&clean(input), None, 0, &Lexicons::builtin());
        let segs: Vec<_> = t.iter().map(|t| t.seg).collect();
        assert_eq!(segs, [0, 0, 0, 1, 1, 2, 2]);
        let fl = &t[5];
        assert_eq!(&input[fl.span.start..fl.span.end], "FL-");
        let p = tokenize(&clean("(OFF)"), None, 0, &Lexicons::builtin());
        assert_eq!(p[0].text, "OFF");
        assert!(p[0].paren);
        assert_eq!((p[0].span.start, p[0].span.end), (0, 5));
    }
}
