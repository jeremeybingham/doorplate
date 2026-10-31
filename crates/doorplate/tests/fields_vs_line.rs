//! One address, one key, however it arrives (#110): pre-split fields give the
//! same key as the one-line form, including the readings that only a state's
//! data has (`SR 60` is `STATE ROAD 60` in Florida).

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use doorplate::{Fields, KeyOptions, Parser};

/// Florida street lines (invented), with a city and a ZIP of that state.
const LINES: &[(&str, &str, &str)] = &[
    ("22200 SR 60", "LAKE WALES", "33898"),
    ("22200 STATE ROAD 60", "LAKE WALES", "33898"),
    ("3709 CTY HWY 214", "MIAMI", "33101"),
    ("3709 CO HWY 214", "MIAMI", "33101"),
    ("3709 COUNTY HWY 214", "MIAMI", "33101"),
    ("12 BAYVIEW CR", "MIAMI", "33101"),
    ("12 BAYVIEW CIR", "MIAMI", "33101"),
    ("500 N SR 7", "FORT LAUDERDALE", "33301"),
    ("1305 MAPLE COVE LOOP 412", "TAMPA", "33601"),
    ("1305 HERON BAY 2B", "TAMPA", "33601"),
    ("RR 2 BOX 45 A", "OCALA", "34470"),
    ("PO BOX 12", "OCALA", "34470"),
    ("123 MAIN ST APT 4", "WEST PALM BEACH", "33401"),
];

fn key(a: Result<doorplate::ParsedAddress, doorplate::ParseError>) -> Option<String> {
    a.unwrap().key(KeyOptions::unit())
}

#[test]
fn fields_and_one_line_give_the_same_key() {
    let p = Parser::new();
    for (line1, city, zip) in LINES {
        let one_line = key(p.parse(&format!("{line1}, {city}, FL {zip}")));
        assert!(one_line.is_some(), "{line1}");
        let fields = |state: Option<&str>, zip: Option<&str>| Fields {
            line1: Some(line1.to_string()),
            city: Some(city.to_string()),
            state: state.map(str::to_string),
            zip: zip.map(str::to_string),
            ..Fields::default()
        };
        // State and ZIP, then everything in line 1.
        let both = key(p.parse_fields(&fields(Some("FL"), Some(zip))));
        assert_eq!(both, one_line, "{line1}: city, state and ZIP fields");
        let all = Fields {
            line1: Some(format!("{line1}, {city}, FL {zip}")),
            ..Fields::default()
        };
        assert_eq!(
            key(p.parse_fields(&all)),
            one_line,
            "{line1}: all in line 1"
        );
        // A state or a ZIP alone still tells the state data; the key then has
        // the `k4n` prefix for the missing part, so compare the address part.
        let street = |k: &Option<String>| {
            k.as_ref()
                .unwrap()
                .split('|')
                .skip(1)
                .filter(|x| !x.is_empty() && *x != "FL" && *x != *zip)
                .collect::<Vec<_>>()
                .join("|")
        };
        for (what, f) in [
            ("state only", fields(Some("FL"), None)),
            ("ZIP only", fields(None, Some(zip))),
        ] {
            let k = key(p.parse_fields(&f));
            assert_eq!(street(&k), street(&one_line), "{line1}: {what}");
        }
    }
}
