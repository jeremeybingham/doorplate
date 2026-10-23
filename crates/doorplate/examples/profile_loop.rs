//! A single-thread parse loop for profiling (#90): `cargo run --release -p doorplate --example profile_loop -- FILE [REPS]`.
//!
//! FILE holds one input per line. Every line is parsed REPS times (default 20) and the best of
//! five passes is printed as addresses per second. Run it under `perf record -e cpu-clock` to see
//! where the time goes (`benchmarks/profile_fold.py` folds the output into tables).

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::hint::black_box;
use std::time::Instant;

use doorplate::Parser;

fn main() {
    let mut args = std::env::args().skip(1);
    let path = args.next().expect("usage: profile_loop FILE [REPS]");
    let reps: usize = args
        .next()
        .map_or(20, |r| r.parse().expect("REPS is a number"));
    let text = std::fs::read_to_string(&path).expect("readable file");
    let lines: Vec<&str> = text.lines().filter(|l| !l.is_empty()).collect();
    let parser = Parser::new();
    let mut best = f64::MAX;
    for _ in 0..5 {
        let t = Instant::now();
        for _ in 0..reps {
            for l in &lines {
                black_box(parser.parse(black_box(l)).ok());
            }
        }
        best = best.min(t.elapsed().as_secs_f64());
    }
    let n = (lines.len() * reps) as f64;
    println!(
        "{} lines x {reps}: {:.0} addresses/s, {:.2} us each (best of 5)",
        lines.len(),
        n / best,
        best / n * 1e6
    );
}
