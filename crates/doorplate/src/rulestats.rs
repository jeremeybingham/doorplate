//! Rule firing counts (#401), behind the `rule-stats` feature (off by default; not part of the
//! public API). Every call of the tagger's `set`, `warn` and `decide` is recorded with the file
//! and line of its caller (`#[track_caller]`), and the tokenizer's passes by name, so a report
//! says which rules fire, how often, and in how many inputs. Counts only; no text is kept.

use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use std::panic::Location;
use std::sync::OnceLock;

#[derive(Default)]
struct Stats {
    /// (kind, site, label) to (fires, inputs it fired in).
    rows: BTreeMap<(String, String, String), (u64, u64)>,
    /// The sites that fired in the parse in progress.
    seen: BTreeSet<(String, String, String)>,
    parses: u64,
}

thread_local! {
    static STATS: RefCell<Stats> = RefCell::new(Stats::default());
}

/// One row of the report.
#[derive(Debug, Clone)]
pub struct Row {
    /// `set`, `warn`, `decide` (tagger) or `tok` (tokenizer).
    pub kind: String,
    /// `file:line` of the call, or the name of the tokenizer rule.
    pub site: String,
    /// The tag, warning or decision recorded there.
    pub label: String,
    pub fires: u64,
    pub inputs: u64,
}

fn record(kind: &str, site: String, label: String) {
    STATS.with(|s| {
        let mut s = s.borrow_mut();
        let key = (kind.to_string(), site, label);
        s.rows.entry(key.clone()).or_default().0 += 1;
        s.seen.insert(key);
    });
}

pub(crate) fn at(kind: &str, loc: &Location<'_>, label: String) {
    let file = loc.file().rsplit('/').next().unwrap_or("");
    record(kind, format!("{file}:{}", loc.line()), label);
}

pub(crate) fn named(name: &str) {
    record("tok", name.to_string(), String::new());
}

/// Call after each parse: counts it, and counts the inputs each site fired in.
pub fn end_parse() {
    STATS.with(|s| {
        let mut s = s.borrow_mut();
        s.parses += 1;
        let seen = std::mem::take(&mut s.seen);
        for k in seen {
            s.rows.entry(k).or_default().1 += 1;
        }
    });
}

/// The rows and the number of parses so far on this thread, then reset.
pub fn take() -> (Vec<Row>, u64) {
    STATS.with(|s| {
        let s = std::mem::take(&mut *s.borrow_mut());
        let rows = s
            .rows
            .into_iter()
            .map(|((kind, site, label), (fires, inputs))| Row {
                kind,
                site,
                label,
                fires,
                inputs,
            })
            .collect();
        (rows, s.parses)
    })
}

/// Whether the call at `loc` is switched off by the environment variable `DOORPLATE_DISABLE`
/// (`file:line` entries separated by commas, as in the report): the call then does nothing. For the
/// deletion check of a rule (#401): no rebuild per site.
pub(crate) fn disabled(loc: &Location<'_>) -> bool {
    static OFF: OnceLock<Vec<String>> = OnceLock::new();
    let off = OFF.get_or_init(|| {
        std::env::var("DOORPLATE_DISABLE")
            .map(|v| v.split(',').map(|s| s.trim().to_string()).collect())
            .unwrap_or_default()
    });
    if off.is_empty() {
        return false;
    }
    let file = loc.file().rsplit('/').next().unwrap_or("");
    let site = format!("{file}:{}", loc.line());
    off.contains(&site)
}
