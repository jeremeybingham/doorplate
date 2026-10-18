# The doorplate blog (Jekyll)

Published from this folder by `.github/workflows/pages.yml` (Pages source:
GitHub Actions). Nothing is published until that workflow is on `main` **and**
Pages is set to "GitHub Actions" in the repository settings.

- `_posts/YYYY-MM-DD-title.md` is a published post.
- `_drafts/` is **not built**. To publish a draft, move it to `_posts/` and
  give it a date prefix in the file name.
- Preview locally: `bundle exec jekyll serve --drafts` in this folder (needs Ruby and
  the `github-pages` gem; optional).

Posts follow the project's rules: this library formats and parses; it does not
validate deliverability. Examples use invented addresses. Never publish rows from
`local-data/`; only aggregate numbers.
