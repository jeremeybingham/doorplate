//! Rule firing counts (#401): `cargo run --release -p doorplate --features rule-stats --example rule_stats -- FILE`.
//!
//! FILE holds one input per line: a one-line address, or five tab-separated fields (line 1, line 2,
//! city, state, ZIP; empty for none) for `parse_fields`. Prints, as tab-separated text, one row per rule (a tagger call
//! site or a tokenizer rule) that fired: kind, site, label, fires, inputs it fired in. Counts only.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use doorplate::{rulestats, Fields, Parser};

fn main() {
    let path = std::env::args().nth(1).expect("usage: rule_stats FILE");
    let text = std::fs::read_to_string(&path).expect("readable file");
    let parser = Parser::new();
    for line in text.lines().filter(|l| !l.is_empty()) {
        if line.contains('\t') {
            let f: Vec<&str> = line.split('\t').collect();
            let get = |i: usize| f.get(i).filter(|s| !s.is_empty()).map(|s| (*s).to_string());
            let fields = Fields {
                line1: get(0),
                line2: get(1),
                city: get(2),
                state: get(3),
                zip: get(4),
            };
            let _ = parser.parse_fields(&fields);
        } else {
            let _ = parser.parse(line);
        }
        rulestats::end_parse();
    }
    let (rows, parses) = rulestats::take();
    println!("# parses\t{parses}");
    for r in rows {
        println!(
            "{}\t{}\t{}\t{}\t{}",
            r.kind, r.site, r.label, r.fires, r.inputs
        );
    }
}
