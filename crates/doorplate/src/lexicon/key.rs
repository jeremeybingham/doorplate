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
    let already = b.is_ascii()
        && !b.is_empty()
        && b[0] != b' '
        && b[b.len() - 1] != b' '
        && !b
            .iter()
            .any(|c| c.is_ascii_lowercase() || *c == b'.' || *c < b' ')
        && !s.contains("  ");
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
