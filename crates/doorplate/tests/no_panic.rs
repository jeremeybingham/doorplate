//! Property tests for the never-panic rule (CONTRIBUTING.md): any input parses
//! without panicking, every span indexes valid text, and every emitter runs.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use doorplate::{Fields, KeyOptions, ParseError, ParseOptions, ParsedAddress, Parser};
use proptest::prelude::*;

/// Address-shaped fragments, so generated input reaches the tagger rules
/// rather than stopping at the first unknown token.
const WORDS: &[&str] = &[
    "123",
    "C/O",
    "%",
    "ATTN",
    "4-H",
    "Club",
    "Star",
    "Bay",
    "Heron",
    "2B",
    "Pinebriar",
    "Hartford",
    "CT",
    "KY",
    "WY",
    "MT",
    "06103",
    "Dept",
    "Department",
    "Math",
    "POX",
    "BX",
    "Pop",
    "OX",
    "USA",
    "United",
    "States",
    "4871",
    "One",
    "Two",
    "Third",
    "Floor",
    "Flr",
    "Mile",
    "Acme",
    "Inc",
    "CO",
    "Box",
    "NO",
    "Num",
    "Loc",
    "Suit",
    "Floo",
    "250",
    "3440",
    "N",
    "SW",
    "Main",
    "St",
    "Street",
    "Apt",
    "Unit",
    "#",
    "4B",
    "PO",
    "Box",
    "RR",
    "HC",
    "Hwy",
    "US",
    "Highway",
    "I-95",
    "FL",
    "Miami",
    "33101",
    "33101-1234",
    "APO",
    "AE",
    "Gen",
    "Delivery",
    "1/2",
    "12-14",
    "No",
    "Situs",
    "St.",
    "Ste",
    "Fl",
    "Rd",
    "Ave",
    "&",
    "-",
    ",",
    ";",
    ".",
    "é",
    "ß",
    "İ",
    "日本",
    "\u{0}",
    "\t",
    "\u{200b}",
    "\u{202e}",
];

fn address_like() -> impl Strategy<Value = String> {
    prop::collection::vec(prop::sample::select(WORDS), 0..14).prop_map(|w| w.join(" "))
}

fn field() -> impl Strategy<Value = Option<String>> {
    prop::option::of(prop_oneof![address_like(), any::<String>()])
}

fn check(r: Result<ParsedAddress, ParseError>) {
    let Ok(a) = r else { return };
    for cs in &a.source.spans {
        let text = a.source.text(&cs.span);
        assert!(text.is_some(), "span does not index input: {cs:?}");
        assert!(cs.span.start <= cs.span.end);
    }
    let _ = (a.key(KeyOptions::property()), a.key(KeyOptions::unit()));
    let _ = a.slug();
    let _ = a.to_usps();
    let _ = a.to_usps_wrapped(30);
    let _ = a.to_reso().fields();
    let _ = a.to_reso().length_overruns();
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(2000))]

    #[test]
    fn arbitrary_string_never_panics(s in any::<String>()) {
        let p = Parser::new();
        check(p.parse(&s));
    }

    #[test]
    fn address_like_never_panics(s in address_like()) {
        let p = Parser::new();
        check(p.parse(&s));
    }

    #[test]
    fn fields_never_panic(
        line1 in field(), line2 in field(), city in field(),
        state in field(), zip in field(),
    ) {
        let p = Parser::new();
        let f = Fields { line1, line2, city, state, zip };
        check(p.parse_fields(&f));
    }

    /// A default_state hint never panics and never fills the state.
    #[test]
    fn hinted_parser_never_panics_or_fills_state(
        s in address_like(), st in prop::sample::select(&["FL", "AL", "ny", "Texas", "DC", "PR"][..]),
    ) {
        let hinted = Parser::with_options(ParseOptions::new().default_state(st)).unwrap();
        let plain = Parser::new();
        if let (Ok(a), Ok(b)) = (hinted.parse(&s), plain.parse(&s)) {
            prop_assert_eq!(a.state, b.state);
            prop_assert_eq!(a.zip5.clone(), b.zip5.clone());
            // Only the hint's own reading differs; with a state or a known
            // ZIP the two parses are identical.
            if b.state.is_some() {
                prop_assert_eq!(a, b);
            }
        }
        check(hinted.parse(&s));
    }

    #[test]
    fn parse_many_matches_parse(v in prop::collection::vec(address_like(), 0..8)) {
        let p = Parser::new();
        let refs: Vec<&str> = v.iter().map(String::as_str).collect();
        let many = p.parse_many(&refs);
        prop_assert_eq!(many.len(), refs.len());
        for (m, s) in many.into_iter().zip(&refs) {
            prop_assert_eq!(m, p.parse(s));
        }
    }

    #[test]
    fn parse_fields_many_matches_parse_fields(
        v in prop::collection::vec((address_like(), address_like()), 0..8)
    ) {
        let p = Parser::new();
        let fields: Vec<Fields> = v
            .into_iter()
            .map(|(a, b)| Fields {
                line1: Some(a),
                city: Some(b),
                ..Fields::default()
            })
            .collect();
        let many = p.parse_fields_many(&fields);
        prop_assert_eq!(many.len(), fields.len());
        for (m, f) in many.into_iter().zip(&fields) {
            prop_assert_eq!(m, p.parse_fields(f));
        }
    }

    /// Keys are spelling-independent: case changes never change the key.
    #[test]
    fn key_ignores_ascii_case(s in address_like()) {
        let p = Parser::new();
        if let (Ok(a), Ok(b)) = (p.parse(&s), p.parse(&s.to_uppercase())) {
            if s.is_ascii() {
                prop_assert_eq!(a.key(KeyOptions::unit()), b.key(KeyOptions::unit()));
            }
        }
    }
}

/// A care-of marker after a street, with its number in the same or a later
/// comma segment, on one line or two (#126).
#[test]
fn care_of_after_street_never_panics() {
    let parser = Parser::new();
    for marker in ["%", "C/O", "ATTN", "c/o"] {
        for rest in [
            "5 STAR GROUP",
            "4-H CLUB",
            "9",
            "4 BAYVIEW WEST A",
            "123 MAIN ST",
            "123 MAIN",
            "",
            ", 5 STAR",
            "5,",
        ] {
            for street in ["123 MAIN ST", "123 MAIN ST STE 4", "123", "MAIN ST"] {
                let one = format!("{street} {marker} {rest}, MIAMI FL 33101");
                let _ = parser.parse(&one);
                let _ = parser.parse(&format!("{street}, {marker} {rest}"));
                let _ = parser.parse_fields(&Fields {
                    line1: Some(street.to_string()),
                    line2: Some(format!("{marker} {rest}")),
                    city: Some("MIAMI".to_string()),
                    state: Some("FL".to_string()),
                    zip: Some("33101".to_string()),
                });
            }
        }
    }
}

/// Recipient words, a marker or `CO` ahead of an address or a box, on one line
/// or two, in every comma placement (#127).
#[test]
fn recipient_before_address_never_panics() {
    let parser = Parser::new();
    for lead in [
        "C/O ACME INC",
        "CO ACME INC",
        "CO",
        "ACME INC",
        "ATTN",
        "CO RD",
        "ACME CO",
        "",
    ] {
        for tail in [
            "20 QUINCEWOOD CT",
            "7100 ZEPHYRMILL DR S",
            "500 5TH AVE",
            "20 CT",
            "20",
            "PO BOX 12345",
            "PO BOX",
            "12 BAYVIEW RD STE 4",
            "612 QUINCEWOOD ST, MIAMI FL 33101",
        ] {
            for sep in [" ", ", ", " , "] {
                let line = format!("{lead}{sep}{tail}");
                let _ = parser.parse(&line);
                let _ = parser.parse(&format!("{line}, MIAMI FL 33101"));
                let _ = parser.parse_fields(&Fields {
                    line1: Some(line),
                    line2: Some("% ACME INC".to_string()),
                    city: Some("MIAMI".to_string()),
                    state: Some("FL".to_string()),
                    zip: Some("33101".to_string()),
                });
            }
        }
    }
}

/// Units written with two numbers, with `BOX`, `NO`, `NUM` or `LOC`, with a cut
/// designator, or twice, in every position after a street (#128).
#[test]
fn unusual_units_never_panic() {
    let parser = Parser::new();
    for street in [
        "123 MAIN ST",
        "123 N MAIN ST NW",
        "123 AVE OF THE ELMS",
        "123",
        "MAIN ST",
        "PO BOX 5",
    ] {
        for unit in [
            "STE 180 417020",
            "250 3440",
            "FL 2 270",
            "BOX 3300",
            "NO 65",
            "NUM",
            "NUM 230 4",
            "LOC 12",
            "SUIT",
            "STE STE C",
            "STE STE",
            "15TH FLOO",
            "3RD FLO",
            "# 1 2 3",
            "BOX NO 5",
            "NO NO",
        ] {
            for sep in [" ", ", "] {
                let line = format!("{street}{sep}{unit}");
                let _ = parser.parse(&line);
                let _ = parser.parse(&format!("{line}, MIAMI FL 33101"));
                let _ = parser.parse_fields(&Fields {
                    line1: Some(street.to_string()),
                    line2: Some(unit.to_string()),
                    city: Some("MIAMI".to_string()),
                    state: Some("FL".to_string()),
                    zip: Some("33101".to_string()),
                });
            }
        }
    }
}

/// Spelled-out house numbers, unit numbers and floors, in every position and
/// comma placement (#129).
#[test]
fn spelled_numbers_never_panic() {
    let parser = Parser::new();
    for lead in [
        "ONE",
        "TWO",
        "TWENTY",
        "ONE NORTH",
        "ONE MILE",
        "THIRD",
        "ONE ONE",
        "",
    ] {
        for tail in [
            "COMMERCE PLAZA",
            "QUINCEWOOD PLAZA BOX 3300",
            "BAYVIEW LANE 15TH FLOOR",
            "MAIN ST SUITE TWO",
            "MAIN ST THIRD FLOOR",
            "MAIN ST THIRD FLR",
            "MAIN ST SUITE",
            "MAIN ST SUITE TWENTY ONE",
            "PLAZA",
            "ST",
            "",
        ] {
            for sep in [" ", ", ", " , "] {
                let line = format!("{lead}{sep}{tail}");
                let _ = parser.parse(&line);
                let _ = parser.parse(&format!("{line}, MIAMI FL 33101"));
                let _ = parser.parse_fields(&Fields {
                    line1: Some(line),
                    line2: Some("THIRD FLOOR".to_string()),
                    city: Some("MIAMI".to_string()),
                    state: Some("FL".to_string()),
                    zip: Some("33101".to_string()),
                });
            }
        }
    }
}

/// A department name on a later line or comma segment, with and without other
/// words, digits and designators around it (#166).
#[test]
fn department_lines_never_panic() {
    let parser = Parser::new();
    for dept in [
        "MATH DEPT",
        "HUMAN RESOURCES DEPARTMENT",
        "DEPT",
        "DEPT 4",
        "DEPT.",
        "SUITE B FINANCE DEPT",
        "ATTN ACCOUNTS DEPT",
        "PO BOX DEPT",
        "DEPT OF MATH DEPT",
        "MATH DEPT 4",
        "# DEPT",
        "(MATH) DEPT",
        "- DEPT",
    ] {
        for street in ["123 MAIN ST", "123", "MAIN ST", "", "FIRE DEPT RD"] {
            for sep in [" ", ", ", " - "] {
                let line = format!("{street}{sep}{dept}");
                let _ = parser.parse(&line);
                let _ = parser.parse(&format!("{line}, MIAMI FL 33101"));
                let _ = parser.parse_fields(&Fields {
                    line1: Some(street.to_string()),
                    line2: Some(dept.to_string()),
                    city: Some("MIAMI".to_string()),
                    state: Some("FL".to_string()),
                    zip: Some("33101".to_string()),
                });
            }
        }
    }
}

/// `BAY` ahead of a value, a hash, a directional or nothing, in every
/// position, including as the first and only word (#144).
#[test]
fn bay_never_panics() {
    let parser = Parser::new();
    for lead in [
        "",
        "1305",
        "1305 HERON",
        "1305 MAIN ST",
        "1305 N",
        "1305 22A",
        "# ",
        "HERON",
    ] {
        for tail in [
            "BAY",
            "BAY 2B",
            "BAY # 2B",
            "BAY W 45",
            "BAY #",
            "BAY BAY 4",
            "BAY ST",
            "BAY UNIT 2B",
            "# BAY 4",
        ] {
            for sep in [" ", ", ", " , "] {
                let line = format!("{lead}{sep}{tail}");
                let _ = parser.parse(&line);
                let _ = parser.parse(&format!("{line}, MIAMI FL 33101"));
                let _ = parser.parse_fields(&Fields {
                    line1: Some(lead.to_string()),
                    line2: Some(tail.to_string()),
                    city: Some("MIAMI".to_string()),
                    state: Some("FL".to_string()),
                    zip: Some("33101".to_string()),
                });
            }
        }
    }
}

/// `LOOP` after a name, ahead of a value, a hash or a directional, in every
/// position (#145).
#[test]
fn loop_never_panics() {
    let parser = Parser::new();
    for lead in ["", "1305", "1305 MAPLE", "1305 N", "# ", "LOOP"] {
        for tail in [
            "LOOP",
            "LOOP 412",
            "LOOP # 412",
            "LOOP W 45",
            "LOOP LOOP 4",
            "LOOP ST",
            "LOOP UNIT 2B",
        ] {
            for sep in [" ", ", ", " , "] {
                let line = format!("{lead}{sep}{tail}");
                let _ = parser.parse(&line);
                let _ = parser.parse(&format!("{line}, MIAMI FL 33101"));
            }
        }
    }
}
