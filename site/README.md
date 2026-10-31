# The doorplate blog (Jekyll)

Published from this folder by `.github/workflows/pages.yml` (Pages source:
GitHub Actions, which the repository already uses) on every push to `main` that changes
`site/`. It can also be started by hand from the Actions tab.

- `demo/index.html` is the live demo (#117): the parser compiled to WebAssembly, run in the visitor's
  browser. `doorplate.wasm` is not in the repository; the Pages workflow builds it from
  `crates/doorplate-wasm` (`cargo build -p doorplate-wasm --target wasm32-unknown-unknown --release`).
  To try the page locally, build it, copy it to `site/demo/doorplate.wasm` and serve the folder (a
  `file:` URL cannot load it). The page sends nothing anywhere; keep it so.
- The demo page's "Parse a CSV file" section (#335) is `demo/csv.js` (the page), `demo/csv-worker.js` (the parser in a Web
  Worker, through the wasm export `parse_batch`) and `demo/csv-core.js` (the CSV reader and writer, tested under Node by
  `tools/docs/test_demo_csv.py`). The result is built in memory and offered as a download; nothing is uploaded and the page has no
  third-party scripts. After a change run the browser check by hand (it needs Playwright; the file's docstring says how):
  `python tools/docs/smoke_demo_csv.py --chrome PATH [--rows N]`. It serves the page from a temporary folder, runs an invented CSV
  through it, and checks that every request is local, that a request to another host is blocked, and that the output equals
  `doorplate parse-file` on the same file.
- `_posts/YYYY-MM-DD-title.md` is a published post.
- `_social/` (not built: the underscore) holds the source and text of social-media graphics and posts, one folder per release (`_social/0.4.1/`: `graphic.html`, `render.py` to export the PNG, `linkedin-post.md`). Post images that the site shows live in `assets/`.
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
