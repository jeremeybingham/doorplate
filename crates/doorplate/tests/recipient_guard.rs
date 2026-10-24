//! Words that are not recipient names (`[non_recipient]` in `special.toml`)
//! and single letters ahead of a house number are not made the attention line
//! (#127): the line is parsed as it was.

#![allow(clippy::unwrap_used)]

use doorplate::Parser;

#[test]
fn location_words_and_letters_are_not_recipients() {
    let parser = Parser::new();
    for lead in [
        "BLOCK", "BLK", "MILEPOST", "MILE", "MP", "BILLBD", "NO", "NO.", "NUMBER", "URB", "A", "B",
    ] {
        let a = parser
            .parse(&format!("{lead} 100 QUINCEWOOD ST, MIAMI FL 33101"))
            .unwrap();
        assert_eq!(a.attention, None, "{lead}");
    }
}

#[test]
fn company_words_are_recipients() {
    let parser = Parser::new();
    for lead in ["ACME INC", "ACME FOUNDATION", "DTC"] {
        let a = parser
            .parse(&format!("{lead} 100 QUINCEWOOD ST, MIAMI FL 33101"))
            .unwrap();
        assert_eq!(a.attention.as_deref(), Some(lead), "{lead}");
        assert_eq!(a.street_number.as_deref(), Some("100"), "{lead}");
    }
}
