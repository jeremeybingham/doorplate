//! A tour of the library: `cargo run -p doorplate --example quickstart`.
//!
//! Every address is invented. The library parses and formats; it does not
//! check that an address exists or can receive mail.

use doorplate::{Fields, KeyOptions, ParseOptions, Parser};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let parser = Parser::new();

    // One line. Only input with no address text is an error.
    let a = parser.parse("123 north main street apt 4, Miami FL 33101")?;
    println!("street name   {:?}", a.street_name);
    println!("warnings      {:?}", a.diagnostics.warnings);

    // Output forms. Only USPS (Pub 28) is a postal form; the display and
    // long forms are mixed case, for showing an address to a person.
    println!("usps          {:?}", a.to_usps().lines());
    println!("display       {:?}", a.to_display().lines());
    println!("long          {:?}", a.to_long().lines());
    println!("reso          {:?}", a.to_reso().fields());
    println!(
        "reso (word) {:?}",
        a.to_reso_with(doorplate::SuffixForm::Word).street_suffix
    );
    println!("key           {:?}", a.key(KeyOptions::property()));
    println!("slug          {:?}", a.slug());

    // Fields already split, one at a time and as a batch.
    let rows = vec![
        Fields {
            line1: Some("412 N HARBOR ST".into()),
            line2: Some("APT 3B".into()),
            city: Some("TAMPA".into()),
            state: Some("FL".into()),
            zip: Some("33602".into()),
        },
        Fields::default(), // no address text: an error for this row only
    ];
    for (i, r) in parser.parse_fields_many(&rows).into_iter().enumerate() {
        match r {
            Ok(a) => println!("row {i}: {:?}", a.to_display().lines()),
            Err(e) => println!("row {i}: {e}"),
        }
    }

    // Options are built, not written as a struct literal, so a new option is not a break:
    // look cities up in Florida when the input names no state.
    let hinted = Parser::with_options(ParseOptions::new().default_state("FL"))?;
    let a = hinted.parse("100 Main St, Miami")?;
    println!("{:?} (state field: {:?})", a.to_display().lines(), a.state);

    // Puerto Rico: the urbanization is its own field, a line above the street in the
    // USPS form, and part of the key (it tells apart same-named streets in one ZIP).
    let a = parser.parse("CALLE LUNA 27 URB LAS PALMAS, SAN JUAN PR 00926")?;
    println!("urbanization  {:?}", a.urbanization);
    println!("usps          {:?}", a.to_usps().lines());
    println!("key           {:?}", a.key(KeyOptions::property()));

    // A batch of lines (parallel with the `rayon` feature).
    let lines = ["1 Main St, Miami FL", "PO Box 5, Tampa FL"];
    for a in parser.parse_many(&lines).into_iter().flatten() {
        println!("{:?}", a.to_long().lines());
    }
    Ok(())
}
