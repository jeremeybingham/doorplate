//! Trailing country.
//!
//! `MIAMI, FL 33101, USA` and `... FL 33101 UNITED STATES` carry a country
//! the parser does not model. The tail is cut from the token list before
//! tagging, so it reaches neither the city nor `unparsed`, and the caller
//! raises [`crate::Warning::CountryIgnored`]. Only names of the United States
//! count (`data/special.toml` `[country]`); another country stays in the
//! parse as ordinary text.
//!
//! A name is cut only where it cannot be part of the address:
//! - it is a segment of its own after a comma (`MIAMI, USA`), or a whole
//!   field other than the street line; or
//! - it follows a ZIP or a state (`FL 33101 USA`, `FL US`).
//!
//! So `US` in `123 US HWY 1`, or after a street (`123 MAIN ST US`), stays.

use crate::classify::zip_parts;
use crate::lexicon::Lexicons;
use crate::tokenize::Token;

/// The longest country name, in words (`UNITED STATES OF AMERICA`).
const MAX_WORDS: usize = 4;

/// Cut a trailing country from `toks`; true when one was cut. With
/// `own_field`, the tokens are a whole field that is not the street line,
/// and a country that is all of it is cut too; otherwise something must
/// precede the country.
pub(crate) fn strip_trailing(toks: &mut Vec<Token>, own_field: bool, lex: &Lexicons) -> bool {
    let n = toks.len();
    for words in (1..=MAX_WORDS.min(n)).rev() {
        let k = n - words;
        let tail = &toks[k..];
        if tail.iter().any(|t| t.seg != tail[0].seg) {
            continue;
        }
        let text = tail.iter().map(|t| t.text.as_str()).collect::<Vec<_>>();
        if !lex.is_country(&text.join(" ")) {
            continue;
        }
        let cut = if k == 0 {
            own_field
        } else {
            let prev = &toks[k - 1];
            prev.seg != toks[k].seg
                || zip_parts(&prev.text).is_some()
                || ends_with_state(&toks[..k], lex)
        };
        if cut {
            toks.truncate(k);
            return true;
        }
    }
    false
}

/// Whether the tokens end in a state: one word (`FL`) or two (`NEW YORK`).
fn ends_with_state(toks: &[Token], lex: &Lexicons) -> bool {
    let n = toks.len();
    let last = &toks[n - 1].text;
    lex.state(last).is_some()
        || (n >= 2
            && toks[n - 2].seg == toks[n - 1].seg
            && lex.state(&format!("{} {last}", toks[n - 2].text)).is_some())
}

/// Names of countries other than the United States, as written after an address (English names
/// and common short forms; ISO 3166-1 short names). A foreign address ends in one (#361).
const FOREIGN: &[&str] = &[
    "AFGHANISTAN",
    "ALBANIA",
    "ALGERIA",
    "ANDORRA",
    "ANGOLA",
    "ARGENTINA",
    "ARMENIA",
    "AUSTRALIA",
    "AUSTRIA",
    "AZERBAIJAN",
    "BAHAMAS",
    "BAHRAIN",
    "BANGLADESH",
    "BARBADOS",
    "BELARUS",
    "BELGIUM",
    "BELIZE",
    "BENIN",
    "BERMUDA",
    "BHUTAN",
    "BOLIVIA",
    "BOSNIA",
    "BOTSWANA",
    "BRAZIL",
    "BRUNEI",
    "BULGARIA",
    "BURKINA FASO",
    "BURMA",
    "BURUNDI",
    "CAMBODIA",
    "CAMEROON",
    "CANADA",
    "CAYMAN ISLANDS",
    "CHAD",
    "CHILE",
    "CHINA",
    "COLOMBIA",
    "COSTA RICA",
    "CROATIA",
    "CUBA",
    "CYPRUS",
    "CZECH REPUBLIC",
    "CZECHIA",
    "DENMARK",
    "DOMINICAN REPUBLIC",
    "ECUADOR",
    "EGYPT",
    "EL SALVADOR",
    "ENGLAND",
    "ESTONIA",
    "ETHIOPIA",
    "FIJI",
    "FINLAND",
    "FRANCE",
    "GERMANY",
    "GHANA",
    "GREAT BRITAIN",
    "GREECE",
    "GUATEMALA",
    "GUYANA",
    "HAITI",
    "HOLLAND",
    "HONDURAS",
    "HONG KONG",
    "HUNGARY",
    "ICELAND",
    "INDIA",
    "INDONESIA",
    "IRAN",
    "IRAQ",
    "IRELAND",
    "ISRAEL",
    "ITALY",
    "IVORY COAST",
    "JAMAICA",
    "JAPAN",
    "JORDAN",
    "KAZAKHSTAN",
    "KENYA",
    "KOREA",
    "KUWAIT",
    "KYRGYZSTAN",
    "LAOS",
    "LATVIA",
    "LEBANON",
    "LIBYA",
    "LITHUANIA",
    "LUXEMBOURG",
    "MACAU",
    "MACEDONIA",
    "MADAGASCAR",
    "MALAYSIA",
    "MALDIVES",
    "MALI",
    "MALTA",
    "MEXICO",
    "MOLDOVA",
    "MONACO",
    "MONGOLIA",
    "MONTENEGRO",
    "MOROCCO",
    "MOZAMBIQUE",
    "MYANMAR",
    "NAMIBIA",
    "NEPAL",
    "NETHERLANDS",
    "NEW ZEALAND",
    "NICARAGUA",
    "NIGER",
    "NIGERIA",
    "NORTH KOREA",
    "NORTHERN IRELAND",
    "NORWAY",
    "OMAN",
    "PAKISTAN",
    "PALESTINE",
    "PANAMA",
    "PARAGUAY",
    "PERU",
    "PHILIPPINES",
    "POLAND",
    "PORTUGAL",
    "QATAR",
    "ROMANIA",
    "RUSSIA",
    "RWANDA",
    "SAUDI ARABIA",
    "SCOTLAND",
    "SENEGAL",
    "SERBIA",
    "SINGAPORE",
    "SLOVAKIA",
    "SLOVENIA",
    "SOMALIA",
    "SOUTH AFRICA",
    "SOUTH KOREA",
    "SPAIN",
    "SRI LANKA",
    "SUDAN",
    "SWEDEN",
    "SWITZERLAND",
    "SYRIA",
    "TAIWAN",
    "TAJIKISTAN",
    "TANZANIA",
    "THAILAND",
    "TRINIDAD",
    "TUNISIA",
    "TURKEY",
    "TURKIYE",
    "UAE",
    "UGANDA",
    "UK",
    "UKRAINE",
    "UNITED ARAB EMIRATES",
    "UNITED KINGDOM",
    "URUGUAY",
    "UZBEKISTAN",
    "VENEZUELA",
    "VIETNAM",
    "WALES",
    "YEMEN",
    "ZAMBIA",
    "ZIMBABWE",
];

/// Names that are also surnames or US place names (`FRANCE`, `JORDAN`, `CHINA`, `MEXICO`): they
/// count only with a digit in the text, such as a postal code.
const SURNAME_LIKE: &[&str] = &[
    "CANADA", "CHAD", "CHINA", "CUBA", "DENMARK", "EGYPT", "ENGLAND", "FRANCE", "GREECE",
    "HOLLAND", "INDIA", "IRELAND", "ISRAEL", "ITALY", "JAPAN", "JORDAN", "LEBANON", "MALI",
    "MALTA", "MEXICO", "NIGER", "NORWAY", "PANAMA", "PERU", "POLAND", "SCOTLAND", "SPAIN",
    "SWEDEN", "TURKEY", "WALES",
];

/// Whether the parse ends in a non-US country name: in the unplaced text, or, with no state, in the
/// city (`LYON 69001, FRANCE`, where the country was read as the city). See [`ends_in_foreign_country`].
pub(crate) fn foreign_address(addr: &crate::ParsedAddress, lex: &Lexicons) -> bool {
    let mut text = addr.diagnostics.unparsed.clone().unwrap_or_default();
    if addr.state.is_none() {
        if let Some(city) = &addr.city {
            text = format!("{text} {city}");
        }
    }
    !text.trim().is_empty() && ends_in_foreign_country(&text, lex)
}

/// Whether the text the parser could not place ends in a non-US country name (`LYON 69001 FRANCE`):
/// the address is foreign, and the US parse of it is a guess (#361). A US state name is never one
/// (`NEW MEXICO`, `GEORGIA`), and a name that is also a surname needs a digit in the text.
pub(crate) fn ends_in_foreign_country(unparsed: &str, lex: &Lexicons) -> bool {
    let upper = unparsed.to_uppercase();
    let words: Vec<&str> = upper
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .collect();
    let n = words.len();
    for w in (1..=MAX_WORDS.min(n)).rev() {
        let name = words[n - w..].join(" ");
        if !FOREIGN.contains(&name.as_str()) {
            continue;
        }
        let state = lex.state(&name).is_some()
            || (n > w && lex.state(&format!("{} {name}", words[n - w - 1])).is_some());
        let digit = words.iter().any(|w| w.chars().any(|c| c.is_ascii_digit()));
        return !state && (digit || !SURNAME_LIKE.contains(&name.as_str()));
    }
    false
}

#[cfg(test)]
mod foreign_tests {
    use super::*;

    #[test]
    fn a_foreign_country_ends_the_unparsed_text() {
        let lex = Lexicons::default();
        for s in [
            "LYON 69001 FRANCE",
            "Ajax, Ontario L1Z0E4, Canada",
            "ROLLESTON 7614 NEW ZEALAND",
            "DUBAI UAE",
            "LONDON NW1 6PU UNITED KINGDOM",
        ] {
            assert!(ends_in_foreign_country(s, &lex), "{s}");
        }
        for s in [
            "JANE FRANCE",
            "ATTN JORDAN",
            "SUITE 4 NEW MEXICO",
            "HARBOR & PINE",
            "GEORGIA",
            "TORONTO CANADA",
        ] {
            assert!(!ends_in_foreign_country(s, &lex), "{s}");
        }
    }
}
