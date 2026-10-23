//! Allocations and bytes per parse, by input file (#90): `cargo run --release -p doorplate --example profile_alloc -- FILE...`.
//!
//! A counting global allocator (no dependency). Counts are deterministic, so unlike timings they
//! can gate a micro-optimization. Also prints `size_of::<ParsedAddress>()`. This example needs
//! `unsafe` for the allocator wrapper; the library itself has none.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic, unsafe_code)]

use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};

use doorplate::{ParsedAddress, Parser};

struct Counting;
static CALLS: AtomicUsize = AtomicUsize::new(0);
static BYTES: AtomicUsize = AtomicUsize::new(0);

// SAFETY: forwards every call to the system allocator and only counts.
unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        CALLS.fetch_add(1, Relaxed);
        BYTES.fetch_add(l.size(), Relaxed);
        System.alloc(l)
    }
    unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
        System.dealloc(p, l)
    }
    unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 {
        CALLS.fetch_add(1, Relaxed);
        BYTES.fetch_add(n.saturating_sub(l.size()), Relaxed);
        System.realloc(p, l, n)
    }
}

#[global_allocator]
static A: Counting = Counting;

fn main() {
    println!(
        "size_of::<ParsedAddress>() = {} bytes",
        std::mem::size_of::<ParsedAddress>()
    );
    let parser = Parser::new();
    for path in std::env::args().skip(1) {
        let text = std::fs::read_to_string(&path).expect("readable file");
        let lines: Vec<&str> = text.lines().filter(|l| !l.is_empty()).collect();
        let (c0, b0) = (CALLS.load(Relaxed), BYTES.load(Relaxed));
        let mut kept = 0usize;
        for l in &lines {
            kept += usize::from(parser.parse(l).is_ok());
        }
        let n = lines.len() as f64;
        println!(
            "{path}: {} lines ({kept} parsed): {:.1} allocations and {:.0} bytes per parse",
            lines.len(),
            (CALLS.load(Relaxed) - c0) as f64 / n,
            (BYTES.load(Relaxed) - b0) as f64 / n
        );
    }
}
