//! JSON and flat-column views of a [`ParsedAddress`]. Read-only: the CLI
//! formats what the parser produced and never re-parses it.

use doorplate::{Highway, KeyOptions, ParsedAddress, PlaceKind, UsaddressTag};
use serde::ser::{SerializeMap, Serializer};
use serde::Serialize;
use serde_json::{json, Value};

/// Parsed components, by `ParsedAddress` field name. Components the parse
/// did not find are left out.
fn components(a: &ParsedAddress) -> Vec<(&'static str, String)> {
    let mut m = Vec::with_capacity(12);
    let mut put = |k: &'static str, v: Option<String>| {
        if let Some(v) = v {
            m.push((k, v));
        }
    };
    put("street_number", a.street_number.clone());
    put(
        "street_dir_prefix",
        a.street_dir_prefix.map(|d| d.abbr().into()),
    );
    put("street_name", a.street_name.clone());
    put("street_suffix", a.street_suffix.map(|s| s.abbr().into()));
    put(
        "street_dir_suffix",
        a.street_dir_suffix.map(|d| d.abbr().into()),
    );
    put("highway", a.highway.as_ref().map(Highway::name));
    put("unit_type", a.unit_type.map(|u| u.abbr().into()));
    put("unit_number", a.unit_number.clone());
    put(
        "second_unit_type",
        a.second_unit_type.map(|u| u.abbr().into()),
    );
    put("second_unit_number", a.second_unit_number.clone());
    put("po_box", a.po_box.clone());
    put(
        "rural_route",
        a.rural_route.as_ref().map(|r| {
            let b = r
                .box_number
                .as_deref()
                .map_or(String::new(), |b| format!(" BOX {b}"));
            format!("{} {}{b}", r.kind.abbr(), r.route)
        }),
    );
    put(
        "general_delivery",
        a.general_delivery.then(|| "GENERAL DELIVERY".into()),
    );
    put(
        "military",
        a.military.as_ref().map(|m| {
            let b = m
                .box_number
                .as_deref()
                .map_or(String::new(), |b| format!(" BOX {b}"));
            format!("{} {}{b}", m.kind.abbr(), m.number)
        }),
    );
    put(
        "military_post_office",
        a.military_post_office.map(|m| m.abbr().into()),
    );
    put("attention", a.attention.clone());
    put("building", a.building.clone());
    put("city", a.city.clone());
    put("state", a.state.map(|s| s.to_string()));
    put("zip5", a.zip5.clone());
    put("zip4", a.zip4.clone());
    m
}

fn warning_codes(a: &ParsedAddress) -> Vec<&'static str> {
    a.diagnostics.warnings.iter().map(|w| w.code()).collect()
}

/// The full record printed by `doorplate parse`. It serializes straight to the
/// writer: no `Value` tree is built (the tree was about half of the CLI's cost).
pub struct Record<'a>(pub &'a ParsedAddress);

pub fn record(a: &ParsedAddress) -> Record<'_> {
    Record(a)
}

/// A map written from pairs, in order.
struct Pairs<'a>(&'a [(&'static str, String)]);

impl Serialize for Pairs<'_> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut m = s.serialize_map(Some(self.0.len()))?;
        for (k, v) in self.0 {
            m.serialize_entry(k, v)?;
        }
        m.end()
    }
}

struct PlaceJson<'a>(&'a doorplate::PlaceMatch);

impl Serialize for PlaceJson<'_> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let m = self.0;
        let mut o = s.serialize_map(Some(5))?;
        o.serialize_entry("name", m.place.name())?;
        o.serialize_entry("state", &m.place.state())?;
        o.serialize_entry("county", &m.place.county())?;
        o.serialize_entry(
            "kind",
            match m.place.kind() {
                PlaceKind::Municipality => "municipality",
                PlaceKind::Place => "place",
                PlaceKind::Subdivision => "subdivision",
                // A kind added later reads as the generic one until it has a name here.
                _ => "place",
            },
        )?;
        o.serialize_entry("source", &m.source.code())?;
        o.end()
    }
}

impl Serialize for Record<'_> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let a = self.0;
        let usps = a.to_usps();
        let reso = a.to_reso().fields();
        let mut m = s.serialize_map(Some(11))?;
        m.serialize_entry("input", &a.source.original)?;
        m.serialize_entry("components", &Pairs(&components(a)))?;
        m.serialize_entry("warnings", &warning_codes(a))?;
        m.serialize_entry("unparsed", &a.diagnostics.unparsed)?;
        m.serialize_entry("key", &a.key(KeyOptions::property()))?;
        m.serialize_entry("key_unit", &a.key(KeyOptions::unit()))?;
        m.serialize_entry("slug", &a.slug())?;
        m.serialize_entry(
            "usps",
            &UspsJson {
                line1: &usps.line1,
                line2: &usps.line2,
                last_line: usps.last_line(),
            },
        )?;
        m.serialize_entry("reso", &Pairs(&reso))?;
        m.serialize_entry("place", &a.place.as_ref().map(PlaceJson))?;
        // Which release, which state data and which custom layer (#3) produced this
        // record. A group, not bare keys.
        m.serialize_entry(
            "provenance",
            &ProvenanceJson {
                library_version: a.diagnostics.library_version,
                state_data_version: a.diagnostics.state_data_version,
                custom_layer: a.diagnostics.custom_layer.as_ref(),
            },
        )?;
        m.end()
    }
}

struct UspsJson<'a> {
    line1: &'a Option<String>,
    line2: &'a Option<String>,
    last_line: String,
}

impl Serialize for UspsJson<'_> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut m = s.serialize_map(Some(3))?;
        m.serialize_entry("line1", self.line1)?;
        m.serialize_entry("line2", self.line2)?;
        m.serialize_entry("last_line", &self.last_line)?;
        m.end()
    }
}

struct ProvenanceJson<'a> {
    library_version: &'a str,
    state_data_version: Option<&'a str>,
    custom_layer: Option<&'a doorplate::LayerInfo>,
}

impl Serialize for ProvenanceJson<'_> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut m = s.serialize_map(Some(3))?;
        m.serialize_entry("library_version", self.library_version)?;
        m.serialize_entry("state_data_version", &self.state_data_version)?;
        m.serialize_entry(
            "custom_layer",
            &self.custom_layer.map(|l| LayerJson {
                name: l.name,
                version: l.version,
                fingerprint: l.fingerprint,
            }),
        )?;
        m.end()
    }
}

struct LayerJson<'a> {
    name: &'a str,
    version: &'a str,
    fingerprint: &'a str,
}

impl Serialize for LayerJson<'_> {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut m = s.serialize_map(Some(3))?;
        m.serialize_entry("name", self.name)?;
        m.serialize_entry("version", self.version)?;
        m.serialize_entry("fingerprint", self.fingerprint)?;
        m.end()
    }
}

/// The record printed by `doorplate parse --usaddress`: each token as
/// `[text, label or null, start, end]`, with byte offsets into its field (or
/// the input, for one line).
pub fn usaddress_record(input: &str, tags: &[UsaddressTag]) -> Value {
    let tags: Vec<Value> = tags
        .iter()
        .map(|t| json!([t.text, t.label, t.span.start, t.span.end]))
        .collect();
    json!({ "input": input, "tags": tags })
}

/// The record printed by `doorplate parse --tag`: the parse joined by usaddress
/// label (`tag()`), the address type, and usaddress's own type name.
/// `None` is an input with no usable text.
pub fn tag_record(input: &str, a: Option<&ParsedAddress>) -> Value {
    let Some(a) = a else {
        return json!({ "input": input, "tag": null, "address_type": null,
            "usaddress_type": null, "repeated_labels": [] });
    };
    let t = a.tag();
    let comps: serde_json::Map<String, Value> = t
        .components()
        .iter()
        .map(|(l, v)| ((*l).to_string(), Value::String(v.clone())))
        .collect();
    json!({
        "input": input,
        "tag": comps,
        "address_type": t.address_type().code(),
        "usaddress_type": t.usaddress_type(),
        "repeated_labels": t.repeated_labels(),
    })
}

/// Columns `doorplate parse-file` appends, in order.
pub const COLUMNS: [&str; 30] = [
    "street_number",
    "street_dir_prefix",
    "street_name",
    "street_suffix",
    "street_dir_suffix",
    "unit_type",
    "unit_number",
    "second_unit_type",
    "second_unit_number",
    "city",
    "state",
    "zip5",
    "zip4",
    "place",
    "place_source",
    "highway",
    "po_box",
    "rural_route",
    "general_delivery",
    "military",
    "military_post_office",
    "attention",
    "building",
    "usps_line1",
    "usps_last_line",
    "key",
    "key_unit",
    "slug",
    "warnings",
    "unparsed",
];

/// One value per [`COLUMNS`] entry; empty when absent.
pub fn row(a: &ParsedAddress) -> Vec<String> {
    let c = components(a);
    let usps = a.to_usps();
    let get = |k: &str| {
        c.iter()
            .find(|(n, _)| *n == k)
            .map_or(String::new(), |(_, v)| v.clone())
    };
    COLUMNS
        .iter()
        .map(|&col| match col {
            "usps_line1" => usps.line1.clone().unwrap_or_default(),
            "usps_last_line" => usps.last_line(),
            "key" => a.key(KeyOptions::property()).unwrap_or_default(),
            "key_unit" => a.key(KeyOptions::unit()).unwrap_or_default(),
            "slug" => a.slug().unwrap_or_default(),
            "place" => a
                .place
                .map(|m| m.place.name().to_string())
                .unwrap_or_default(),
            "place_source" => a
                .place
                .map(|m| m.source.code().to_string())
                .unwrap_or_default(),
            "warnings" => warning_codes(a).join(";"),
            "unparsed" => a.diagnostics.unparsed.clone().unwrap_or_default(),
            other => get(other),
        })
        .collect()
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use doorplate::{Fields, Parser};

    /// Every component `components()` can print has a `parse-file` column.
    /// The inputs between them fill every component; extend them when a
    /// component is added.
    #[test]
    fn every_component_has_a_column() {
        let p = Parser::new();
        let mut parsed: Vec<ParsedAddress> = [
            "123 N MAIN ST E APT 4 PMB 9, MIAMI, FL 33101-1234",
            "100 HWY 66 FRONTAGE RD, TULSA OK 74101",
            "RR 2 BOX 152, AXTELL NE 68924",
            "GENERAL DELIVERY, JUNEAU AK 99801",
            "PSC 1650 BOX 10, APO AE 09001",
            "1679 E ORANGETHORPE AVE PO BOX 365, ATWOOD, CA 92811",
        ]
        .iter()
        .map(|s| p.parse(s).unwrap())
        .collect();
        for line2 in ["ANNEX BUILDING", "ATTN LAW DEPT"] {
            let f = Fields {
                line1: Some("323 NORRISTOWN ROAD".into()),
                line2: Some(line2.into()),
                city: Some("OCALA".into()),
                state: Some("FL".into()),
                zip: Some("34470".into()),
            };
            parsed.push(p.parse_fields(&f).unwrap());
        }
        let mut seen = std::collections::BTreeSet::new();
        for a in &parsed {
            for (k, _) in components(a) {
                assert!(COLUMNS.contains(&k), "no column for `{k}`");
                seen.insert(k);
            }
            assert_eq!(row(a).len(), COLUMNS.len());
        }
        assert_eq!(
            seen.len(),
            21,
            "inputs no longer cover every component: {seen:?}"
        );
    }

    #[test]
    fn second_unit_is_in_the_row() {
        let a = Parser::new().parse("123 MAIN ST STE 201 PMB 308").unwrap();
        let r = row(&a);
        let col = |n: &str| r[COLUMNS.iter().position(|c| *c == n).unwrap()].as_str();
        assert_eq!((col("unit_type"), col("unit_number")), ("STE", "201"));
        assert_eq!(
            (col("second_unit_type"), col("second_unit_number")),
            ("PMB", "308")
        );
    }
}
