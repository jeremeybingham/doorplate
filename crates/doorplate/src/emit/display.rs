//! Display and long-form output. These are not Pub 28 forms: they are for
//! showing an address to a person, in mixed case. Rules are in
//! `docs/usps-pub28-notes.md`, section "Display emitter".
//!
//! This formats a parse; it does not check that the address exists or is
//! deliverable.

use super::usps::join;
use crate::types::{ParsedAddress, RouteKind, UnitType};

/// A mixed-case address for display: `123 N Main St Apt 4` (short) or
/// `123 North Main Street Apartment 4` (long). Not a Pub 28 form; use
/// [`UspsAddress`](crate::UspsAddress) for mail.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct DisplayAddress {
    /// Delivery line, with the unit at the end.
    pub line1: Option<String>,
    /// City in mixed case, or the military post office (`APO`).
    pub city: Option<String>,
    /// Two-letter state code.
    pub state: Option<String>,
    /// `NNNNN` or `NNNNN-NNNN`.
    pub zip: Option<String>,
}

impl DisplayAddress {
    /// `City ST ZIP`, with the missing parts left out.
    pub fn last_line(&self) -> String {
        join([&self.city, &self.state, &self.zip])
    }

    /// The non-empty lines: the delivery line, then the last line.
    pub fn lines(&self) -> Vec<String> {
        let last = self.last_line();
        [self.line1.clone().unwrap_or_default(), last]
            .into_iter()
            .filter(|l| !l.is_empty())
            .collect()
    }
}

impl ParsedAddress {
    /// The address in mixed case with Pub 28 abbreviations: `123 N Main St
    /// Apt 4`. Display only; not a Pub 28 form (see [`Self::to_usps`]).
    pub fn to_display(&self) -> DisplayAddress {
        self.display(false)
    }

    /// The address in mixed case with directionals, suffixes and unit
    /// designators spelled out: `123 North Main Street Apartment 4`. Display
    /// only; not a Pub 28 form.
    pub fn to_long(&self) -> DisplayAddress {
        self.display(true)
    }

    fn display(&self, long: bool) -> DisplayAddress {
        let units = if self.is_dual() {
            None
        } else {
            let u = join([
                &unit_text(self.unit_type, self.unit_number.as_deref(), long),
                &unit_text(
                    self.second_unit_type,
                    self.second_unit_number.as_deref(),
                    long,
                ),
            ]);
            (!u.is_empty()).then_some(u)
        };
        let primary = self
            .display_special(long)
            .or_else(|| self.display_street(long));
        let line1 = match (primary, units) {
            (p, None) => p,
            (None, u) => u,
            (Some(p), Some(u)) => Some(format!("{p} {u}")),
        };
        let zip = self.zip5.as_ref().map(|z5| match &self.zip4 {
            Some(z4) => format!("{z5}-{z4}"),
            None => z5.clone(),
        });
        DisplayAddress {
            line1,
            city: self
                .military_post_office
                .map(|p| p.abbr().to_string())
                .or_else(|| self.city.as_deref().map(title))
                .filter(|c| !c.is_empty()),
            state: self.state.map(|s| s.code().to_string()),
            zip,
        }
    }

    fn display_street(&self, long: bool) -> Option<String> {
        let dir = |d: crate::Directional| {
            if long {
                title(d.name())
            } else {
                d.abbr().to_string()
            }
        };
        let name = match (&self.highway, &self.street_name) {
            (Some(h), n) => {
                let hw = h.name();
                let mut words: Vec<String> = hw.split(' ').map(highway_word).collect();
                if let Some(n) = n {
                    words.push(title(n));
                }
                Some(words.join(" "))
            }
            (None, Some(n)) => Some(title(n)),
            (None, None) => None,
        };
        let line = join([
            &self.street_number.as_deref().map(title),
            &self.street_dir_prefix.map(dir),
            &name,
            &self
                .street_suffix
                .map(|s| title(if long { s.name() } else { s.abbr() })),
            &self.street_dir_suffix.map(dir),
        ]);
        (!line.is_empty()).then_some(line)
    }

    fn display_special(&self, long: bool) -> Option<String> {
        let with_box = |head: String, b: &Option<String>| match b {
            Some(b) => format!("{head} Box {}", title(b)),
            None => head,
        };
        if let Some(po) = &self.po_box {
            Some(format!("PO Box {}", title(po)))
        } else if let Some(r) = &self.rural_route {
            let kind = match (r.kind, long) {
                (RouteKind::Rural, true) => "Rural Route",
                (RouteKind::HighwayContract, true) => "Highway Contract Route",
                (k, false) => k.abbr(),
            };
            Some(with_box(
                format!("{kind} {}", title(&r.route)),
                &r.box_number,
            ))
        } else if let Some(m) = &self.military {
            let kind = match m.kind.abbr() {
                "UNIT" => "Unit",
                other => other,
            };
            Some(with_box(
                format!("{kind} {}", title(&m.number)),
                &m.box_number,
            ))
        } else if self.general_delivery {
            Some("General Delivery".to_string())
        } else {
            None
        }
    }
}

/// `Apt 4` or `Apartment 4`; `#4` when the designator is unknown; the
/// designator alone when there is no number.
fn unit_text(t: Option<UnitType>, number: Option<&str>, long: bool) -> Option<String> {
    let n = number.map(title).filter(|n| !n.is_empty());
    let name = |t: UnitType| title(if long { t.name() } else { t.abbr() });
    match (t, n) {
        (Some(t), Some(n)) => Some(format!("{} {n}", name(t))),
        (Some(t), None) => Some(name(t)),
        (None, Some(n)) => Some(format!("#{n}")),
        (None, None) => None,
    }
}

/// A word of a highway name: a state code or a one- or two-letter prefix
/// (`KY`, `US`, `FM`) stays upper case; a route (`625`, `60E`) is upper case;
/// the rest is title case.
fn highway_word(w: &str) -> String {
    if w.len() <= 2 || w.chars().any(|c| c.is_ascii_digit()) {
        w.to_uppercase()
    } else {
        title(w)
    }
}

/// Mixed case for display. Words are split on spaces; within a word:
/// hyphen- and slash-separated parts are cased alone (`Mid-Island`); a word
/// with a digit is upper case except an ordinal's suffix (`5th`, `23B`);
/// a leading `Mc` is kept (`McDonald`); `of`, `the`, `de`, `la`, `del` and
/// `and` are lower case unless first (`Via de la Valle`). Anything else is `Capitalized`. The
/// parse has already dropped apostrophes (`OBRIEN`), so `Obrien` is the best
/// this can do.
pub(super) fn title(s: &str) -> String {
    s.split_whitespace()
        .enumerate()
        .map(|(i, w)| match w.to_ascii_lowercase().as_str() {
            p @ ("of" | "the" | "de" | "la" | "del" | "and") if i > 0 => p.to_string(),
            _ => title_word(w),
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn title_word(w: &str) -> String {
    let mut out = String::with_capacity(w.len());
    let mut part = String::new();
    let flush = |part: &mut String, out: &mut String| {
        out.push_str(&title_part(part));
        part.clear();
    };
    for c in w.chars() {
        if c == '-' || c == '/' {
            flush(&mut part, &mut out);
            out.push(c);
        } else {
            part.push(c);
        }
    }
    flush(&mut part, &mut out);
    out
}

fn title_part(p: &str) -> String {
    if p.is_empty() {
        return String::new();
    }
    if p.chars().any(|c| c.is_ascii_digit()) {
        let upper = p.to_uppercase();
        let digits = upper.trim_end_matches(|c: char| c.is_ascii_alphabetic());
        let suffix = &upper[digits.len()..];
        return if !digits.is_empty()
            && matches!(suffix, "ST" | "ND" | "RD" | "TH")
            && digits.chars().all(|c| c.is_ascii_digit())
        {
            format!("{digits}{}", suffix.to_lowercase())
        } else {
            upper
        };
    }
    let upper = p.to_uppercase();
    if upper.chars().count() >= 4
        && upper.starts_with("MC")
        && upper.chars().all(char::is_alphabetic)
    {
        return format!("Mc{}", capitalize(&upper[2..]));
    }
    capitalize(p)
}

fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        Some(f) => f
            .to_uppercase()
            .chain(chars.flat_map(char::to_lowercase))
            .collect(),
        None => String::new(),
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::title;
    use crate::Parser;

    fn both(input: &str) -> (String, String, String) {
        let a = Parser::new().parse(input).unwrap();
        (
            a.to_display().line1.unwrap_or_default(),
            a.to_long().line1.unwrap_or_default(),
            a.to_display().last_line(),
        )
    }

    #[test]
    fn title_rules() {
        assert_eq!(title("MAIN"), "Main");
        assert_eq!(title("MID-ISLAND"), "Mid-Island");
        assert_eq!(title("5TH"), "5th");
        assert_eq!(title("101ST"), "101st");
        assert_eq!(title("23B"), "23B");
        assert_eq!(title("289-01"), "289-01");
        assert_eq!(title("1/2"), "1/2");
        assert_eq!(title("MCDONALD"), "McDonald");
        assert_eq!(title("MCA"), "Mca");
        assert_eq!(title("ST PETERSBURG"), "St Petersburg");
        assert_eq!(title("VIA DE LA VALLE"), "Via de la Valle");
        assert_eq!(title("THE STRAND"), "The Strand");
        assert_eq!(title("LA JOLLA"), "La Jolla");
        assert_eq!(title(""), "");
    }

    #[test]
    fn street_with_unit() {
        let (short, long, last) = both("123 north main street apt 4, miami fl 33101-1234");
        assert_eq!(short, "123 N Main St Apt 4");
        assert_eq!(long, "123 North Main Street Apartment 4");
        assert_eq!(last, "Miami FL 33101-1234");
    }

    #[test]
    fn ordinals_and_postdirectionals() {
        let (short, long, _) = both("100 NE 5th Ave SW, Tampa FL 33601");
        assert_eq!(short, "100 NE 5th Ave SW");
        assert_eq!(long, "100 Northeast 5th Avenue Southwest");
    }

    #[test]
    fn unknown_designator_uses_pound() {
        assert_eq!(both("4158 Inverrary Dr #309").0, "4158 Inverrary Dr #309");
    }

    #[test]
    fn special_forms() {
        assert_eq!(both("P.O. Box 12, Tampa FL 33601").0, "PO Box 12");
        assert_eq!(both("Star Route 68 Box 23A").0, "HC 68 Box 23A");
        assert_eq!(
            both("Star Route 68 Box 23A").1,
            "Highway Contract Route 68 Box 23A"
        );
        assert_eq!(both("RFD 2 Box 152").1, "Rural Route 2 Box 152");
        assert_eq!(
            both("General Delivery, Tampa FL 33601").0,
            "General Delivery"
        );
        assert_eq!(
            both("PSC 1650 Box 10, APO AE 09001"),
            (
                "PSC 1650 Box 10".into(),
                "PSC 1650 Box 10".into(),
                "APO AE 09001".into()
            )
        );
        assert_eq!(
            both("Unit 9900 Box 0500, DPO AE 09701").0,
            "Unit 9900 Box 0500"
        );
    }

    #[test]
    fn highways() {
        assert_eq!(
            both("100 Kentucky State Highway 625").0,
            "100 KY State Highway 625"
        );
        assert_eq!(both("US 41 SW").0, "US Highway 41 SW");
        assert_eq!(both("farm to market 1200").0, "FM 1200");
        assert_eq!(both("100 County Road 23E").0, "100 County Road 23E");
    }

    #[test]
    fn names_and_places() {
        assert_eq!(
            both("1 O'Brien St., St. Petersburg, FL 33701").0,
            "1 Obrien St"
        );
        assert_eq!(
            both("1 O'Brien St., St. Petersburg, FL 33701").2,
            "St Petersburg FL 33701"
        );
        assert_eq!(both("289-01 Mid-Island Plz").0, "289-01 Mid-Island Plz");
        assert_eq!(both("123 1/2 Main St").0, "123 1/2 Main St");
    }

    #[test]
    fn partial_addresses_leave_parts_out() {
        assert_eq!(both("Tampa FL 33601").0, "");
        assert_eq!(both("Tampa FL 33601").2, "Tampa FL 33601");
        let a = Parser::new().parse("123 Main St, Miami FL").unwrap();
        assert_eq!(a.to_display().lines(), ["123 Main St", "Miami FL"]);
    }

    #[test]
    fn dual_address_is_the_po_box_alone() {
        let a = Parser::new()
            .parse("9418 CUBA RD APT 2, PO BOX 100, HAYES VA 23072")
            .unwrap();
        assert_eq!(a.to_display().line1.as_deref(), Some("PO Box 100"));
    }
}
