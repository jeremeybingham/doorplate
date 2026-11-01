# LinkedIn post: doorplate 0.5.1 (draft for the owner; #453)

Attach `graphic.png` (1080 x 1350). Every figure is from `docs/benchmarks.md` and `docs/speed-and-size.md` (0.5.1, `c68760e`; 0.5.1 changed no key and no
parser output against 0.5.0). Links go in the first comment if you prefer a cleaner post. `chart.png` (1080 x 420) is the post's chart, not for LinkedIn.

## Main version (about 170 words)

I just released doorplate 0.5.1, an open-source US address parser written in Rust, with a Python package and a command-line tool.

0.5.0 made it read many more messy shapes and moved the match key to k4, and it cost me some speed. 0.5.1 gets the speed back and then some, with no key changing:
- half the time per parse of 0.4.1 (15.6 vs 31.1 microseconds on one pinned CPU, 85,900 vs 157,500 instructions)
- 4.7x faster than usaddress per thread (43,411 vs 9,297 addresses a second), and 14.8x on 4 threads in batch
- more accurate than usaddress on 3 of the 4 sets I tested (98.5% vs 96.1% on everyday addresses). usaddress still wins on its own test files, 100% vs 99.1%, and the graphic says so.

Most of the gain came from not asking questions twice, and from not asking questions whose answer is no: 83% of the table lookups find nothing, so a small filter in front of each table answers that before the search. I also wrote down what did not work.

New on the Try page: parse a CSV file in your browser. Pick the address column, download the parsed file. Nothing is uploaded.

It is still an alpha, and it gets better with real, messy addresses. If you have addresses that parse badly, `doorplate anonymize` changes the digits and names and keeps the shape: send me a few lines and open an issue.

doorplate parses and formats addresses. It does not validate that an address exists or can receive mail.

GitHub: github.com/jeremeybingham/doorplate
Try it in your browser: jeremeybingham.github.io/doorplate/demo/

#opensource #rust #python #data #addresses #dataengineering #performance

## Short version (about 60 words)

doorplate 0.5.1 is out: an open-source US address parser in Rust (Python package and CLI).

Half the time per parse of 0.4.1, no key changed. 4.7x faster than usaddress per thread, more accurate on 3 of 4 benchmarks (usaddress wins on its own test files).

New: parse a CSV file in your browser, nothing uploaded.

Alpha, and hungry for messy addresses: github.com/jeremeybingham/doorplate

## Hook options (first line, before "see more")

1. My address parser got 7% slower in the last release. In this one it takes half the time it did two releases ago.
2. 83% of the lookups my parser did found nothing. A small filter in front of each table made it twice as fast.
3. I benchmarked my address parser against usaddress. It wins 3 of 4, and I'll show you the one it loses.

## Comment to pin (links)

- Code and docs: github.com/jeremeybingham/doorplate, doorplate.readthedocs.io
- Install: `pip install doorplate` or `cargo install doorplate-cli`
- How the speed came back, with the dead ends: github.com/jeremeybingham/doorplate/blob/main/docs/speed-and-size.md
- How the numbers were measured and how to rerun them: github.com/jeremeybingham/doorplate/blob/main/docs/running-benchmarks.md

## Notes for the owner

- "2x faster than 0.4.1" is the engine on one pinned CPU on the `natural` mix (31.1 to 15.6 microseconds, best of five, builds alternated in one session). From Python the gain is smaller (`parse` on the corpus inputs 63,901 to 72,755 per second), because building result objects is not the parser; the post says so.
- The 14.8x compares doorplate's batch call on 4 threads (137,985) with usaddress's single call (9,297; usaddress has no batch API); the graphic leaves it out and the main text says "in batch".
- "7% slower in the last release" (hook 1) is 0.5.0 against 0.4.1 in instructions (157,500 to 171,600, 9%) and 7% to 9% in time; say "a bit slower" if you want it safer.
- 0.5.0 never had a post, so the LinkedIn text explains it in one line.
- The old comparison chart (six versions, 0.3.0 to 0.5.1-dev, from different sessions) stays in `local-data/`; I did not publish it, because the sessions differ by up to 10% and the 4-thread suite figure at the release (137,985) is lower than the one in the old chart (164,477, an earlier session) which would have undercut the claim for a measurement reason. The post chart uses the one session that measured all three builds side by side.
