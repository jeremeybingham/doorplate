## What and why

<!-- A reasonable number of related changes per pull request. Say what changes and why; link the issue if there is one. -->

## Checklist

- [ ] `cargo fmt`, `cargo clippy --workspace --all-targets --all-features -- -D warnings` and `cargo test --workspace --all-features` pass
- [ ] A parsing bug fix adds a golden-corpus case (`docs/tests/corpus.md`); `tests/corpus/passing.txt` is updated if more cases now pass
- [ ] A parse-rule change adds a row to `docs/usps-pub28-notes.md` with its source
- [ ] A change to what an input produces as a key uses a new version prefix and updates `docs/key-format.md` (never edit a released key version in place; `k4` is cut with 0.5.0 and frozen from there, so a key change needs `k5`)
- [ ] Python changes: `pytest crates/doorplate-py/tests` passes
- [ ] Related documentation checked and updated: find what you changed in the table in `docs/change-checklist.md`
- [ ] No personal data: examples and corpus cases are invented or public addresses, with no names
