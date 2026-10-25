//! Token classification (pipeline step 3).
//!
//! Shape tests on single tokens (numbers, ZIPs, ordinals, unit values) and
//! longest-match lexicon lookups over runs of tokens. The tagger decides
//! what a token *is* from these and its position; nothing here looks at
//! context beyond the tokens it is given.

use crate::lexicon::{Lexicons, MAX_FORM_WORDS};
use crate::tokenize::Token;

pub(crate) const ORDINAL_SUFFIXES: [&str; 4] = ["ST", "ND", "RD", "TH"];

pub(crate) fn has_digit(t: &str) -> bool {
    t.bytes().any(|c| c.is_ascii_digit())
}

pub(crate) fn all_digits(t: &str) -> bool {
    !t.is_empty() && t.bytes().all(|c| c.is_ascii_digit())
}

/// A spelled-out number, `ONE` to `TWENTY`: its value.
pub(crate) fn spelled_number(t: &str) -> Option<u32> {
    const WORDS: [&str; 20] = [
        "ONE",
        "TWO",
        "THREE",
        "FOUR",
        "FIVE",
        "SIX",
        "SEVEN",
        "EIGHT",
        "NINE",
        "TEN",
        "ELEVEN",
        "TWELVE",
        "THIRTEEN",
        "FOURTEEN",
        "FIFTEEN",
        "SIXTEEN",
        "SEVENTEEN",
        "EIGHTEEN",
        "NINETEEN",
        "TWENTY",
    ];
    let k = WORDS.iter().position(|w| t.eq_ignore_ascii_case(w))?;
    u32::try_from(k + 1).ok()
}

/// A spelled-out ordinal, `FIRST` to `TWENTIETH`: its value.
pub(crate) fn spelled_ordinal(t: &str) -> Option<u32> {
    const WORDS: [&str; 20] = [
        "FIRST",
        "SECOND",
        "THIRD",
        "FOURTH",
        "FIFTH",
        "SIXTH",
        "SEVENTH",
        "EIGHTH",
        "NINTH",
        "TENTH",
        "ELEVENTH",
        "TWELFTH",
        "THIRTEENTH",
        "FOURTEENTH",
        "FIFTEENTH",
        "SIXTEENTH",
        "SEVENTEENTH",
        "EIGHTEENTH",
        "NINETEENTH",
        "TWENTIETH",
    ];
    let k = WORDS.iter().position(|w| t.eq_ignore_ascii_case(w))?;
    u32::try_from(k + 1).ok()
}

/// `42ND`, `1ST`, `6TH`: digits then an ordinal suffix.
pub(crate) fn is_ordinal(t: &str) -> bool {
    let d = t.bytes().take_while(u8::is_ascii_digit).count();
    d > 0 && ORDINAL_SUFFIXES.contains(&&t[d..])
}

/// A number run into an ordinal street that can't be split reliably:
/// `409742ND` is 4097 42ND or 40974 2ND. Ordinal street numbers rarely
/// run past three digits.
pub(crate) fn is_glued_ordinal(t: &str) -> bool {
    is_ordinal(t) && t.bytes().take_while(u8::is_ascii_digit).count() >= 4
}

/// `5` or `9` digits, or `5-4`. Returns (zip5, zip4).
pub(crate) fn zip_parts(t: &str) -> Option<(&str, Option<&str>)> {
    let b = t.as_bytes();
    if all_digits(t) {
        return match b.len() {
            5 => Some((t, None)),
            9 => Some((&t[..5], Some(&t[5..]))),
            _ => None,
        };
    }
    let (a, z4) = t.split_once('-')?;
    (a.len() == 5 && all_digits(a) && z4.len() == 4 && all_digits(z4)).then_some((a, Some(z4)))
}

/// Shapes a house number takes: `123`, `12A`, `12-A`, `1204-1206`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum NumberShape {
    Plain,
    /// Two numbers joined by a hyphen: maybe a range of addresses.
    Range,
}

pub(crate) fn house_number(t: &str) -> Option<NumberShape> {
    if is_grid_number(t) || is_lettered_number(t) || is_lettered_number_letter(t) {
        return Some(NumberShape::Plain);
    }
    let d = t.bytes().take_while(u8::is_ascii_digit).count();
    if d == 0 {
        return None;
    }
    let rest = &t[d..];
    if rest.is_empty() {
        return Some(NumberShape::Plain);
    }
    if rest.len() == 1 && rest.bytes().all(|c| c.is_ascii_alphabetic()) {
        return Some(NumberShape::Plain);
    }
    let after = rest.strip_prefix('-')?;
    if all_digits(after) {
        // `1204-1206` is a range; `112-10` and `289-01` are one hyphenated
        // address (Pub 28 Appendix D1, section 232).
        let range = after.len() == d && after > &t[..d];
        return Some(if range {
            NumberShape::Range
        } else {
            NumberShape::Plain
        });
    }
    // `12-34A`: the Queens form with one trailing letter (#100).
    let e = after.bytes().take_while(u8::is_ascii_digit).count();
    let tail = &after[e..];
    let one_letter = |s: &str| s.len() == 1 && s.bytes().all(|c| c.is_ascii_alphabetic());
    (one_letter(after) || e > 0 && one_letter(tail)).then_some(NumberShape::Plain)
}

/// A county grid number: `22W410`, `5S710` (DuPage County, IL),
/// `W338S9739`, `S1749` (Waukesha and Sauk counties, WI). Digits and one
/// or two compass letters, each letter followed by digits.
pub(crate) fn is_grid_number(t: &str) -> bool {
    let b = t.as_bytes();
    let dir = |c: u8| matches!(c, b'N' | b'S' | b'E' | b'W');
    let mut k = b.iter().take_while(|c| c.is_ascii_digit()).count();
    let mut letters = 0;
    while k < b.len() {
        if !dir(b[k]) {
            return false;
        }
        let d = b[k + 1..].iter().take_while(|c| c.is_ascii_digit()).count();
        if d == 0 {
            return false;
        }
        letters += 1;
        k += 1 + d;
    }
    (1..=2).contains(&letters) && b.len() >= 4
}

/// A compass letter, three digits or more and one trailing letter:
/// `E7608B` (Wisconsin grid numbers with a suffix letter).
pub(crate) fn is_lettered_number_letter(t: &str) -> bool {
    let b = t.as_bytes();
    b.len() >= 5
        && matches!(b[0], b'N' | b'S' | b'E' | b'W')
        && b[b.len() - 1].is_ascii_alphabetic()
        && b[1..b.len() - 1].iter().all(u8::is_ascii_digit)
}

/// A letter and two digits or more: `T703` (Ohio township numbering),
/// `A13`. Only read as a house number at the start of a street.
pub(crate) fn is_lettered_number(t: &str) -> bool {
    let b = t.as_bytes();
    b.len() >= 3 && b[0].is_ascii_alphabetic() && b[1..].iter().all(u8::is_ascii_digit)
}

/// `1/2`, `3/4`: the fraction in `123 1/2`.
pub(crate) fn is_fraction(t: &str) -> bool {
    t.split_once('/')
        .is_some_and(|(a, b)| all_digits(a) && all_digits(b) && a.len() <= 2 && b.len() <= 2)
}

/// Two numbers joined by a slash: `5210/5212` (several addresses).
pub(crate) fn is_slash_pair(t: &str) -> bool {
    t.split_once('/')
        .is_some_and(|(a, b)| house_number(a).is_some() && house_number(b).is_some())
        && !is_fraction(t)
}

/// Two unit values joined by a slash: `101/102` (one tenant in two units).
/// Read only after a unit designator or `#`; a small `1/2` is a fraction.
pub(crate) fn is_unit_pair(t: &str) -> bool {
    t.split_once('/')
        .is_some_and(|(a, b)| is_unit_value(a) && is_unit_value(b))
        && !is_fraction(t)
}

/// A unit or box value: has a digit (`309`, `4C`, `H28`, `A4-2`, `3-203`)
/// or is one letter (`B`). Letters, digits and inner hyphens only.
pub(crate) fn is_unit_value(t: &str) -> bool {
    let ok_chars = t.bytes().all(|c| c.is_ascii_alphanumeric() || c == b'-');
    let single_letter = t.len() == 1 && t.bytes().all(|c| c.is_ascii_alphabetic());
    // A range of letters (`A-D`, `APT A-H` for a building's units).
    let letter_range = t.len() == 3
        && t.as_bytes()[1] == b'-'
        && t.as_bytes()[0].is_ascii_alphabetic()
        && t.as_bytes()[2].is_ascii_alphabetic();
    ok_chars && !t.starts_with('-') && (has_digit(t) || single_letter || letter_range)
}

/// One to three short tokens that make a unit with no designator (`2 5`,
/// `4 G`, `B B5`, `9 2 208`). A token is digits, one or two letters, or
/// letters mixed with digits, up to six characters; at least one token holds
/// a digit or is a single letter, so words do not qualify.
pub(crate) fn is_bare_unit<'a>(tokens: impl Iterator<Item = &'a str> + Clone) -> bool {
    let short = |t: &str| {
        let letters = t.bytes().filter(u8::is_ascii_alphabetic).count();
        t.len() <= 6
            && t.bytes().all(|c| c.is_ascii_alphanumeric())
            && (all_digits(t) || has_digit(t) || letters <= 2)
    };
    (1..=3).contains(&tokens.clone().count())
        && tokens.clone().all(short)
        && tokens.into_iter().any(|t| has_digit(t) || is_letter(t))
}

/// A word that is a unit value after a `#`: letters only, as in `# REAR`,
/// `# PRIMARY`, `# GAR`. Without the `#` a word is not a unit value.
pub(crate) fn is_unit_word(t: &str) -> bool {
    (2..=12).contains(&t.len()) && t.bytes().all(|c| c.is_ascii_alphabetic())
}

/// A highway route: starts with a digit (`20`, `60E`, `1150EE`).
pub(crate) fn is_route_value(t: &str) -> bool {
    t.bytes().next().is_some_and(|c| c.is_ascii_digit())
        && t.bytes().all(|c| c.is_ascii_alphanumeric())
}

/// A highway route that starts with a letter: one letter, digits, and at
/// most one more letter (`A1A`, Florida's State Road A1A; `M28`). Read only
/// after a highway prefix, where it cannot be a unit.
pub(crate) fn is_lettered_route(t: &str) -> bool {
    let b = t.as_bytes();
    let digits = b.iter().skip(1).take_while(|c| c.is_ascii_digit()).count();
    let rest = b.len().saturating_sub(1 + digits);
    b.first().is_some_and(u8::is_ascii_alphabetic)
        && digits > 0
        && rest <= 1
        && b.last().is_some_and(u8::is_ascii_alphanumeric)
        && b[1 + digits..].iter().all(u8::is_ascii_alphabetic)
}

/// A single letter, as in `V 21` or `AVENUE G`.
pub(crate) fn is_letter(t: &str) -> bool {
    t.len() == 1 && t.bytes().all(|c| c.is_ascii_alphabetic())
}

/// Longest run of tokens starting at `start` (and before `end`, within one
/// segment) that `f` accepts, joined with spaces. Returns the value and the
/// number of tokens.
///
/// The runs share their start, so each is a prefix of the longest: the tokens
/// are joined once and `f` sees slices of that string, longest first.
pub(crate) fn longest_at<T>(
    toks: &[Token],
    start: usize,
    end: usize,
    f: impl Fn(&str) -> Option<T>,
) -> Option<(T, usize)> {
    let seg = toks.get(start)?.seg;
    let max = MAX_FORM_WORDS.min(end.saturating_sub(start));
    let run = toks.get(start..(start + max).min(toks.len()))?;
    let n = run
        .iter()
        .take_while(|t| t.seg == seg && !t.is_hash() && !t.is_dash())
        .count();
    let mut joined = String::with_capacity(run[..n].iter().map(|t| t.text.len() + 1).sum());
    let mut cut = [0usize; MAX_FORM_WORDS];
    for (k, t) in run[..n].iter().enumerate() {
        if k > 0 {
            joined.push(' ');
        }
        joined.push_str(&t.text);
        cut[k] = joined.len();
    }
    (1..=n)
        .rev()
        .find_map(|w| f(&joined[..cut[w - 1]]).map(|v| (v, w)))
}

/// Longest run of tokens ending just before `end` (and starting at or after
/// `min`, within one segment) that `f` accepts.
///
/// The runs share their end, so each is a suffix of the longest: joined once,
/// as in [`longest_at`].
pub(crate) fn longest_ending<T>(
    toks: &[Token],
    min: usize,
    end: usize,
    f: impl Fn(&str) -> Option<T>,
) -> Option<(T, usize)> {
    let seg = toks.get(end.checked_sub(1)?)?.seg;
    let max = MAX_FORM_WORDS.min(end.saturating_sub(min));
    let run = toks.get(end - max..end)?;
    let n = run
        .iter()
        .rev()
        .take_while(|t| t.seg == seg && !t.is_hash() && !t.is_dash())
        .count();
    let run = &run[max - n..];
    let mut joined = String::with_capacity(run.iter().map(|t| t.text.len() + 1).sum());
    let mut at = [0usize; MAX_FORM_WORDS];
    for (k, t) in run.iter().enumerate() {
        if k > 0 {
            joined.push(' ');
        }
        at[k] = joined.len();
        joined.push_str(&t.text);
    }
    (1..=n).rev().find_map(|w| {
        let from = if w == n { 0 } else { at[n - w] };
        f(&joined[from..]).map(|v| (v, w))
    })
}

pub(crate) fn join(run: &[Token]) -> String {
    let mut s = String::new();
    for t in run {
        if !s.is_empty() {
            s.push(' ');
        }
        s.push_str(&t.text);
    }
    s
}

/// Whether `t` is a cut-off unit designator: a strict prefix, two letters
/// or more, of a designator's abbreviation or name (`UNI`, `APAR`). A street
/// suffix is not: `ST` and `TRL` start STE and TRAILER, but `DRY CREEK TRL`
/// ends in its suffix.
pub(crate) fn is_cut_designator(t: &str, lex: &Lexicons) -> bool {
    t.len() >= 2
        && t.bytes().all(|c| c.is_ascii_alphabetic())
        && lex.unit(t).is_none()
        && lex.suffix(t).is_none()
        && lex.units().any(|u| {
            [u.abbr(), u.name()]
                .iter()
                .any(|w| w.len() > t.len() && w.starts_with(t))
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shapes() {
        assert_eq!(zip_parts("33101"), Some(("33101", None)));
        assert_eq!(zip_parts("33101-1234"), Some(("33101", Some("1234"))));
        assert_eq!(zip_parts("331011234"), Some(("33101", Some("1234"))));
        assert_eq!(zip_parts("3310"), None);
        assert_eq!(house_number("12A"), Some(NumberShape::Plain));
        assert_eq!(house_number("12-A"), Some(NumberShape::Plain));
        // The Queens form with a trailing letter (#100): one letter only.
        assert_eq!(house_number("12-34A"), Some(NumberShape::Plain));
        assert_eq!(house_number("1204-1206A"), Some(NumberShape::Plain));
        assert_eq!(house_number("12-34AB"), None);
        assert_eq!(house_number("12A-34"), None);
        assert_eq!(house_number("12-34-5A"), None);
        assert_eq!(house_number("1204-1206"), Some(NumberShape::Range));
        let lex = Lexicons::builtin();
        assert!(is_cut_designator("UNI", &lex));
        assert!(!is_cut_designator("TRL", &lex) && !is_cut_designator("ST", &lex));
        assert_eq!(spelled_number("One"), Some(1));
        assert_eq!(spelled_number("TWENTY"), Some(20));
        assert_eq!(spelled_number("TWENTYONE"), None);
        assert_eq!(spelled_ordinal("third"), Some(3));
        assert_eq!(spelled_ordinal("TWENTIETH"), Some(20));
        assert_eq!(spelled_ordinal("THREE"), None);
        assert_eq!(house_number("112-10"), Some(NumberShape::Plain));
        assert_eq!(house_number("289-01"), Some(NumberShape::Plain));
        for g in ["22W410", "5S710", "W338S9739", "S1749", "0N428"] {
            assert_eq!(house_number(g), Some(NumberShape::Plain), "{g}");
        }
        assert!(!is_grid_number("N1") && !is_grid_number("I10") && !is_grid_number("12A"));
        assert_eq!(house_number("T703"), Some(NumberShape::Plain));
        assert!(!is_lettered_number("A1") && !is_lettered_number("AB12"));
        assert_eq!(house_number("42ND"), None);
        assert!(is_ordinal("42ND") && !is_glued_ordinal("42ND"));
        assert!(is_glued_ordinal("409742ND"));
        assert!(is_slash_pair("5210/5212") && !is_slash_pair("1/2"));
        assert!(is_fraction("1/2"));
        for v in ["309", "4C", "H28", "A4-2", "3-203", "B"] {
            assert!(is_unit_value(v), "{v}");
        }
        assert!(!is_unit_value("OFF"));
        assert!(is_route_value("60E") && !is_route_value("MM"));
        for ok in ["A1A", "M28", "K68"] {
            assert!(is_lettered_route(ok), "{ok}");
        }
        for bad in ["A", "AB1", "A1AB", "1A", "A-1", "PH5"] {
            assert!(!is_lettered_route(bad), "{bad}");
        }
    }

    #[test]
    fn cut_designator() {
        let lex = Lexicons::builtin();
        assert!(is_cut_designator("UNI", &lex));
        assert!(!is_cut_designator("UNIT", &lex));
        assert!(!is_cut_designator("CUTOF", &lex));
    }
}
