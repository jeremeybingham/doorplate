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

use doorplate::{ParsedAddress, Parser};
use serde_json::{json, Value};

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

fn spans(a: &ParsedAddress) -> Vec<Value> {
    let text = &a.source.original;
    a.source
        .spans
        .iter()
        .map(|c| {
            json!({
                "component": format!("{:?}", c.component),
                "start": utf16(text, c.span.start),
                "end": utf16(text, c.span.end),
            })
        })
        .collect()
}

fn run(input: &str) -> String {
    let v = match PARSER.with(|p| p.parse(input)) {
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
    let out = run(&String::from_utf8_lossy(bytes));
    RESULT.with(|r| {
        let mut r = r.borrow_mut();
        *r = out.into_bytes();
        r.len()
    })
}

#[no_mangle]
pub extern "C" fn result_ptr() -> *const u8 {
    RESULT.with(|r| r.borrow().as_ptr())
}
