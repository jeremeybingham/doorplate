//! Scratch: the full parse of every line of FILE, for a before/after comparison.
#![allow(clippy::unwrap_used, clippy::expect_used)]
use std::io::Write;
fn main() {
    let parser = doorplate::Parser::new();
    let out = std::io::stdout();
    let mut out = std::io::BufWriter::new(out.lock());
    for path in std::env::args().skip(1) {
        let text = std::fs::read_to_string(&path).expect("readable file");
        for l in text.lines() {
            writeln!(out, "{:?}", parser.parse(l)).ok();
        }
    }
}
