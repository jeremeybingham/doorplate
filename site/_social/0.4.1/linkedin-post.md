# LinkedIn post: doorplate 0.4.1 (draft for the owner; #264)

Attach `graphic.png` (1080 x 1350). Every figure is from `docs/benchmarks.md`, `docs/speed-and-size.md` and `docs/anonymizing.md`
(measured on 0.4.0; 0.4.1 changed no parser rule and no key). Links go in the first comment if you prefer a cleaner post.

## Main version (about 170 words)

Address data is messy, and the messy rows are the ones that break your pipeline.

I just released doorplate 0.4.1, an open-source US address parser written in Rust with a Python package and a command-line tool.

Against usaddress, on the same benchmarks:
- 4.3x faster per thread (38,305 vs 8,937 addresses a second), 17x in batch on 4 threads
- more accurate on 3 of the 4 sets I tested (98.3% vs 96.1% on everyday addresses). usaddress still wins on its own test files, 100% vs 99.2%, and the graphic says so.
- 2.0 MB installed instead of 4.8 MB

New in 0.4.1: `doorplate anonymize`. It changes the digits and names in an address and keeps its shape, so you can share a sample of a private dataset without sharing the data. On nine real sources, 97 to 99.9% of street lines still parse the same afterwards.

It is an alpha and it gets better with real, messy addresses. If you have county exports, mailing lists, rural routes, units in odd places, anything that parses badly: anonymize a few lines and open an issue.

doorplate parses and formats addresses. It does not validate that an address exists or can receive mail.

GitHub: github.com/jeremeybingham/doorplate
Try it in your browser: jeremeybingham.github.io/doorplate/demo/

#opensource #rust #python #data #addresses #dataengineering

## Short version (about 70 words)

doorplate 0.4.1 is out: an open-source US address parser in Rust (Python package and CLI).

4.3x faster than usaddress per thread, more accurate on 3 of 4 benchmarks (usaddress wins on its own test files), 2.0 MB installed.

New: `doorplate anonymize` keeps the shape of an address and changes the digits and names, so you can send me a sample of your messy private data safely.

Alpha, and hungry for messy addresses: github.com/jeremeybingham/doorplate

## Hook options (first line, before "see more")

1. Address data is messy, and the messy rows are the ones that break your pipeline.
2. I benchmarked my address parser against usaddress. It wins 3 of 4, and I'll show you the one it loses.
3. How do you share a private address dataset without sharing the addresses?

## Comment to pin (links)

- Code and docs: github.com/jeremeybingham/doorplate, doorplate.readthedocs.io
- Install: `pip install doorplate` or `cargo install doorplate-cli`
- How to anonymize and send a sample: github.com/jeremeybingham/doorplate/blob/main/docs/anonymizing.md
- How the numbers were measured and how to rerun them: github.com/jeremeybingham/doorplate/blob/main/docs/running-benchmarks.md

## Notes for the owner

- The 17x figure compares doorplate's batch call on 4 threads with usaddress's single call (usaddress has no batch API), so the graphic says "4 threads, batch".
- "More accurate on 3 of 4" counts the four rows of the "In short" table; the fourth, usaddress's own test files, is shown on the graphic.
- Nothing in the post claims the anonymizer makes data safe; the docs say "obfuscation that keeps the shape, not anonymity", and so does the advice to read the output before sharing.
