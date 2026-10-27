//! The custom layer (#3): loading, validation, what a layer changes, provenance.
//! Every spelling and address here is invented.
#![cfg(feature = "custom-layer")]
#![allow(clippy::unwrap_used, clippy::expect_used)]

use doorplate::{CustomLayer, LayerSources, ParseOptions, Parser};

const LAYER: &str = "name = \"test-layer\"\nversion = \"1\"\nnotes = \"tests\"\n";

fn layer(aliases: &str) -> CustomLayer {
    CustomLayer::from_sources(&LayerSources::new(LAYER).aliases(aliases)).expect("valid layer")
}

fn parser(l: CustomLayer) -> Parser {
    Parser::with_options(ParseOptions::new().custom_layer(l)).unwrap()
}

fn problems(sources: &LayerSources<'_>) -> Vec<String> {
    CustomLayer::from_sources(sources)
        .expect_err("should be rejected")
        .problems()
        .to_vec()
}

#[test]
fn a_suffix_spelling_changes_the_parse_and_the_key() {
    let l = layer(
        "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"TRAYL\"]\nevidence = \"seen in a county export\"\n",
    );
    let text = "123 Oak Trayl, Miami, FL 33101";
    let base = Parser::new().parse(text).unwrap();
    assert_eq!(
        base.street_suffix, None,
        "the base tables do not know TRAYL"
    );
    let a = parser(l).parse(text).unwrap();
    assert_eq!(a.street_name.as_deref(), Some("OAK"));
    assert_eq!(a.street_suffix.map(|s| s.abbr()), Some("TRL"));
    assert!(a
        .diagnostics
        .warnings
        .iter()
        .any(|w| w.code() == "non_standard_abbreviation"));
    assert_ne!(a.key(Default::default()), base.key(Default::default()));
    assert_eq!(a.to_usps().line1.as_deref(), Some("123 OAK TRL"));
}

#[test]
fn a_variant_spelling_raises_no_warning() {
    let l = layer(
        "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"TRAYL\"]\nkind = \"variant\"\nevidence = \"x\"\n",
    );
    let a = parser(l).parse("123 Oak Trayl, Miami, FL 33101").unwrap();
    assert!(!a
        .diagnostics
        .warnings
        .iter()
        .any(|w| w.code() == "non_standard_abbreviation"));
}

#[test]
fn unit_directional_state_special_and_highway_aliases() {
    let l = layer(
        r#"
[[unit]]
abbr = "STE"
spellings = ["SUTE"]
evidence = "x"
[[directional]]
abbr = "N"
spellings = ["NRTH"]
evidence = "x"
[[state]]
code = "FL"
spellings = ["FLORIDDA"]
evidence = "x"
[[special]]
form = "po_box"
spellings = ["POSTBX"]
evidence = "x"
[[highway]]
standard = "COUNTY ROAD"
spellings = ["CNTRY RD"]
evidence = "x"
"#,
    );
    let p = parser(l);
    let a = p
        .parse("12 Nrth Oak St Sute 4, Miami, Floridda 33101")
        .unwrap();
    assert_eq!(a.unit_type.map(|u| u.abbr()), Some("STE"));
    assert_eq!(a.street_dir_prefix.map(|d| d.abbr()), Some("N"));
    assert_eq!(a.state.map(|s| s.code()), Some("FL"));
    let b = p.parse("Postbx 12, Miami, FL 33101").unwrap();
    assert_eq!(b.po_box.as_deref(), Some("12"));
    let c = p.parse("100 Cntry Rd 12, Miami, FL 33101").unwrap();
    assert_eq!(
        c.highway.as_ref().map(|h| h.prefix.standard()),
        Some("COUNTY ROAD")
    );
}

#[test]
fn a_state_scoped_override_reads_a_base_spelling_differently_in_one_state() {
    let ov = "[[suffix]]\nstate = \"OH\"\nspelling = \"PL\"\nabbr = \"PLZ\"\nevidence = \"local usage\"\n";
    let l = CustomLayer::from_sources(&LayerSources::new(LAYER).overrides(ov)).unwrap();
    let p = parser(l);
    let oh = p.parse("100 Main Pl, Dayton, OH 45402").unwrap();
    assert_eq!(oh.street_suffix.map(|s| s.abbr()), Some("PLZ"));
    let tx = p.parse("100 Main Pl, Austin, TX 78701").unwrap();
    assert_eq!(tx.street_suffix.map(|s| s.abbr()), Some("PL"));
}

#[test]
fn a_word_list_addition_changes_the_parse() {
    let text = "4401 Main St, Tampa, FL 33601 Foobarland";
    let base = Parser::new().parse(text).unwrap();
    assert!(!base
        .diagnostics
        .warnings
        .iter()
        .any(|w| w.code() == "country_ignored"));
    let l = layer("[[words]]\nlist = \"country\"\nwords = [\"FOOBARLAND\"]\nevidence = \"x\"\n");
    let a = parser(l).parse(text).unwrap();
    assert!(a
        .diagnostics
        .warnings
        .iter()
        .any(|w| w.code() == "country_ignored"));
}

#[test]
fn provenance_names_the_layer_and_follows_the_content() {
    let a1 = "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"TRAYL\"]\nevidence = \"x\"\n";
    let a2 = "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"TRAYLL\"]\nevidence = \"x\"\n";
    let (l1, l1b, l2) = (layer(a1), layer(a1), layer(a2));
    let info = l1.info();
    assert_eq!((info.name, info.version), ("test-layer", "1"));
    assert_eq!(info.fingerprint.len(), 16);
    assert!(info.fingerprint.bytes().all(|b| b.is_ascii_hexdigit()));
    assert_eq!(l1, l1b, "the same content is the same layer");
    assert_ne!(l1, l2);
    let parsed = parser(l1).parse("1 Oak St, Miami, FL 33101").unwrap();
    assert_eq!(parsed.diagnostics.custom_layer, Some(info));
    assert_eq!(
        Parser::new()
            .parse("1 Oak St")
            .unwrap()
            .diagnostics
            .custom_layer,
        None
    );
}

#[test]
fn an_empty_layer_changes_nothing() {
    let l = CustomLayer::from_sources(&LayerSources::new(LAYER)).unwrap();
    let (p, q) = (parser(l), Parser::new());
    for t in [
        "123 N Main St Apt 4, Miami, FL 33101",
        "PO Box 12, Tampa FL 33601",
        "RR 2 Box 15, Dalton, GA 30720",
        "12 Oak Hollow County Road 7",
    ] {
        let (a, b) = (p.parse(t).unwrap(), q.parse(t).unwrap());
        assert_eq!(a.key(Default::default()), b.key(Default::default()), "{t}");
        assert_eq!(a.to_usps(), b.to_usps(), "{t}");
        assert_eq!(a.diagnostics.warnings, b.diagnostics.warnings, "{t}");
    }
}

#[test]
fn conflicts_with_the_shipped_tables_are_rejected() {
    let src = |a: &'static str| LayerSources::new(LAYER).aliases(a);
    let p = problems(&src(
        "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"ST\"]\nevidence = \"x\"\n",
    ));
    assert_eq!(p.len(), 1);
    assert!(
        p[0].contains("aliases.toml [[suffix]] #1")
            && p[0].contains("already in the shipped tables"),
        "{p:?}"
    );
    let p = problems(&src(
        "[[words]]\nlist = \"building\"\nwords = [\"TOWER\"]\nevidence = \"x\"\n",
    ));
    assert!(
        p[0].contains("already in the shipped `building` list"),
        "{p:?}"
    );
    // The shipped Florida data already reads SR as STATE ROAD.
    let ov = "[[highway]]\nstate = \"FL\"\nspelling = \"SR\"\nhighway = \"STATE ROUTE\"\nevidence = \"x\"\n";
    let p = problems(&LayerSources::new(LAYER).overrides(ov));
    assert!(p[0].contains("shipped FL data already reads"), "{p:?}");
}

#[test]
fn every_problem_is_listed_with_its_file_and_entry() {
    let aliases = r#"
[[suffix]]
abbr = "NOPE"
spellings = ["AAA"]
evidence = "x"
[[suffix]]
abbr = "TRL"
spellings = ["TRAYL", "TRAYL"]
[[unit]]
abbr = "STE"
spellings = ["SUTE"]
evidence = "x"
colour = "red"
[[words]]
list = "mystery"
words = ["X"]
evidence = "x"
"#;
    let p = problems(&LayerSources::new(LAYER).aliases(aliases));
    let joined = p.join("\n");
    assert!(
        joined.contains(
            "aliases.toml [[suffix]] #1: no street suffix with the abbreviation \"NOPE\""
        ),
        "{joined}"
    );
    assert!(
        joined.contains("aliases.toml [[suffix]] #2: needs `evidence` or `note`"),
        "{joined}"
    );
    assert!(
        joined.contains("#2: \"TRAYL\" is already added by another entry"),
        "{joined}"
    );
    assert!(
        joined.contains("aliases.toml [[unit]] #1: unknown key `colour`"),
        "{joined}"
    );
    assert!(
        joined.contains("aliases.toml [[words]] #1: `list` \"mystery\" is not one of"),
        "{joined}"
    );
    assert!(p.len() >= 5);
    let shown = CustomLayer::from_sources(&LayerSources::new(LAYER).aliases(aliases))
        .unwrap_err()
        .to_string();
    assert!(shown.starts_with("the custom layer has "), "{shown}");
}

#[test]
fn layer_toml_and_toml_syntax_are_checked() {
    let p = problems(&LayerSources::new("version = \"1\"\n"));
    assert!(p[0].contains("layer.toml: `name` is required"), "{p:?}");
    let p = problems(&LayerSources::new(
        "name = \"bad name!\"\nversion = \"1\"\n",
    ));
    assert!(p[0].contains("`name` must be 1 to 64 characters"), "{p:?}");
    let p = problems(&LayerSources::new(LAYER).aliases("[[suffix\n"));
    assert!(p[0].starts_with("aliases.toml: not valid TOML"), "{p:?}");
    let p = problems(&LayerSources::new(
        "name = \"x\"\nversion = \"1\"\ncolor = 1\n",
    ));
    assert!(p[0].contains("unknown key `color`"), "{p:?}");
}

#[test]
fn a_spelling_needs_letters_and_a_reasonable_length() {
    let p = problems(&LayerSources::new(LAYER).aliases(
        "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"--\", \"A B C D E F\"]\nevidence = \"x\"\n",
    ));
    assert!(
        p.iter().any(|m| m.contains("has no letters or digits")),
        "{p:?}"
    );
    assert!(p.iter().any(|m| m.contains("more than")), "{p:?}");
}

#[test]
fn a_state_scoped_highway_spelling_is_read_in_that_state_only() {
    // The example in docs/custom-layers.md.
    let ov = "[[highway]]\nstate = \"TX\"\nspelling = \"RM\"\nhighway = \"RANCH ROAD\"\nkind = \"variant\"\nevidence = \"x\"\n";
    let l = CustomLayer::from_sources(&LayerSources::new(LAYER).overrides(ov)).unwrap();
    let p = parser(l);
    let tx = p.parse("9100 RM 1960, Austin, TX 78701").unwrap();
    assert_eq!(
        tx.highway.as_ref().map(|h| h.prefix.standard()),
        Some("RANCH ROAD")
    );
    let oh = p.parse("9100 RM 1960, Dayton, OH 45402").unwrap();
    assert!(oh.highway.is_none());
}
