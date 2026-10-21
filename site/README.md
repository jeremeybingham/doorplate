# The doorplate blog (Jekyll)

Published from this folder by `.github/workflows/pages.yml` (Pages source:
GitHub Actions, which the repository already uses) on every push to `main` that changes
`site/`. It can also be started by hand from the Actions tab.

- `demo/index.html` is the live demo (#117): the parser compiled to WebAssembly, run in the visitor's
  browser. `doorplate.wasm` is not in the repository; the Pages workflow builds it from
  `crates/doorplate-wasm` (`cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release`).
  To try the page locally, build it, copy it to `site/demo/doorplate.wasm` and serve the folder (a
  `file:` URL cannot load it). The page sends nothing anywhere; keep it so.
- `_posts/YYYY-MM-DD-title.md` is a published post.
- `_drafts/` is **not built**. To publish a draft, move it to `_posts/` and
  give it a date prefix in the file name.
- `_drafts/2026-10-18-doorplate-vs-usaddress.md` is the deferred second post (#88). It is out of
  date (0.2.0 figures, `k1` keys): refresh it from `docs/benchmarks.md` and `docs/key-format.md`
  before it moves to `_posts/`.
- Preview locally: `bundle exec jekyll serve --drafts` in this folder (needs Ruby and
  the `github-pages` gem; optional).

Posts follow the project's rules: this library formats and parses; it does not
validate deliverability. Examples use invented addresses. Never publish rows from
`local-data/`; only aggregate numbers.
