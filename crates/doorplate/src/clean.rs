//! Input cleaning (pipeline step 1).
//!
//! Produces uppercase ASCII-leaning text with single spaces, and keeps a map
//! from every cleaned byte back to the original input so components can
//! report spans into the original text.
//!
//! What it does:
//! - Any Unicode whitespace or control character, including the
//!   non-breaking space seen in real license files (`BOYNTON\xa0BEACH`),
//!   becomes a space; runs of spaces collapse to one; ends are trimmed.
//! - Accented Latin letters lose their accent (`RATÓN` -> `RATON`).
//! - Curly quotes and Unicode dashes become their ASCII forms.
//! - Letters are uppercased.
//!
//! Punctuation is left for the tokenizer, which knows where commas, `#`,
//! hyphens and periods matter.

/// Cleaned text plus the map back to the original.
#[derive(Debug, Clone)]
pub(crate) struct Cleaned {
    pub text: String,
    /// For each byte of `text`, the original byte range of the character it
    /// came from.
    src: Vec<(usize, usize)>,
}

impl Cleaned {
    /// Original byte range covered by `text[start..end]`. `start < end`
    /// must hold; an empty or out-of-range request returns `None`.
    pub fn original_range(&self, start: usize, end: usize) -> Option<(usize, usize)> {
        if start >= end {
            return None;
        }
        let (s, _) = *self.src.get(start)?;
        let (_, e) = *self.src.get(end - 1)?;
        Some((s, e))
    }
}

pub(crate) fn clean(input: &str) -> Cleaned {
    let mut text = String::with_capacity(input.len());
    let mut src = Vec::with_capacity(input.len());
    let mut pending_space = false;
    for (i, c) in input.char_indices() {
        let range = (i, i + c.len_utf8());
        if c.is_ascii() {
            // ASCII: white space and controls are the bytes up to the space and DEL; every
            // other byte is kept, upper-cased, as one byte.
            if c <= ' ' || c == '\x7f' {
                pending_space = !text.is_empty();
                continue;
            }
            if pending_space {
                text.push(' ');
                src.push((range.0, range.0));
                pending_space = false;
            }
            text.push(c.to_ascii_uppercase());
            src.push(range);
            continue;
        }
        if c.is_whitespace() || c.is_control() {
            pending_space = !text.is_empty();
            continue;
        }
        if pending_space {
            // A space between two kept characters maps to the gap's start.
            text.push(' ');
            src.push((range.0, range.0));
            pending_space = false;
        }
        let mut push = |s: &str| {
            src.extend(std::iter::repeat(range).take(s.len()));
            text.push_str(s);
        };
        match fold(c) {
            Some(s) => push(s),
            None => {
                for u in c.to_uppercase() {
                    let mut buf = [0u8; 4];
                    push(u.encode_utf8(&mut buf));
                }
            }
        }
    }
    Cleaned { text, src }
}

/// ASCII replacement for a non-ASCII character, uppercased; `None` keeps
/// the character (uppercased by the caller).
fn fold(c: char) -> Option<&'static str> {
    if c.is_ascii() {
        return None;
    }
    Some(match c {
        'À'..='Å' | 'à'..='å' | 'Ā' | 'ā' | 'Ă' | 'ă' | 'Ą' | 'ą' => "A",
        'Æ' | 'æ' => "AE",
        'Ç' | 'ç' | 'Ć' | 'ć' | 'Č' | 'č' => "C",
        'Ð' | 'ð' | 'Ď' | 'ď' | 'Đ' | 'đ' => "D",
        'È'..='Ë' | 'è'..='ë' | 'Ē' | 'ē' | 'Ė' | 'ė' | 'Ę' | 'ę' | 'Ě' | 'ě' => "E",
        'Ğ' | 'ğ' => "G",
        'Ì'..='Ï' | 'ì'..='ï' | 'Ī' | 'ī' | 'Į' | 'į' | 'İ' | 'ı' => "I",
        'Ł' | 'ł' => "L",
        'Ñ' | 'ñ' | 'Ń' | 'ń' | 'Ň' | 'ň' => "N",
        'Ò'..='Ö' | 'Ø' | 'ò'..='ö' | 'ø' | 'Ō' | 'ō' | 'Ő' | 'ő' => "O",
        'Œ' | 'œ' => "OE",
        'Ř' | 'ř' => "R",
        'Ś' | 'ś' | 'Š' | 'š' | 'Ş' | 'ş' => "S",
        'ß' => "SS",
        'Ť' | 'ť' | 'Ţ' | 'ţ' => "T",
        'Ù'..='Ü' | 'ù'..='ü' | 'Ū' | 'ū' | 'Ů' | 'ů' | 'Ű' | 'ű' => "U",
        'Ý' | 'ý' | 'ÿ' | 'Ÿ' => "Y",
        'Ź' | 'ź' | 'Ż' | 'ż' | 'Ž' | 'ž' => "Z",
        '‘' | '’' | '‚' | '′' => "'",
        '“' | '”' | '„' | '″' => "\"",
        '‐' | '‑' | '‒' | '–' | '—' | '―' | '−' => "-",
        '＃' | '№' => "#",
        '½' => "1/2",
        '¼' => "1/4",
        '¾' => "3/4",
        _ => return None,
    })
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn folds_and_collapses() {
        let c = clean("  Boca\u{a0}Ratón ,  fl ");
        assert_eq!(c.text, "BOCA RATON , FL");
    }

    #[test]
    fn maps_back_to_original() {
        let input = "1  Ñame\u{a0}St";
        let c = clean(input);
        assert_eq!(c.text, "1 NAME ST");
        let (s, e) = c.original_range(2, 6).unwrap();
        assert_eq!(&input[s..e], "Ñame");
        let (s, e) = c.original_range(7, 9).unwrap();
        assert_eq!(&input[s..e], "St");
    }

    #[test]
    fn folds_letters_and_number_signs_the_table_lists() {
        // invented street names with a Turkish g, an oe ligature, a fullwidth and a numero sign
        assert_eq!(clean("Ğöl Œuvre").text, "GOL OEUVRE");
        assert_eq!(clean("12 Oak St ＃4").text, "12 OAK ST #4");
        assert_eq!(clean("12 Oak St № 4").text, "12 OAK ST # 4");
    }

    #[test]
    fn a_range_that_is_empty_or_outside_the_text_has_no_original() {
        let c = clean("12 OAK ST");
        assert_eq!(c.original_range(3, 3), None);
        assert_eq!(c.original_range(5, 2), None);
        assert_eq!(c.original_range(0, 99), None);
    }

    #[test]
    fn dashes_and_quotes() {
        assert_eq!(clean("N/A – Main’s").text, "N/A - MAIN'S");
    }

    /// `clean` before the ASCII branch (#672 C8): every character through the general path.
    fn clean_general(input: &str) -> Cleaned {
        let mut text = String::new();
        let mut src = Vec::new();
        let mut pending_space = false;
        for (i, c) in input.char_indices() {
            let range = (i, i + c.len_utf8());
            if c.is_whitespace() || c.is_control() {
                pending_space = !text.is_empty();
                continue;
            }
            if pending_space {
                text.push(' ');
                src.push((range.0, range.0));
                pending_space = false;
            }
            let mut push = |s: &str| {
                src.extend(std::iter::repeat(range).take(s.len()));
                text.push_str(s);
            };
            match fold(c) {
                Some(s) => push(s),
                None => {
                    for u in c.to_uppercase() {
                        let mut buf = [0u8; 4];
                        push(u.encode_utf8(&mut buf));
                    }
                }
            }
        }
        Cleaned { text, src }
    }

    /// The ASCII branch gives the text and the source map of the general path, on every
    /// ASCII byte and on mixes with non-ASCII and spacing characters.
    #[test]
    fn the_ascii_branch_matches_the_general_path() {
        let all: String = (0u8..=127).map(char::from).collect();
        let pool = [
            "a", "Z", "7", " ", "\t", "\u{7f}", "\u{0}", ",", "#", "é", "ß", "\u{a0}", "ǅ", "–",
        ];
        let mut x: u64 = 0x9E37_79B9_7F4A_7C15;
        let mut next = move || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            x
        };
        let mut inputs = vec![all, String::new(), " ".into()];
        for _ in 0..20_000 {
            let mut s = String::new();
            for _ in 0..(next() % 8) {
                s.push_str(pool[(next() >> 8) as usize % pool.len()]);
            }
            inputs.push(s);
        }
        for s in inputs {
            let (a, b) = (clean(&s), clean_general(&s));
            assert_eq!((a.text, a.src), (b.text, b.src), "{s:?}");
        }
    }
}
