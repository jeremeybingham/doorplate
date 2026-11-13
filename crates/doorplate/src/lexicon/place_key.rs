// Place-name comparison key. Like `key.rs`, this file is compiled twice:
// into the crate as `lexicon::place_key`, and into build.rs via `#[path]`, so
// the compiled place tables and the runtime lookups compare names with
// exactly the same rule. Keep it dependency-free and free of `crate::` paths.

/// The comparison key for a place name. Case, punctuation, spacing and
/// abbreviations do not count, so `St. Petersburg`, `SAINT PETERSBURG` and
/// `ST PETERSBURG` share a key, as do `W PALM BCH` and `WEST PALM BEACH`.
///
/// Each word is upper-cased and stripped of anything but letters and digits
/// (hyphens and slashes split words). `ST`, `FT` and `MT` become `SAINT`,
/// `FORT` and `MOUNT`; any other word is replaced by `expand(word)` when it
/// returns a full form (the caller passes directional and Pub 28 suffix
/// names, so `N` is `NORTH` and `SPGS` is `SPRINGS`). The words are joined
/// with no spaces (`DE FUNIAK` is `DEFUNIAK`).
// This file is compiled into the crate and into build.rs; each uses one of the two functions.
#[allow(dead_code)]
pub fn place_key<F, R>(s: &str, expand: F) -> String
where
    F: Fn(&str) -> Option<R>,
    R: AsRef<str>,
{
    let mut out = String::with_capacity(s.len());
    place_key_into(s, expand, &mut out);
    out
}

/// [`place_key`], appended to `out` (which is not cleared). Each word is
/// written into `out` as it is read and replaced in place when it expands,
/// so the call allocates nothing beyond `out`'s own growth.
#[allow(dead_code)]
pub fn place_key_into<F, R>(s: &str, expand: F, out: &mut String)
where
    F: Fn(&str) -> Option<R>,
    R: AsRef<str>,
{
    for word in s.split(|c: char| c.is_whitespace() || c == '-' || c == '/') {
        let start = out.len();
        for c in word.chars() {
            // ASCII is the common case: its upper case is one byte, no iterator.
            if c.is_ascii() {
                if c.is_ascii_alphanumeric() {
                    out.push(c.to_ascii_uppercase());
                }
            } else if c.is_alphanumeric() {
                out.extend(c.to_uppercase());
            }
        }
        let replacement = match &out[start..] {
            "" => continue,
            "ST" => Some("SAINT"),
            "FT" => Some("FORT"),
            "MT" => Some("MOUNT"),
            _ => None,
        };
        match replacement {
            Some(full) => {
                out.truncate(start);
                out.push_str(full);
            }
            None => {
                if let Some(full) = expand(&out[start..]) {
                    out.truncate(start);
                    out.push_str(full.as_ref());
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `place_key_into` before the ASCII branch (#672 C1a).
    fn general(s: &str) -> String {
        let mut out = String::new();
        for word in s.split(|c: char| c.is_whitespace() || c == '-' || c == '/') {
            let start = out.len();
            for c in word.chars().filter(|c| c.is_alphanumeric()) {
                out.extend(c.to_uppercase());
            }
            let r = match &out[start..] {
                "" => continue,
                "ST" => Some("SAINT"),
                "FT" => Some("FORT"),
                "MT" => Some("MOUNT"),
                _ => None,
            };
            if let Some(full) = r {
                out.truncate(start);
                out.push_str(full);
            }
        }
        out
    }

    #[test]
    fn the_ascii_branch_matches_the_general_loop() {
        let pool = [
            "st", "Ft.", "mt", "a", "Z9", " ", "-", "/", ".", "é", "ß", "ǅ", "'", "\u{a0}",
        ];
        let mut x: u64 = 0x2545_F491_4F6C_DD1D;
        let mut next = move || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            x
        };
        for _ in 0..20_000 {
            let mut s = String::new();
            for _ in 0..(next() % 8) {
                s.push_str(pool[(next() >> 8) as usize % pool.len()]);
            }
            assert_eq!(place_key(&s, |_| None::<&str>), general(&s), "{s:?}");
        }
    }
}
