# LinkedIn post: doorplate 0.7.1 (draft for the owner; #859)

No graphic this time (`graphic.png` in this folder is optional). Every figure is from the 0.7.1 blog post
(`site/_posts/2026-11-23-doorplate-0-7-1.md`), which takes them from `docs/benchmarks.md` and `docs/speed-and-size.md`.
Put the links in the first comment if you prefer a cleaner post.

## Main version (about 220 words)

doorplate 0.7.1 is out. It is an open-source US address parser written in Rust, with a Python package and a command-line tool.

0.7.0 was the first beta, and 0.7.1 adds speed on top of it with no change to what any address parses to.

- More accurate: a Parser Score of 91.8 on the address-parser-showdown, against 90.9 for 0.6.2, 84.7 for usaddress and 80.8 for libpostal. The gain is on the hard and nightmare tiers; on ordinary addresses the parsers are close.
- Better in Puerto Rico: on a fixed sample of real Puerto Rico rows, the share that get a warning fell from 45.4% to 38.2%. "CALLE LUNA 123", "APARTADO 825" and "COND VISTA REAL TORRE 2 APT 905" now read right. It is better, not finished.
- Faster: 5.76 microseconds per parse, 10% less than 0.7.0 and 5% less than 0.6.2. The work was skipping scans that cannot match and reusing buffers.
- Stable: from 0.7.0 the API, the command-line options and the warning codes are stable.

The author built the showdown, which is a conflict of interest. The report describes the method and every prediction file is published.

From here, development slows down. The best thing for the project now is users. If you have addresses that parse badly, a bug report with an address is the most useful thing you can send, and `doorplate anonymize` keeps the shape and changes the digits and names.

doorplate parses and formats addresses. It does not validate that an address exists or can receive mail.

pip install -U doorplate

#opensource #rust #python #data #addresses #dataengineering

## Short version (about 70 words)

doorplate 0.7.1 is out: an open-source US address parser in Rust (Python package and CLI), now in beta.

Parser Score 91.8 on a benchmark anyone can rerun (usaddress 84.7, libpostal 80.8; I built the benchmark, so read the method). Puerto Rico rows with warnings fell from 45.4% to 38.2%. 10% less time per parse than 0.7.0.

What it needs now is users and messy real addresses: github.com/jeremeybingham/doorplate

## Hook options (first line, before "see more")

1. My address parser is now in beta, and the thing it needs most is addresses it gets wrong.
2. In Puerto Rico, "CALLE LUNA 123" puts the number after the street. Most parsers read that badly. Mine now reads it right.
3. The last release of my address parser changed nothing it outputs and made it 10% faster.

## Comment to pin (links)

- Blog post: jeremeybingham.github.io/doorplate/2026/11/23/doorplate-0-7-1.html
- Code and docs: github.com/jeremeybingham/doorplate, doorplate.readthedocs.io
- Install: `pip install doorplate` or `cargo install doorplate-cli`
- The benchmark and its report: github.com/jeremeybingham/address-parser-showdown
- Try it in your browser: jeremeybingham.github.io/doorplate/demo/

## Notes for the owner

- "Faster" is the engine on the pinned loop (6.39 to 5.76 microseconds, one alternating session), not wall time from Python; the blog post says to read the ratios, not the digits. The 5.70 microsecond goal was missed by about 1%, and the post does not claim it.
- "Better in Puerto Rico" is the share of rows with a warning other than a missing city, state or ZIP, on a fixed sample of public sources. It did not move on Netsyms (53.0% to 52.9%); the post says so, so I kept "better, not finished".
- The three Puerto Rico examples are in the blog post and the changelog and are invented forms, not rows from the data.
- The post URL assumes the blog's date-path pattern (as in the showdown post); check it once the post is live.
- I left out the state packs and the RESO 2.1 suffix option to keep the post short; both are in the blog post.
