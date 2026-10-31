//! # doorplate
//!
//! Pure-Rust US address parsing and normalization.
//!
//! This crate **parses and formats** addresses. It does **not** validate
//! deliverability; that requires CASS-certified data.
//!
//! ```
//! let a = doorplate::Parser::new()
//!     .parse("123 N Main St Apt 4, Miami, FL 33101")
//!     .unwrap();
//! assert_eq!(a.street_name.as_deref(), Some("MAIN"));
//! assert_eq!(a.street_suffix.map(|s| s.abbr()), Some("ST"));
//! assert_eq!(a.city.as_deref(), Some("MIAMI"));
//! ```
//!
//! Emitters: [`ParsedAddress::to_usps`], [`ParsedAddress::to_reso`],
//! [`ParsedAddress::key`], [`ParsedAddress::slug`] and
//! [`ParsedAddress::to_usaddress_tags`].
//!
//! To share a messy address without sharing its names and numbers, [`Anonymizer`] rewrites
//! address-like text and keeps its shape (obfuscation, not anonymity: read the output before you
//! share it).

mod anonymize;
mod assemble;
mod classify;
mod clean;
#[cfg(feature = "corpus")]
pub mod corpus;
mod country;
mod emit;
mod input;
mod intersection;
mod layer;
pub mod lexicon;
mod parser;
mod place;
#[cfg(feature = "rule-stats")]
#[doc(hidden)]
pub mod rulestats;
mod tagger;
mod tokenize;
mod types;

pub use anonymize::{Anonymized, Anonymizer};
pub use emit::{
    AddressType, DisplayAddress, KeyOptions, ResoAddress, TaggedAddress, UsaddressTag, UspsAddress,
};
pub use input::Fields;
pub use layer::{CustomLayer, LayerInfo};
#[cfg(feature = "custom-layer")]
pub use layer::{LayerError, LayerSources};
pub use lexicon::{HighwayPrefix, Lexicons, Lookup, MatchKind, ZipPlaces};
pub use parser::{OptionsError, ParseError, ParseOptions, Parser};
pub use types::{
    Component, ComponentSpan, Diagnostics, Directional, FieldName, Highway, InputKind, MilitaryBox,
    MilitaryKind, MilitaryPostOffice, ParsedAddress, Place, PlaceKind, PlaceMatch, PlaceSource,
    RouteKind, RuralRoute, SourceInfo, Span, StateCode, StateKind, StreetSuffix, UnitType, Warning,
};

/// Library version, surfaced in [`Diagnostics`].
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
