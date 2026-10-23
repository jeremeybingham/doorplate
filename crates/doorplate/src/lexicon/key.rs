// Lexicon key normalization. This file is compiled twice: into the crate as
// `lexicon::key`, and into build.rs via `#[path]`, so the data tables and the
// runtime lookups normalize spellings with exactly the same function. Keep it
// dependency-free and free of `crate::` paths.

/// Normalize a spelling into a lexicon key: uppercase, periods removed, runs
/// of whitespace collapsed to one space, trimmed. `"P.O.  Box"` becomes
/// `"PO BOX"`, `"N.E."` becomes `"NE"`.
///
/// Anything else (hyphens, slashes, `#`, non-ASCII letters) is kept as is;
/// broader input cleaning happens before lexicon lookup, in the parser.
pub fn normalize_key(s: &str) -> String {
    normalize_key_cow(s).into_owned()
}

/// [`normalize_key`], borrowing the input when it is already a key (ASCII, no
/// lowercase letters, periods or whitespace other than single inner spaces),
/// which is the common case for tokens of upper-case input. Lookups use this
/// to skip an allocation per call.
pub fn normalize_key_cow(s: &str) -> std::borrow::Cow<'_, str> {
    let b = s.as_bytes();
    // One pass: ASCII, nothing a key would change (lowercase letters, periods,
    // control characters), and no space at either end or next to another.
    let mut already = !b.is_empty() && b[0] != b' ' && b[b.len() - 1] != b' ';
    let mut prev = 0u8;
    for &c in b {
        if !c.is_ascii()
            || c.is_ascii_lowercase()
            || c == b'.'
            || c < b' '
            || (c == b' ' && prev == b' ')
        {
            already = false;
            break;
        }
        prev = c;
    }
    if already {
        return std::borrow::Cow::Borrowed(s);
    }
    std::borrow::Cow::Owned(normalize_slow(s))
}

fn normalize_slow(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut pending_space = false;
    for c in s.chars() {
        if c == '.' {
            continue;
        }
        if c.is_whitespace() {
            pending_space = !out.is_empty();
            continue;
        }
        if pending_space {
            out.push(' ');
            pending_space = false;
        }
        out.extend(c.to_uppercase());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The one-pass check may borrow only when the string is already its own
    /// key, and otherwise the result is the slow path's (#147).
    #[test]
    fn the_fast_path_borrows_only_a_string_that_is_already_a_key() {
        let pool = [
            "A", "z", "AVE", "Ave", "N.E.", ".", " ", "  ", "\t", "\u{7f}", "é", "ß", "ǅ", "#",
            "-", "1/2", "PO", "box",
        ];
        let mut x: u64 = 0x2545_F491_4F6C_DD1D;
        let mut next = move || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            x
        };
        for _ in 0..40_000 {
            let mut s = String::new();
            for _ in 0..(next() % 6) {
                s.push_str(pool[(next() >> 8) as usize % pool.len()]);
                if next() % 3 == 0 {
                    s.push(' ');
                }
            }
            let slow = normalize_slow(&s);
            let fast = normalize_key_cow(&s);
            if matches!(fast, std::borrow::Cow::Borrowed(_)) {
                assert_eq!(fast, s, "{s:?}");
            }
            assert_eq!(fast, slow, "{s:?}");
        }
    }
}
