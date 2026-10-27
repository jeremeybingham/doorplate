//! The custom layer (#3): your own spellings and word lists on top of the shipped tables.
//!
//! A layer is add-only and deterministic. It maps extra *spellings* onto rows the shipped
//! tables already have (a suffix, a unit designator, a directional, a state, a special word, a
//! highway prefix), adds words to the tagger's word lists, and reads a spelling differently in
//! one state (the same shape as a state's `overrides.toml`). A spelling the shipped data
//! already has is a load error, except in the state-scoped overrides, whose job is to replace
//! a base reading. The tagger does not change: [`crate::Lexicons`] consults the layer after its
//! own tables.
//!
//! A layer can change a key. Parse with the same layer, or store the layer's fingerprint
//! ([`Diagnostics::custom_layer`](crate::Diagnostics::custom_layer)) with the keys.
//!
//! The core takes text; with the `custom-layer` feature, [`CustomLayer::from_sources`] reads
//! the files' contents. The files, and the guide to writing them, are in
//! `docs/custom-layers.md`. This library formats and parses; it does not validate that an
//! address exists or can receive mail.

use std::collections::{HashMap, HashSet};

use crate::lexicon::{HighwayPrefix, Lookup, Special};
use crate::types::StreetSuffix;
use crate::types::{StateCode, UnitType};
use crate::Directional;

#[cfg(feature = "custom-layer")]
mod load;
#[cfg(feature = "custom-layer")]
pub use load::{LayerError, LayerSources};

/// Which custom layer a parse used: its name, its version, and a fingerprint of its content
/// (FNV-1a 64 over the files' bytes, as 16 hex digits; it changes when any byte of the layer
/// changes, comments included). Stored with a key, it says which layer made the key.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub struct LayerInfo {
    pub name: &'static str,
    pub version: &'static str,
    pub fingerprint: &'static str,
}

/// A loaded custom layer. Cheap to copy; the data lives for the rest of the process (a layer is
/// loaded once, and loading the same content again returns the same data).
#[derive(Debug, Clone, Copy)]
pub struct CustomLayer(pub(crate) &'static Layer);

impl PartialEq for CustomLayer {
    fn eq(&self, other: &Self) -> bool {
        self.0.info.fingerprint == other.0.info.fingerprint
    }
}

impl Eq for CustomLayer {}

impl CustomLayer {
    /// The layer's name, version and fingerprint.
    pub fn info(&self) -> LayerInfo {
        self.0.info
    }
}

/// The data of a layer. Keys are normalized lexicon keys (`normalize_key`).
#[derive(Debug)]
pub(crate) struct Layer {
    pub(crate) info: LayerInfo,
    pub(crate) suffix: HashMap<String, Lookup<StreetSuffix>>,
    pub(crate) unit: HashMap<String, Lookup<UnitType>>,
    pub(crate) directional: HashMap<String, Lookup<Directional>>,
    pub(crate) state: HashMap<String, Lookup<StateCode>>,
    pub(crate) special: HashMap<String, Lookup<Special>>,
    pub(crate) highway: HashMap<String, Lookup<HighwayPrefix>>,
    /// `STATE|KEY` -> the suffix a spelling is read as in that state.
    pub(crate) state_suffix: HashMap<String, Lookup<StreetSuffix>>,
    /// `STATE|KEY` -> the highway prefix a spelling is read as in that state.
    pub(crate) state_highway: HashMap<String, Lookup<HighwayPrefix>>,
    pub(crate) words: WordLists,
}

/// The tagger's word lists a layer may add to (`data/special.toml`).
#[derive(Debug, Default)]
pub(crate) struct WordLists {
    pub(crate) building: HashSet<String>,
    pub(crate) area: HashSet<String>,
    pub(crate) city_head: HashSet<String>,
    pub(crate) non_recipient: HashSet<String>,
    pub(crate) numbered_street: HashSet<String>,
    pub(crate) placeholder: HashSet<String>,
    pub(crate) country: HashSet<String>,
    pub(crate) place_prefix: HashSet<String>,
}
