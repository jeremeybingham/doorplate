//! doorplate for the browser: one function, `parse`, that takes an address
//! as UTF-8 and leaves a JSON string in a buffer the page reads back.
//!
//! No `wasm-bindgen`: the page needs only four exports (`alloc`, `dealloc`,
//! `parse`, `result_ptr`) and a few lines of JavaScript, so the build is
//! `cargo build --target wasm32-unknown-unknown` and nothing else.
//!
//! The JSON is the command-line tool's record (`json::record`, so the demo
//! cannot disagree with `doorplate parse`) plus `spans`: each component's
//! range in the input, in UTF-16 units, which is how JavaScript indexes a
//! string.

use std::cell::RefCell;

use doorplate::{FieldName, Fields, ParseError, ParsedAddress, Parser};
use serde_json::{json, Value};

// The command-line tool's JSON builder, compiled in as is (it needs only
// `doorplate` and `serde_json`), so the demo and `doorplate parse` print the
// same record from one source file. The tool's other views go unused here.
#[allow(dead_code)]
#[path = "../../doorplate-cli/src/json.rs"]
mod json;

thread_local! {
    static PARSER: Parser = Parser::new();
    static RESULT: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
}

/// The offset of byte `i` of `s` counted in UTF-16 units.
fn utf16(s: &str, i: usize) -> usize {
    s.get(..i).map_or(0, |p| p.encode_utf16().count())
}

fn field_name(f: Option<FieldName>) -> Value {
    match f {
        None => Value::Null,
        Some(FieldName::Line1) => json!("line1"),
        Some(FieldName::Line2) => json!("line2"),
        Some(FieldName::City) => json!("city"),
        Some(FieldName::State) => json!("state"),
        Some(FieldName::Zip) => json!("zip"),
    }
}

/// Each component's range, in UTF-16 units of the text it indexes: the input
/// for one line, or the named field for `parse_fields` (`field` says which).
fn spans(a: &ParsedAddress) -> Vec<Value> {
    a.source
        .spans
        .iter()
        .map(|c| {
            let text = match c.span.field {
                None => a.source.original.as_str(),
                Some(f) => a
                    .source
                    .fields
                    .as_ref()
                    .and_then(|x| x.get(f))
                    .unwrap_or_default(),
            };
            json!({
                "component": format!("{:?}", c.component),
                "field": field_name(c.span.field),
                "start": utf16(text, c.span.start),
                "end": utf16(text, c.span.end),
            })
        })
        .collect()
}

fn record(result: Result<ParsedAddress, ParseError>, input: &str) -> String {
    let v = match result {
        Ok(a) => {
            let mut v = json::record(&a);
            if let Value::Object(m) = &mut v {
                m.insert("spans".into(), Value::Array(spans(&a)));
            }
            v
        }
        Err(e) => json!({ "input": input, "error": e.to_string() }),
    };
    v.to_string()
}

fn run(input: &str) -> String {
    record(PARSER.with(|p| p.parse(input)), input)
}

/// `{"line1": ..., "line2": ..., "city": ..., "state": ..., "zip": ...}`, any
/// of them missing or null, as `Parser::parse_fields` takes them.
fn run_fields(json_text: &str) -> String {
    let Ok(Value::Object(m)) = serde_json::from_str::<Value>(json_text) else {
        return json!({ "input": "", "error": "fields must be a JSON object" }).to_string();
    };
    let get = |k: &str| m.get(k).and_then(Value::as_str).map(str::to_string);
    let fields = Fields {
        line1: get("line1"),
        line2: get("line2"),
        city: get("city"),
        state: get("state"),
        zip: get("zip"),
    };
    record(PARSER.with(|p| p.parse_fields(&fields)), "")
}

fn store(out: String) -> usize {
    RESULT.with(|r| {
        let mut r = r.borrow_mut();
        *r = out.into_bytes();
        r.len()
    })
}

/// Reserve `len` bytes for the page to write its input into.
#[no_mangle]
pub extern "C" fn alloc(len: usize) -> *mut u8 {
    let mut v = Vec::<u8>::with_capacity(len);
    let p = v.as_mut_ptr();
    std::mem::forget(v);
    p
}

/// Free a buffer from [`alloc`] (`len` as it was reserved).
///
/// # Safety
/// `ptr` must come from `alloc(len)` and not be used afterwards.
#[no_mangle]
pub unsafe extern "C" fn dealloc(ptr: *mut u8, len: usize) {
    drop(Vec::from_raw_parts(ptr, 0, len));
}

/// Parse the `len` bytes at `ptr` (UTF-8). Returns the length of the JSON,
/// which is at [`result_ptr`] until the next call.
///
/// # Safety
/// `ptr` must point to `len` initialized bytes.
#[no_mangle]
pub unsafe extern "C" fn parse(ptr: *const u8, len: usize) -> usize {
    let bytes = std::slice::from_raw_parts(ptr, len);
    store(run(&String::from_utf8_lossy(bytes)))
}

/// Like [`parse`], for pre-split fields given as a JSON object (UTF-8).
///
/// # Safety
/// `ptr` must point to `len` initialized bytes.
#[no_mangle]
pub unsafe extern "C" fn parse_fields(ptr: *const u8, len: usize) -> usize {
    let bytes = std::slice::from_raw_parts(ptr, len);
    store(run_fields(&String::from_utf8_lossy(bytes)))
}

#[no_mangle]
pub extern "C" fn result_ptr() -> *const u8 {
    RESULT.with(|r| r.borrow().as_ptr())
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::indexing_slicing)]
mod tests {
    use super::*;

    fn parsed(input: &str) -> Value {
        serde_json::from_str(&run(input)).unwrap()
    }

    /// The text each span covers, by component, read back with JavaScript's
    /// indexing (UTF-16 units).
    fn covered(input: &str, v: &Value) -> Vec<(String, String)> {
        let units: Vec<u16> = input.encode_utf16().collect();
        v["spans"]
            .as_array()
            .unwrap()
            .iter()
            .map(|s| {
                let (a, b) = (s["start"].as_u64().unwrap(), s["end"].as_u64().unwrap());
                (
                    s["component"].as_str().unwrap().to_string(),
                    String::from_utf16(&units[a as usize..b as usize]).unwrap(),
                )
            })
            .collect()
    }

    #[test]
    fn record_plus_spans() {
        let input = "123 north main street apt 4, Miami FL 33101";
        let v = parsed(input);
        assert_eq!(v["key"], "k2:S|123|N|MAIN|ST||FL|33101");
        assert_eq!(v["usps"]["line1"], "123 N MAIN ST APT 4");
        let got = covered(input, &v);
        assert!(got.contains(&("StreetName".into(), "main".into())));
        assert!(got.contains(&("UnitNumber".into(), "4".into())));
        assert!(got.contains(&("Zip5".into(), "33101".into())));
    }

    #[test]
    fn same_record_as_the_command_line() {
        let input = "21-77 31ST ST, FLUSHING NY 11354";
        let mut v = parsed(input);
        v.as_object_mut().unwrap().remove("spans");
        let a = Parser::new().parse(input).unwrap();
        assert_eq!(v, json::record(&a));
    }

    #[test]
    fn offsets_count_utf16_units_not_bytes() {
        // `É` is two bytes and one unit; the emoji is four bytes and two units.
        let input = "😀 12 CAFÉ ST, ZÜRICH NY 11354";
        let v = parsed(input);
        let got = covered(input, &v);
        // How the parser reads the emoji is not the point; every span after
        // it must still land on the right text.
        assert!(
            got.contains(&("StreetSuffix".into(), "ST".into())),
            "{got:?}"
        );
        assert!(got.contains(&("City".into(), "ZÜRICH".into())), "{got:?}");
        assert!(got.contains(&("Zip5".into(), "11354".into())), "{got:?}");
    }

    #[test]
    fn fields_spans_index_their_own_field() {
        let fields = r#"{"line1": "123 N MAIN ST", "line2": "% JOHN SMITH", "city": "MIAMI", "state": "FL", "zip": "33101"}"#;
        let v: Value = serde_json::from_str(&run_fields(fields)).unwrap();
        assert_eq!(v["key"], "k2:S|123|N|MAIN|ST||FL|33101");
        let by_field = |f: &str, c: &str| {
            v["spans"]
                .as_array()
                .unwrap()
                .iter()
                .find(|s| s["field"] == f && s["component"] == c)
                .cloned()
        };
        let att = by_field("line2", "Attention").unwrap();
        assert_eq!(
            (att["start"].as_u64(), att["end"].as_u64()),
            (Some(0), Some(12))
        );
        let city = by_field("city", "City").unwrap();
        assert_eq!(
            (city["start"].as_u64(), city["end"].as_u64()),
            (Some(0), Some(5))
        );
        assert!(by_field("line1", "StreetName").is_some());
    }

    #[test]
    fn fields_accept_missing_and_null_and_reject_non_objects() {
        let v: Value =
            serde_json::from_str(&run_fields(r#"{"line1": "1 A ST", "city": null}"#)).unwrap();
        assert!(v.get("error").is_none());
        let v: Value = serde_json::from_str(&run_fields("[1]")).unwrap();
        assert_eq!(v["error"], "fields must be a JSON object");
        let v: Value = serde_json::from_str(&run_fields("{}")).unwrap();
        assert_eq!(v["error"], "address input is empty");
    }

    #[test]
    fn empty_input_is_an_error_record() {
        let v = parsed("");
        assert_eq!(v["error"], "address input is empty");
        assert!(v.get("spans").is_none());
    }
}
