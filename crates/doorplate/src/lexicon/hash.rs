// The hash behind the lexicon's open-addressing indexes (#703 G3, G4, G6). This file is compiled
// twice, like `key.rs`: into the crate as `lexicon::hash`, and into build.rs via `#[path]`, so the
// slot tables build.rs writes are probed with exactly the hash the runtime uses. Keep it
// dependency-free and free of `crate::` paths.

/// The FNV-1a hash of a key.
#[inline]
pub fn hash(key: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &c in key.as_bytes() {
        h = (h ^ u64::from(c)).wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// The first slot of a hash in a table of `mask + 1` slots.
#[inline]
pub fn slot_of(h: u64, mask: usize) -> usize {
    ((h >> 32) ^ h) as usize & mask
}

/// An open-addressing table over `keys`, at most half full: slot `s` holds the position of its key
/// plus one, 0 for empty. A lookup of a key that is not in the table usually ends at the first
/// empty slot.
pub fn build_slots<'a>(keys: impl Iterator<Item = &'a str> + Clone) -> Vec<u32> {
    let n = keys.clone().count();
    let size = (n * 2).next_power_of_two().max(8);
    let mask = size - 1;
    let mut slots = vec![0u32; size];
    for (i, k) in keys.enumerate() {
        let mut s = slot_of(hash(k), mask);
        while slots[s] != 0 {
            s = (s + 1) & mask;
        }
        slots[s] = i as u32 + 1;
    }
    slots
}
