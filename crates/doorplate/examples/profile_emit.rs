//! What the emitters cost on top of `parse` (#703 G8): `cargo run --release -p doorplate --example profile_emit -- MODE FILE [REPS]`.
//!
//! MODE is `parse`, `key`, `usps`, `reso`, `display` or `usaddress`. Each line is parsed REPS times
//! (default 1) and the chosen output is built from the result. Run it under callgrind once per
//! mode and subtract the `parse` run to get the emitter's own instructions.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::hint::black_box;

use doorplate::{KeyOptions, Parser};

fn main() {
    let mut args = std::env::args().skip(1);
    let mode = args.next().expect("usage: profile_emit MODE FILE [REPS]");
    let path = args.next().expect("usage: profile_emit MODE FILE [REPS]");
    let reps: usize = args
        .next()
        .map_or(1, |r| r.parse().expect("REPS is a number"));
    let text = std::fs::read_to_string(&path).expect("readable file");
    let lines: Vec<&str> = text.lines().filter(|l| !l.is_empty()).collect();
    let parser = Parser::new();
    for _ in 0..reps {
        for l in &lines {
            let Ok(p) = parser.parse(black_box(l)) else {
                continue;
            };
            match mode.as_str() {
                "parse" => {}
                "key" => drop(black_box(p.key(KeyOptions::default()))),
                "usps" => drop(black_box(p.to_usps())),
                "reso" => drop(black_box(p.to_reso())),
                "display" => drop(black_box(p.to_display())),
                "usaddress" => drop(black_box(p.to_usaddress_tags())),
                _ => panic!("unknown mode"),
            }
            black_box(&p);
        }
    }
}
