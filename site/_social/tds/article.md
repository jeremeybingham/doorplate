# Towards Data Science article: draft for the owner

## Notes for the owner (delete before submitting)

- **Submission guidelines not read.** towardsdatascience.com returned 403 to automated fetches, so this draft has not been
  checked against the [submission guidelines](https://towardsdatascience.com/submission-guidelines/). Read them first,
  especially on: articles about your own tool, whether the article must be unpublished elsewhere (do not post it on the
  project blog or Medium until they answer), length, and AI-assisted writing. Known from their public pages: submissions
  go through a form, editors answer in about a week, and authors must use their real names.
- **Disclosure.** The article says up front that you wrote doorplate and the showdown. It also has a sentence about building
  doorplate with an AI coding assistant (marked `[OWNER: ...]`); word it the way you want, but keep it in. Leaving it
  out would be risky with editors and readers in 2026.
- **Figures.** Every figure is from the showdown's pinned run of 2026-11-23 (`report/REPORT.md`, doorplate 0.7.1,
  usaddress 0.5.16, libpostal with the Senzing model) or from `docs/dataframes.md` (the `parse_many` batch figures, 0.7.0
  release candidate, 4 CPUs). The code blocks were run on 2026-11-23 against the current build (0.7.2-dev, which parses
  as 0.7.1); every address in them is invented.
- **Images.** TDS articles do better with images. The charts in `site/_social/showdown/` are from the **older** run
  (doorplate 90.9); regenerate them with the 0.7.1 figures (91.8, 90.7 to 92.9) before using them. Suggested: the Parser
  Score chart with intervals, and the per-part chart. Say in the caption that they are your own images.
- **Length:** about 2,400 words (code blocks included) without these notes.
- **Title options:**
  1. "Replacing usaddress with one import: a faster, rules-based US address parser"
  2. "I built a rules-based address parser and benchmarked it against the ML ones. Here's what held up."
  3. "Parsing US addresses at 100,000 per second, without a model"

---

# Replacing usaddress with one import: a faster, rules-based US address parser

*What I learned building doorplate, how it compares with usaddress and libpostal, and where it still loses.*

If you have worked with US address data, you have probably used [usaddress](https://github.com/datamade/usaddress).
DataMade's library takes a string like `123 N Main St Apt 4, Miami FL 33101` and labels each token: the house number,
the street name, the suffix, the unit, the city. It is the default choice in Python, and for good reason: it is small,
easy to install and usually right.

Over the past five weeks I built a replacement called [doorplate](https://github.com/jeremeybingham/doorplate).
doorplate is a US address parser written in Rust, with a Python package and a command-line tool. This article is about three
claims I want to make for it, and how far each one holds:

1. **It is a drop-in replacement for usaddress**, for code that calls `parse` and `tag`.
2. **It is faster**: about 13 times faster than usaddress from Python, in one process.
3. **It is more accurate**, by a lot on messy and unusual addresses and by a little on ordinary ones.

A disclosure first: I wrote doorplate, and I also built the benchmark the accuracy figures come from. I'll describe
how the benchmark guards against that bias and where it can't. [OWNER: one sentence on how you built it, e.g. "I wrote
the rules and labeled the test data myself, and used an AI coding assistant for much of the implementation."]

## Why another address parser?

Address parsing sounds like a solved problem until you run a real file through it. Public-records exports, mailing
lists and web forms contain things like:

- `RR 3 BOX 12`, a rural route, not a street
- `PSC 1650 BOX 10, APO AE 09173`, a military address
- `CALLE LUNA 123`, a Puerto Rico address with the house number after the street
- `123 OAKBLVD`, two words with the space lost
- units in odd places, units written twice, and cities that start with a compass word (`S Elgin`)

usaddress is a conditional random field (CRF), a statistical model trained on labeled examples. libpostal, the other
common choice, is also a CRF, trained on OpenStreetMap and OpenAddresses data. Both are good at the shapes they were
trained on. When they get something wrong, the fix is to add training data and retrain, which few users do.

doorplate takes the opposite approach: **hand-written rules plus a list of place names**, with no learned model. Every
rule cites its source (USPS Publication 28 where one exists), and every misparse that gets fixed becomes a test case.
That has costs: someone has to write the rules, and a rule can only handle shapes someone has seen. It also has
benefits:

- **It is predictable.** The same input gives the same output, and you can read why.
- **A misparse can be fixed.** A bug report becomes a rule or a line of data, not a retraining job.
- **It is small and fast.** No model to load: the Python wheel has no runtime dependencies and uses about 25 MB of
  memory after loading, against about 3 GB for libpostal.

It does more than label tokens. It also standardizes to USPS Publication 28 and RESO formats, builds a match key for
deduplication, and reports warnings when the input looks wrong. More on the key below.

One thing it does **not** do is validate. doorplate tells you how an address is written, not whether it exists or can
receive mail. Validation needs postal-service-certified data, and no parser gives you that.

## Claim 1: drop-in compatibility with usaddress

Most usaddress code calls one of two functions: `parse`, which returns `(token, label)` pairs, or `tag`, which returns
a dictionary of labeled parts and an address type. doorplate ships a compatibility module with the same functions, the
same label names and the same exception:

```python
import doorplate.compat as usaddress    # was: import usaddress

parts, kind = usaddress.tag("PO Box 12, Tampa FL 33601")
tokens = usaddress.parse("PO Box 12, Tampa FL 33601")
# [('PO', 'USPSBoxType'), ('Box', 'USPSBoxType'), ('12,', 'USPSBoxID'),
#  ('Tampa', 'PlaceName'), ('FL', 'StateName'), ('33601', 'ZipCode')]
```

The rest of the script stays as it was. The tokens are cut the same way as `usaddress.parse`: I checked them token by
token against usaddress's own tokenizer on the 8,108 in-scope strings of its test files and on 56,835 benchmark inputs,
and found no difference. `tag_mapping` works as before, so code that renames labels (`PlaceName` to `City`) keeps
working.

"Drop-in" has limits, and you should know them before you switch:

- **A token doorplate cannot place gets the label `None`.** usaddress labels every token. Code that calls a string
  method on every label needs a guard.
- **Intersections are not modeled.** `Main St & 1st Ave` never comes back as the `Intersection` type; the second street
  is reported as unparsed text with a warning.
- **A repeated label does not raise by default.** usaddress raises `RepeatedLabelError` when a label appears in two
  separate runs. doorplate joins the runs instead, and raises only when you pass `strict=True`, so an existing
  `try/except` keeps its meaning if you ask for it. On the 8,108 strings of usaddress's test files, usaddress raises on 5
  and doorplate (with `strict=True`) on none.
- **There is no model to retrain**, so `tokenize`, `TAGGER` and the training tools are not provided.
- **Some labels differ at the edges.** A parser built from rules and a parser built from a model disagree on rare
  shapes. For example, usaddress labels the `PSC 1650` in a military address as a subaddress, and doorplate labels it as
  a box group.

So it is label compatibility, not identical output. For most scripts that is a one-line change. If you are on a
pipeline that depends on exact labels for unusual shapes, run both on a sample of your data and compare first.

## Claim 2: faster

All of the timings below come from one machine (an Intel Core i9-9900K under WSL2, limited to 4 CPUs) in the
benchmark's pinned run. Read the ratios, not the digits: they move between sessions.

| Calling it from Python, one process | Strings per second | Memory after loading |
|---|---|---|
| doorplate 0.7.1 | about 117,000 | 25 MB |
| libpostal (Senzing model) | about 15,600 | about 3 GB |
| usaddress 0.5.16 | about 9,000 | 27 MB |

That is about 13 times faster than usaddress and 7 times faster than libpostal, in a plain loop of single calls. The
parse itself takes about 6 microseconds in Rust; the rest of each call is the cost of crossing into Python.

For batches, `parse_many` releases Python's global interpreter lock (GIL) and parses in parallel across cores. On
100,000 addresses with 4 CPUs:

| Method | Time | Per second |
|---|---|---|
| a loop of `parse` | 0.74 s | 135,000 |
| `parse_many` | 0.29 s | 345,000 |
| DuckDB, `doorplate_parse(address)` with 7 columns | 0.29 s | 341,000 |
| pandas or Polars `parse_column`, 15 columns | 0.46 to 0.59 s | 170,000 to 216,000 |

(These batch figures are from the 0.7.0 release candidate; 0.7.1 parses identically and slightly faster.) At these
speeds, `parse_many` would get through 10 million addresses in about 30 seconds on 4 CPUs, where a loop of usaddress
calls would take about 20 minutes (estimated from the rates above, not timed).

## Claim 3: more accurate

This is the claim that needs the most care, so here is how it was measured.

### The benchmark

I built an open benchmark, [address-parser-showdown](https://github.com/jeremeybingham/address-parser-showdown), to
compare doorplate, usaddress and libpostal on equal terms. Because each parser uses its own labels, each one is read
through an adapter into one neutral schema of eight fields (house number, street, unit, PO box, route, city, state,
ZIP). A record counts as right only when every field matches the hand label in both span and label.

The data:

- **A new hand-labeled golden set** of 2,439 records in three tiers: `normal` (1,568), `hard` (556) and `nightmare`
  (226). Most came from public records drawn at random; the rest are invented strings of rare and typo shapes. No parser
  was run on any candidate before it was labeled. Every record was checked against doorplate's tests, usaddress's
  training files, libpostal's test sources and the geocode benchmark, so that no parser had seen it. libpostal's
  training data could not be checked.
- **Four outside sets**, scored as neutral parts. These include the `dev` split (60,522 one-line addresses) of the
  geocoding address-parsing benchmark of Yin, Li and Goldberg ([arXiv:2310.14360](https://arxiv.org/abs/2310.14360)),
  and the US rows of Senzing's libpostal test data.
- **Each parser's own test files**, reported separately, since every parser does best on its own tests.

The headline is a **Parser Score**: coarse record accuracy, half from the golden set's three tiers and half from the
neutral parts. I fixed the formula before the first run.

### The results

| | doorplate | usaddress | libpostal |
|---|---|---|---|
| **Parser Score** (95% bootstrap interval) | **91.8** (90.7 to 92.9) | 84.7 (83.4 to 86.0) | 80.8 (79.5 to 82.2) |
| Golden, `normal` tier | 94.9% | 93.6% | 91.8% |
| Golden, `hard` tier | 92.4% | 88.5% | 70.9% |
| Golden, `nightmare` tier | 73.0% | 51.3% | 54.0% |
| Geocode benchmark `dev` (60,522) | 94.4% | 88.4% | 79.9% |
| Senzing US rows (2,172) | 98.1% | 90.6% | **98.8%** |

The ranking holds in every sensitivity check: with equal weights, and with each set left out in turn.

What the numbers say, and what they don't:

- **On ordinary addresses, the three parsers are close.** On the golden set's random public stratum (829 real address
  lines), doorplate gets 93.7%, usaddress 93.0% and libpostal 91.3%. The gap between doorplate and usaddress there is not
  statistically significant (exact McNemar test, p = 0.29). If your data is clean, accuracy is not a reason to switch;
  speed might be.
- **The gap is on hard data.** Most of the spread comes from rarer shapes: rural routes, military lines, units in odd
  places and typos. On the nightmare tier, doorplate is right on 73% and the others on about half. Real exports have a
  long tail of these, and they are often the records you most need to get right.
- **doorplate does not win everywhere.** libpostal is slightly ahead on the Senzing set built from OpenStreetMap, and
  usaddress and libpostal each lead on their own test files.

### The conflict of interest

I wrote the parser, built the benchmark and labeled the golden set, so the benchmark could favor doorplate in ways I
can't see. What I did about it:

- The scoring formula and the labeling conventions were fixed before the first run, and every later change is logged
  with its effect (none changed the ranking).
- Half of the score comes from outside sets I did not label.
- The geocode benchmark's `test` split is left out entirely, because I read it while writing doorplate's rules.
- Every prediction file is published, so anyone can rescore the run or check a single record.

What it doesn't cover: the hand labels are still mine, and one of the four neutral sets (doorplate's own benchmark suite)
was built by me too. Leaving that set out lowers all three scores but keeps the order (89.9, 81.7, 77.9). The full method
is in the [report](https://github.com/jeremeybingham/address-parser-showdown/blob/main/report/REPORT.md). If you think
the method is unfair to usaddress or libpostal, I'd like to hear how.

## Beyond parsing: a key for deduplication

A common reason to parse addresses is to find the same place written two ways. doorplate builds a canonical **match
key** that ignores case, punctuation and abbreviation:

```python
import doorplate

doorplate.parse("123 N. Main St #4, miami, fl 33101").key()
# 'k6:S|123|N|MAIN|ST||FL|33101'
doorplate.parse("123 north main street apt 4, Miami FL 33101").key()
# 'k6:S|123|N|MAIN|ST||FL|33101'
```

`key()` identifies the property. A second key, `key_unit`, includes the unit, for when apartment 4 and apartment 5 must
stay apart. The `k6:` prefix is the key version: store it with your keys, because a later version may change them.

The same thing works in SQL. With DuckDB, deduplicating a table takes one query:

```python
import duckdb
from doorplate import duckdb as dd

con = duckdb.connect()
con.sql("""CREATE TABLE addresses AS SELECT * FROM (VALUES
  (1, '123 N. Main St #4, miami, fl 33101'),
  (2, '123 north main street apt 4, Miami FL 33101'),
  (3, 'PO Box 12, Tampa FL 33601'),
  (4, 'P.O. Box 12 Tampa, Florida 33601')) t(id, address)""")

dd.register(con, columns=["key"])
con.sql("""
  SELECT doorplate_parse(address).key AS key, count(*) AS n, list(id) AS ids
  FROM addresses GROUP BY key ORDER BY key
""").show()
```

```
┌──────────────────────────────┬───────┬─────────┐
│             key              │   n   │   ids   │
├──────────────────────────────┼───────┼─────────┤
│ k6:P|12|FL|33601             │     2 │ [3, 4]  │
│ k6:S|123|N|MAIN|ST||FL|33101 │     2 │ [1, 2]  │
└──────────────────────────────┴───────┴─────────┘
```

There are matching helpers for pandas and Polars (`parse_column`), and a command-line tool that adds parsed columns to
a CSV without any Python (`doorplate parse-file in.csv --column address -o out.csv`).

## Should you switch?

- **Yes, probably**, if you parse large files and speed matters, if your data is messy (public records, mailing lists,
  free-text forms), or if you need standardized output or a dedup key and have been building those yourself.
- **Test first** if your pipeline depends on exact usaddress labels for rare shapes, or on intersections.
- **No**, if you need addresses outside the US (libpostal covers the world) or need to know an address is deliverable
  (that takes a validation service).

You can try it without installing anything: the [in-browser demo](https://jeremeybingham.github.io/doorplate/demo/)
parses as you type and runs on your machine, so nothing is sent anywhere. Otherwise:

```sh
pip install doorplate
```

doorplate is in beta: from version 0.7 the API and warning codes are stable. Its rules have been tested on about 290
million rows of public records, but your data will have shapes mine doesn't. If it gets your addresses wrong, a bug
report with a sample is the most useful thing you can send. `doorplate anonymize` changes the names and digits but keeps
the shape, so you can share the problem without sharing the data.

*doorplate is open source under the MIT or Apache 2.0 license. Code: [github.com/jeremeybingham/doorplate](https://github.com/jeremeybingham/doorplate).
Documentation: [doorplate.readthedocs.io](https://doorplate.readthedocs.io/en/latest/). Benchmark and report:
[address-parser-showdown](https://github.com/jeremeybingham/address-parser-showdown). All images are by the author.*
