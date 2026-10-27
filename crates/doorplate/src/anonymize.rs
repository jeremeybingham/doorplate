//! Shape-preserving obfuscation of address-like text (#105).
//!
//! [`Anonymizer`] works token by token and needs no successful parse, so it handles
//! lines that do not parse or are badly formed. It keeps what decides how the parser
//! reads a line (punctuation, spacing, case, street suffixes, directionals, unit
//! designators, state codes, the special words, and the city, state and ZIP prefix
//! the parser finds) and replaces the rest: digit runs become other digits of the
//! same length, and every other word becomes an invented word of the same length and
//! case. The same input value gets the same replacement for one seed, so duplicates
//! stay duplicates.
//!
//! **This is obfuscation that keeps the shape, not anonymization.** A word the
//! lexicons know (a street named `PARK`, `LAKE` or `SUMMIT`) is kept, a rare name that
//! happens to be a lexicon word is kept, and the city and the first three ZIP digits are
//! kept. Look at the output before you share it.
//!
//! ```
//! use doorplate::Anonymizer;
//!
//! let a = Anonymizer::with_seed(7); // `Anonymizer::new()` picks a random seed
//! let r = a.anonymize("123 N Zephyrmill Ave Apt 4, Miami, FL 33101");
//! assert!(r.text.contains(" N ") && r.text.contains(", FL 331"));
//! assert!(!r.text.contains("Zephyrmill"));
//! assert!(r.faithful); // the parser reads the copy the way it read the original
//! ```
//!
//! The rules, the options of `doorplate anonymize`, the limits and the measured rates are in
//! `docs/anonymizing.md`.
//!
//! This library formats and parses; it does not validate that an address exists or can
//! receive mail.

use crate::{Component, Lexicons, ParsedAddress, Parser};

/// The result of [`Anonymizer::anonymize`].
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct Anonymized {
    /// The obfuscated text, the same length in characters as the input.
    pub text: String,
    /// Whether the parser reads the output like the input: the same address type,
    /// warnings, suffix, directionals, unit designators, state and city, and the same
    /// shape (letters `a`, digits `9`) for the number, name, unit number and
    /// leftover text. `false` is not an error; it says the output is less faithful.
    pub faithful: bool,
}

/// Obfuscates address-like text: digits and unknown words change, the shape stays. The rules and
/// limits are in `docs/anonymizing.md`.
#[derive(Debug, Clone)]
pub struct Anonymizer {
    parser: Parser,
    seed: u64,
}

impl Default for Anonymizer {
    fn default() -> Self {
        Self::new()
    }
}

impl Anonymizer {
    /// An anonymizer with a random seed: two runs give different output, and nobody can
    /// recompute the replacements from the input.
    pub fn new() -> Self {
        Self::with_seed(random_seed())
    }

    /// An anonymizer with a fixed seed: the same input gives the same output (for tests
    /// and for repeatable files). A seed you publish lets anyone check a guessed input.
    pub fn with_seed(seed: u64) -> Self {
        Anonymizer {
            parser: Parser::new(),
            seed,
        }
    }

    /// The seed in use.
    pub fn seed(&self) -> u64 {
        self.seed
    }

    /// Obfuscates one line (or any text) and checks the result against the original.
    pub fn anonymize(&self, text: &str) -> Anonymized {
        let lex = Lexicons::builtin();
        let before = self.parser.parse(text).ok();
        let mut keep = before.as_ref().map(kept_spans).unwrap_or_default();
        keep.words.extend(form_words(text, &lex));
        let out = self.rewrite(text, &keep, &lex);
        let faithful = match (&before, self.parser.parse(&out).ok()) {
            (Some(a), Some(b)) => signature(a) == signature(&b),
            (None, None) => true,
            _ => false,
        };
        Anonymized {
            text: out,
            faithful,
        }
    }

    fn rewrite(&self, text: &str, keep: &Kept, lex: &Lexicons) -> String {
        let chars: Vec<(usize, char)> = text.char_indices().collect();
        let mut out = String::with_capacity(text.len());
        let mut i = 0;
        while i < chars.len() {
            let c = chars[i].1;
            if !c.is_alphanumeric() {
                out.push(c);
                i += 1;
                continue;
            }
            // A token: a maximal run of letters and digits.
            let mut j = i;
            while j < chars.len() && chars[j].1.is_alphanumeric() {
                j += 1;
            }
            let start = chars[i].0;
            let end = chars.get(j).map_or(text.len(), |c| c.0);
            let token = &text[start..end];
            let prev = i.checked_sub(1).map(|p| chars[p].1);
            let next = chars.get(j).map(|c| c.1);
            out.push_str(&self.token(token, start, end, prev, next, keep, lex));
            i = j;
        }
        out
    }

    #[allow(clippy::too_many_arguments)]
    fn token(
        &self,
        token: &str,
        start: usize,
        end: usize,
        prev: Option<char>,
        next: Option<char>,
        keep: &Kept,
        lex: &Lexicons,
    ) -> String {
        // Letters inside a kept span stay; digits never do (only a ZIP's prefix).
        let in_kept = keep.words.iter().any(|&(s, e)| s <= start && end <= e);
        // Split into runs of digits and runs of letters: `12A`, `5TH`, `APT4`.
        let runs = split_runs(token);
        let all_runs_ordinal = runs.len() == 2 && runs[0].0 && is_ordinal_suffix(runs[1].1);
        let mut out = String::new();
        for (idx, &(is_digits, run)) in runs.iter().enumerate() {
            if is_digits {
                let lone_fraction = run.chars().count() == 1
                    && (prev == Some('/') && idx == 0
                        || next == Some('/') && idx + 1 == runs.len());
                let zip_prefix = keep
                    .zip3
                    .iter()
                    .any(|&(s, e)| s <= start && end <= e)
                    .then_some(3);
                if lone_fraction {
                    out.push_str(run);
                } else {
                    out.push_str(&self.digits(run, zip_prefix));
                }
            } else if all_runs_ordinal && idx == 1 {
                let sfx = ordinal_suffix(&out, run);
                out.push_str(&sfx);
            } else if in_kept {
                out.push_str(run);
            } else {
                out.push_str(&self.word(run, lex));
            }
        }
        out
    }

    /// Other digits of the same length; never equal to `run`; leading zeros stay.
    fn digits(&self, run: &str, keep_prefix: Option<usize>) -> String {
        let orig: Vec<char> = run.chars().collect();
        let lead_zeros = orig
            .iter()
            .take_while(|&&c| c == '0')
            .count()
            .min(orig.len() - 1);
        let keep = keep_prefix.unwrap_or(0).min(orig.len()).max(lead_zeros);
        if keep == orig.len() {
            return run.to_string();
        }
        // The first replaced digit is never zero, so a number does not gain a leading zero.
        let lo = |k: usize| u32::from(k == keep && keep == lead_zeros);
        let mut h = Rng::new(self.seed, run, 0);
        let mut out: Vec<char> = orig.clone();
        for (k, slot) in out.iter_mut().enumerate().skip(keep) {
            let l = lo(k);
            *slot = digit(l + (h.next() % u64::from(10 - l)) as u32);
        }
        if out == orig {
            // The same value by chance: step the last replaced digit to the next one.
            let k = out.len() - 1;
            let l = lo(k);
            let d = out[k].to_digit(10).unwrap_or(0);
            out[k] = digit(l + (d - l + 1) % (10 - l));
        }
        out.into_iter().collect()
    }

    /// A word: kept when it is a lexicon word or one letter, else an invented word of the
    /// same length and case that is no lexicon word and not the original.
    fn word(&self, run: &str, lex: &Lexicons) -> String {
        let n = run.chars().count();
        if n <= 1 || in_lexicon(run, lex) {
            return run.to_string();
        }
        let upper = run.to_uppercase();
        for salt in 0..32u64 {
            let mut h = Rng::new(self.seed, &upper, salt + 1);
            let cand = invent(&mut h, n);
            if cand != upper && !in_lexicon(&cand, lex) {
                return copy_case(run, &cand);
            }
        }
        // Practically unreachable: a fixed fallback that differs from the original.
        copy_case(run, &"Q".repeat(n).replacen('Q', "X", 1))
    }
}

/// The spans the parser found that must stay as written.
#[derive(Debug, Default)]
struct Kept {
    /// Byte ranges kept whole: city and state.
    words: Vec<(usize, usize)>,
    /// Byte ranges of a ZIP: its first three digits stay.
    zip3: Vec<(usize, usize)>,
}

fn kept_spans(a: &ParsedAddress) -> Kept {
    let mut k = Kept::default();
    // Spans index the original only for single-line input, which is all `parse` takes.
    // Without a state or a matched place the "city" of a street line is a guess, and often
    // part of the street: keep it only when the parse found a place to stand on.
    let city_is_real = a.state.is_some() || a.place.is_some();
    for s in &a.source.spans {
        match s.component {
            Component::City if city_is_real => k.words.push((s.span.start, s.span.end)),
            Component::State => k.words.push((s.span.start, s.span.end)),
            Component::Zip5 => k.zip3.push((s.span.start, s.span.end)),
            _ => {}
        }
    }
    k
}

/// Byte ranges of the words of a multi-word lexicon form (`PO BOX`, `NORTH EAST`, `NEW YORK`),
/// which are lexicon words only together. A window of up to `MAX_FORM_WORDS` words that are
/// separated by spaces or periods is checked as one string.
fn form_words(text: &str, lex: &Lexicons) -> Vec<(usize, usize)> {
    let mut words: Vec<(usize, usize)> = Vec::new();
    let mut start = None;
    for (i, c) in text.char_indices() {
        match (c.is_alphabetic(), start) {
            (true, None) => start = Some(i),
            (false, Some(s)) => {
                words.push((s, i));
                start = None;
            }
            _ => {}
        }
    }
    if let Some(s) = start {
        words.push((s, text.len()));
    }
    let mut out = Vec::new();
    for w in 0..words.len() {
        for n in (2..=crate::lexicon::MAX_FORM_WORDS.min(words.len() - w)).rev() {
            let span = &words[w..w + n];
            let joined_ok = span
                .windows(2)
                .all(|p| text[p[0].1..p[1].0].chars().all(|c| c == ' ' || c == '.'));
            if !joined_ok {
                continue;
            }
            let form = span
                .iter()
                .map(|&(s, e)| &text[s..e])
                .collect::<Vec<_>>()
                .join(" ");
            if in_lexicon(&form, lex) {
                out.extend_from_slice(span);
                break;
            }
        }
    }
    out
}

/// What the parser sees, with names and numbers reduced to their shape.
fn signature(a: &ParsedAddress) -> String {
    let abbr = |d: &Option<crate::Directional>| d.map(|d| d.abbr()).unwrap_or("");
    let mut codes: Vec<&str> = a.diagnostics.warnings.iter().map(|w| w.code()).collect();
    codes.sort_unstable();
    let shape = |s: &Option<String>| s.as_deref().map(shape_of).unwrap_or_default();
    format!(
        "{:?}|{}|{}|{}|{}|{}|{:?}|{}|{}|{:?}|{}|{}|{}|{}|{}|{}|{}|{}|{}",
        a.address_type(),
        codes.join(","),
        shape(&a.street_number),
        abbr(&a.street_dir_prefix),
        shape(&a.street_name),
        a.street_suffix.map(|s| s.abbr()).unwrap_or(""),
        a.street_dir_suffix.map(|d| d.abbr()),
        a.unit_type.map(|u| u.abbr()).unwrap_or(""),
        shape(&a.unit_number),
        a.second_unit_type.map(|u| u.abbr()),
        shape(&a.second_unit_number),
        a.city.as_deref().unwrap_or(""),
        a.state.map(|s| s.code()).unwrap_or(""),
        a.zip5.as_deref().map_or(0, str::len),
        a.zip4.as_deref().map_or(0, str::len),
        shape(&a.po_box),
        a.general_delivery,
        shape(&a.attention),
        shape(&a.diagnostics.unparsed),
    )
}

/// Letters become `a`, digits `9`, runs collapse: `12A OAK` is `9a a`.
fn shape_of(s: &str) -> String {
    let mut out = String::new();
    for c in s.chars() {
        let m = if c.is_alphabetic() {
            'a'
        } else if c.is_ascii_digit() {
            '9'
        } else {
            c
        };
        if (m == 'a' || m == '9') && out.ends_with(m) {
            continue;
        }
        out.push(m);
    }
    out
}

/// Runs of digits and of non-digits in a token: `5TH` is `[(true,"5"), (false,"TH")]`.
fn split_runs(token: &str) -> Vec<(bool, &str)> {
    let mut runs = Vec::new();
    let mut start = 0;
    let mut cur: Option<bool> = None;
    for (i, c) in token.char_indices() {
        let d = c.is_ascii_digit();
        if cur.is_some() && cur != Some(d) {
            runs.push((cur.unwrap_or(false), &token[start..i]));
            start = i;
        }
        cur = Some(d);
    }
    if cur.is_some() {
        runs.push((cur.unwrap_or(false), &token[start..]));
    }
    runs
}

fn is_ordinal_suffix(s: &str) -> bool {
    matches!(s.to_ascii_uppercase().as_str(), "ST" | "ND" | "RD" | "TH")
}

/// The ordinal suffix for the number just written, in the case of the original.
fn ordinal_suffix(number: &str, original: &str) -> String {
    let n: u64 = number.parse().unwrap_or(0);
    let s = match (n % 10, n % 100) {
        (_, 11..=13) => "TH",
        (1, _) => "ST",
        (2, _) => "ND",
        (3, _) => "RD",
        _ => "TH",
    };
    copy_case(original, s)
}

fn in_lexicon(word: &str, lex: &Lexicons) -> bool {
    lex.suffix(word).is_some()
        || lex.directional(word).is_some()
        || lex.unit(word).is_some()
        || lex.state(word).is_some()
        || lex.special(word).is_some()
        || lex.highway(word).is_some()
        || lex.military(word).is_some()
        || lex.military_post_office(word).is_some()
}

const CONSONANTS: &[u8] = b"BCDFGHJKLMNPRSTVWZ";
const VOWELS: &[u8] = b"AEIOU";

/// A pronounceable invented word of `n` letters, upper case.
fn invent(h: &mut Rng, n: usize) -> String {
    (0..n)
        .map(|k| {
            let set = if k % 2 == 0 { CONSONANTS } else { VOWELS };
            set[(h.next() % set.len() as u64) as usize] as char
        })
        .collect()
}

/// `cand` (upper case) in the case pattern of `orig`, character by character.
fn copy_case(orig: &str, cand: &str) -> String {
    orig.chars()
        .zip(cand.chars())
        .map(|(o, c)| {
            if o.is_lowercase() {
                c.to_ascii_lowercase()
            } else {
                c
            }
        })
        .collect()
}

fn digit(d: u32) -> char {
    char::from_digit(d, 10).unwrap_or('0')
}

/// A small keyed generator (FNV-1a over the seed, the value and a salt, then splitmix64).
/// Its output is stable across versions, which `std`'s hashers do not promise.
struct Rng(u64);

impl Rng {
    fn new(seed: u64, value: &str, salt: u64) -> Self {
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for b in seed
            .to_le_bytes()
            .iter()
            .chain(value.as_bytes())
            .chain(salt.to_le_bytes().iter())
        {
            h ^= u64::from(*b);
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
        Rng(h)
    }

    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }
}

fn random_seed() -> u64 {
    use std::collections::hash_map::RandomState;
    use std::hash::{BuildHasher, Hasher};
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    // `RandomState` is seeded by the operating system, and its keys change with each new
    // value; the clock and a counter keep two calls in one tick apart on a coarse clock.
    let os = RandomState::new().build_hasher().finish();
    let t = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_nanos() as u64);
    let n = COUNTER.fetch_add(1, Ordering::Relaxed);
    Rng::new(os ^ t, "seed", n).next()
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    fn a() -> Anonymizer {
        Anonymizer::with_seed(7)
    }

    #[test]
    fn keeps_the_shape_and_changes_the_names() {
        let r = a().anonymize("123 N Zephyrmill Ave Apt 4, Miami, FL 33101");
        assert!(r.text.starts_with(|c: char| c.is_ascii_digit()));
        assert_ne!(r.text, "123 N Zephyrmill Ave Apt 4, Miami, FL 33101");
        assert!(r.text.contains(" N "), "{}", r.text);
        assert!(r.text.contains(" Ave Apt "), "{}", r.text);
        assert!(r.text.contains(", Miami, FL 331"), "{}", r.text);
        assert!(!r.text.contains("Zephyrmill"));
        assert_eq!(r.text.chars().count(), 43);
        assert!(r.faithful, "{}", r.text);
    }

    #[test]
    fn same_input_same_output_and_seed_changes_it() {
        let x = a().anonymize("77 Quincewood Rd").text;
        assert_eq!(x, a().anonymize("77 Quincewood Rd").text);
        assert_ne!(
            x,
            Anonymizer::with_seed(8).anonymize("77 Quincewood Rd").text
        );
    }

    #[test]
    fn a_repeated_value_gets_the_same_replacement() {
        let t = a().anonymize("55 Bayview Dr, 55 Bayview Dr").text;
        let (l, r) = t.split_once(", ").unwrap();
        assert_eq!(l, r);
    }

    #[test]
    fn digits_never_equal_the_original_and_keep_leading_zeros() {
        for seed in 0..200 {
            let z = Anonymizer::with_seed(seed);
            for n in ["7", "0", "9", "10", "007", "1234"] {
                let t = z.anonymize(n).text;
                assert_ne!(t, n, "seed {seed}");
                assert_eq!(t.len(), n.len());
                if n.starts_with('0') && n.len() > 1 {
                    assert!(t.starts_with('0'));
                }
                if !n.starts_with('0') {
                    assert!(!t.starts_with('0'), "{t}");
                }
            }
        }
    }

    #[test]
    fn ordinals_stay_ordinals() {
        for seed in 0..50 {
            let t = Anonymizer::with_seed(seed).anonymize("12 5th Ave").text;
            let w = t.split(' ').nth(1).unwrap();
            let n: u64 = w[..w.len() - 2].parse().unwrap();
            assert_eq!(
                w[w.len() - 2..].to_string(),
                ordinal_suffix(&n.to_string(), "th")
            );
        }
    }

    #[test]
    fn fractions_hyphens_and_letters_keep_their_form() {
        let t = a().anonymize("12A 1/2 Oakline St").text;
        assert!(t.contains(" 1/2 "), "{t}");
        assert!(t.split(' ').next().unwrap().ends_with('A'), "{t}");
        let t = a().anonymize("41-20 Bayview Ave").text;
        let num = t.split(' ').next().unwrap();
        assert_eq!(num.len(), 5);
        assert_eq!(&num[2..3], "-");
    }

    #[test]
    fn unparseable_text_still_changes() {
        let t = a().anonymize("???").text;
        assert_eq!(t, "???");
        let t = a().anonymize("c/o Marigold Holdings 99 !!").text;
        assert!(t.starts_with("c/o "), "{t}");
        assert!(!t.contains("Marigold") && !t.contains("99"), "{t}");
    }

    #[test]
    fn invented_words_are_not_lexicon_words() {
        let lex = Lexicons::builtin();
        for seed in 0..300 {
            let z = Anonymizer::with_seed(seed);
            for w in ["Zephyrmill", "Quincewood", "Bayview", "Oak", "Ox"] {
                let t = z.word(w, &lex);
                assert!(!in_lexicon(&t, &lex) || in_lexicon(w, &lex), "{t}");
                assert_ne!(t.to_uppercase(), w.to_uppercase());
                assert_eq!(t.chars().count(), w.chars().count());
            }
        }
    }

    #[test]
    fn ordinal_suffixes_follow_the_number() {
        for (n, want) in [
            ("1", "ST"),
            ("2", "ND"),
            ("3", "RD"),
            ("4", "TH"),
            ("11", "TH"),
            ("12", "TH"),
            ("13", "TH"),
            ("21", "ST"),
            ("111", "TH"),
            ("112", "TH"),
            ("101", "ST"),
        ] {
            assert_eq!(ordinal_suffix(n, "TH"), want, "{n}");
        }
        assert_eq!(ordinal_suffix("3", "th"), "rd");
    }

    #[test]
    fn a_whole_run_kept_as_a_zip_prefix_is_unchanged() {
        assert_eq!(a().digits("123", Some(3)), "123");
        assert_eq!(&a().digits("33101", Some(3))[..3], "331");
        assert_ne!(&a().digits("33101", Some(3))[3..], "01");
    }

    #[test]
    fn default_is_new() {
        assert_ne!(Anonymizer::default().seed(), Anonymizer::default().seed());
    }

    #[test]
    fn random_seeds_differ_even_when_created_back_to_back() {
        let seeds: std::collections::HashSet<u64> =
            (0..1000).map(|_| Anonymizer::new().seed()).collect();
        assert_eq!(seeds.len(), 1000);
    }

    #[test]
    fn case_is_kept() {
        let t = a().anonymize("55 BAYVIEW dr").text;
        let w = t.split(' ').nth(1).unwrap();
        assert!(w.chars().all(|c| c.is_ascii_uppercase()), "{t}");
        let t = a().anonymize("55 bayview dr").text;
        assert!(
            t.split(' ')
                .nth(1)
                .unwrap()
                .chars()
                .all(|c| c.is_ascii_lowercase()),
            "{t}"
        );
    }

    #[test]
    fn po_box_and_rural_route_stay_forms() {
        let r = a().anonymize("PO Box 1234, Austin, TX 78701");
        assert!(r.text.starts_with("PO Box "), "{}", r.text);
        assert!(r.faithful, "{}", r.text);
        let r = a().anonymize("RR 2 Box 15, Dalton, GA 30720");
        assert!(r.text.starts_with("RR "), "{}", r.text);
        assert!(r.faithful, "{}", r.text);
    }

    #[test]
    fn output_is_never_the_input_for_text_with_names_or_numbers() {
        for line in ["9 Foobar Way", "Unit 12", "Mr Smith, 5 Elm"] {
            assert_ne!(a().anonymize(line).text, line);
        }
    }
}
