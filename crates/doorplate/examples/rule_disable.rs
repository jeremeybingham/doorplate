//! The deletion check of a rule (#401): `DOORPLATE_DISABLE=rules.rs:179 cargo run --release -p doorplate
//! --features rule-stats,corpus --example rule_disable -- [INPUTS]`.
//!
//! With `DOORPLATE_DISABLE` naming tagger call sites (`file:line`, comma-separated, as the rule-stats
//! report prints them), those calls do nothing. Prints the golden-corpus cases that pass in
//! `tests/corpus/passing.txt` and now fail, then, for each line of INPUTS (a one-line address, or five
//! tab-separated fields), the key, the warning codes and the unparsed text, tab-separated, so two runs
//! can be compared with `diff`.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::path::Path;

use doorplate::{corpus, Fields, KeyOptions, Parser};

fn main() {
    let parser = Parser::new();
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/corpus");
    let report = corpus::load(&dir)
        .unwrap_or_else(|e| panic!("malformed corpus:\n  {}", e.join("\n  ")))
        .run(&parser);
    let cmp = report.compare(&corpus::read_baseline(&dir));
    let mut regressed = cmp.regressed.clone();
    regressed.sort();
    println!("# regressed\t{}\t{}", regressed.len(), regressed.join(" "));
    let Some(path) = std::env::args().nth(1) else {
        return;
    };
    let text = std::fs::read_to_string(path).expect("readable file");
    for line in text.lines().filter(|l| !l.is_empty()) {
        let parsed = if line.contains('\t') {
            let f: Vec<&str> = line.split('\t').collect();
            let get = |i: usize| f.get(i).filter(|s| !s.is_empty()).map(|s| (*s).to_string());
            parser.parse_fields(&Fields {
                line1: get(0),
                line2: get(1),
                city: get(2),
                state: get(3),
                zip: get(4),
            })
        } else {
            parser.parse(line)
        };
        match parsed {
            Ok(a) => {
                let warns: Vec<String> = a
                    .diagnostics
                    .warnings
                    .iter()
                    .map(|w| format!("{w:?}"))
                    .collect();
                println!(
                    "{}\t{}\t{}",
                    a.key(KeyOptions::default()).unwrap_or_default(),
                    warns.join("|"),
                    a.diagnostics.unparsed.clone().unwrap_or_default()
                );
            }
            Err(_) => println!("error"),
        }
    }
}
