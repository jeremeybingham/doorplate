# Benchmarks: accuracy

Figures: 0.6.0 (`a6a7df4`), measured 2026-11-12, unless a table names another build (0.5.1 is `c68760e`; 0.6.1 is `c0976c7`, measured 2026-11-13: the speed and size rows only, because 0.6.1 changes no output and the accuracy runs on the suite's v1 files gave the 0.6.0 figures again); one machine (Intel Core i9-9900K, WSL2); usaddress 0.5.16.
Speed, size and memory are on [their own page](speed-and-size.md); how to rerun each benchmark is in [`running-benchmarks.md`](running-benchmarks.md).

## Summary

| | Build | doorplate | usaddress |
|---|---|---|---|
| [Benchmark suite](#the-benchmark-suite), whole suite (19,586), whole address right, coarse: **v2** (v1) | 0.6.0 (`a6a7df4`) | **95.6%** (94.4%) | 85.5% |
| Benchmark suite, `natural` stratum (16,001): **v2** (v1) | 0.6.0 (`a6a7df4`) | **98.7%** (98.5%) | 96.1% |
| [Geocode benchmark](#geocode-benchmark-one-line-no-commas), `dev` split (60,522), whole address right, coarse | 0.6.0 (`a6a7df4`) | 94.4% | 88.1% |
| Addresses per second, one thread, suite inputs (`parse_tokens` / `usaddress.parse`) | 0.6.1 (`c0976c7`) | 82,331 | 8,880 |
| Addresses per second, `parse_many` on 4 threads (usaddress has no batch call) | 0.6.1 (`c0976c7`) | 324,740 | |
| One address in Rust (criterion, median of the corpus shapes) | 0.5.1 (`c68760e`) | 4 to 11 µs | |
| Installed size (wheel / package and dependencies); import time | 0.6.1 (`c0976c7`) | 2.1 MB; 1 ms | 4.8 MB; 10 ms |

Read the suite's `natural` stratum as the estimate for ordinary input, and the geocode `dev` split for one-line street
addresses with input errors. Accuracy uses usaddress's labels, folded into the coarse set (`docs/usaddress-compat.md`,
"Scoring rules"); a whole address is right only when every token is.

## Reading the figures across versions

| Benchmark suite, whole suite (19,586), all records | v1 (frozen) | v2 (letter convention) |
|---|---|---|
| 0.5.1 | 93.4% | 93.4% |
| Before the prefix labels (`a81bb15`) | 92.4% | 93.5% |
| 0.6.0 (`a6a7df4`), with the prefix labels | 94.4% | 95.6% |

usaddress is 85.5% in every cell.

- **Lead with v2; v1 is the series that compares across versions** (92.2% at 0.3.1, 92.3% at 0.4.1, 93.4% at 0.5.1). v2
  scores the same records and counts a letter A to D after the house number as right in the number or in the unit.
- **The v1 drop from 0.5.1 is one convention, not a regression.** All 212 records lost are a letter after the house number
  (`123 B ELM ST`), which 0.6.0 reads as a unit and suite v1, usaddress and fastaddress keep in the number (the geocode
  benchmark keeps it in the street name). No other rule lost a record. The unit reading was chosen on review cards (88%
  read the letter as a unit) and so that `123 B ELM ST` shares a key with `123 ELM ST APT B`. The provider labels disagree:
  they cost 212 of the suite's 241 such records under v1, and the letter is 87% to 92% of the strings the geocode splits
  lost since 0.4.1. The conventions are listed in [`usaddress-compat.md`](usaddress-compat.md#label-conventions).
- **What "best" means here.** Gold labels are providers' field conventions, not ground truth. Where doorplate's reading
  differs on purpose, the difference is named and counted (v2, the label conventions) and never tuned away. The suite is
  not a work list.
- **Why the 0.6.0 rules do not show.** They gained 3 records and lost 0: their shapes are too rare for 19,586 records. They
  are measured by the key comparison, the review queues and the changed-rows review (112 of 150 cards right; 90 of 102 key
  and unit cards).
- **What the remaining errors are** (`a81bb15`, v2, 1,272 records): 556 hold a label doorplate did not model, 437 of them
  the house-number prefix (`W 615 ELM ST`; 0 of 437 scored, 401 right but for the label). Since 0.6.0 the prefix is
  labelled, which is the step to 95.6%. The rest are the unit and street (132), unit and city (127) and street and city
  (82 and 68) boundaries, and a premodifier read as street name (60), mostly in the `hard` stratum.
- **A glued letter** (`123B ELM ST`) stays in the house number and keys apart from the spaced one; it raises
  `glued_number_letter`.

## The benchmark suite

19,586 labeled addresses in `benchmarks/suite/` that neither library's rules, model or tests were made from:
anonymized National Address Database points, TIGER street names, templates for boxes, routes, military and general
delivery, and 1,000 hand-labeled shapes. Gold labels come from the field each token was written from. Run under a fixed
4-CPU, 8 GB profile (`python benchmarks/suite.py all`; specification: [`benchmark-suite.md`](benchmark-suite.md)).

**Whole address right, coarse** (intervals are 95% Wilson):

| | Records | 0.6.0 (`a6a7df4`), v2 | 0.6.0, v1 | 0.5.1 (`c68760e`), v1 | usaddress |
|---|---|---|---|---|---|
| `natural` stratum | 16,001 | 98.7% | 98.5% | 98.5% (98.3 to 98.7) | 96.1% (95.8 to 96.4) |
| Whole suite | 19,586 | 95.6% | 94.4% | 93.4% (93.1 to 93.8) | 85.5% (85.0 to 86.0) |
| `hard` stratum | 2,585 | 76.4% | 69.0% | 61.8% (59.9 to 63.6) | 18.3% (16.9 to 19.8) |
| `hand` stratum | 1,000 | 95.2% | 95.1% | 94.3% (92.7 to 95.6) | 89.1% (87.0 to 90.9) |

- **Which row to read.** `natural` is a random draw by state population: the estimate for ordinary input. `hard` holds
  the records in each blind-spot class of either library, so it is low for both by design. The whole suite blends 80%
  `natural`, 15% `hard` and 5% `hand`.
- **Shared labels** leave out records whose gold labels include one doorplate does not model (a street premodifier, a
  recipient line, landmarks, a country): 0.6.0 96.1% (v2) and 94.9% (v1) of 18,814 records; 0.5.1 96.0% (95.7 to
  96.3) against usaddress 87.9% (87.4 to 88.4) of 18,401, and `natural` 98.8% against 96.4% of 15,472. The set grew
  with the prefix labels, so the two builds are not on the same records. A trailing `USA` is not counted against doorplate.
- **Tokens right:** 0.6.0 99.1% (v2), 98.9% (v1); 0.5.1 98.8%; usaddress 96.8%.
- **Paired, all records, v1** (both right / only doorplate / only usaddress / neither): 0.6.0 16,113 / 2,378 / 633 /
  462; 0.5.1 16,264 / 2,035 / 482 / 805.

By how the record is written (0.6.0, v1, all strata):

| | Records | doorplate | usaddress |
|---|---|---|---|
| Mixed case, commas | 3,561 | 96.9% | 89.4% |
| Uppercase, commas | 5,333 | 96.2% | 89.1% |
| Spelled out (`Avenue`, `Northwest`, `Apartment`) | 2,677 | 96.6% | 86.8% |
| Uppercase, no commas (the geocode style) | 5,042 | 90.6% | 80.1% |
| Mixed case, no commas | 1,973 | 91.6% | 78.7% |
| No state | 460 | 86.1% | 69.1% |
| No ZIP | 659 | 92.6% | 75.9% |
| A recipient line or a trailing `USA` | 612 | 94.6% | 78.1% |

By address type (0.6.0, v1): street 95.6% against 85.9%; PO box 99.6% against 99.6%; rural route 100% against 91.0%;
highway contract 100% against 100%; general delivery 100% against 0.0%; military 72.3% against 0.8%. doorplate's
military figure is the 30 `CMR` boxes of the `natural` stratum, a type the current Pub 28 does not list and doorplate
leaves out on purpose; the share of `CMR` is a choice of the templates.

Blind spots (0.6.0, v1, `hard` stratum, the class is the first token that differs):

| Blind spot | Records | doorplate | usaddress |
|---|---|---|---|
| A trailing direction read as part of the city | 395 | 79.2% | 16.5% |
| A number prefix (`W 615`) read as the number | 376 | 97.6% | 2.7% |
| A number prefix (`W 615`) read as street | 391 | 91.3% | 0.8% |
| A fraction or suffix after the number read as street | 233 | 82.8% | 66.1% |
| A unit identifier read as street | 333 | 60.4% | 5.4% |
| A unit identifier read as city | 209 | 39.2% | 48.8% |
| A city read as street | 164 | 58.5% | 29.3% |
| A street premodifier (`Old`) read as street | 60 | 0.0% | 3.3% |

The number prefix is labelled since 0.6.0 (0.5.1 scored 0.0% on both classes).

**doorplate only** (no usaddress counterpart; 0.6.0, v1):

| Measure | Result |
|---|---|
| Fields input (`parse_fields`), whole record right | 99.1% of 17,693 records (`natural` 99.6%, `hard` 95.6%) |
| House number, street, direction, suffix, ZIP | 99.6% to 100% each |
| Unit number | 98.2% |
| Standardized output (`to_usps`), both lines right | 99.5% of 16,052 records |
| Key stability: one `k5` key across two to four styles of the same record | 91.7% of 18,586 records |
| Two different records with the same key | 4 of 18,584 |
| Of the records parsed wrong, share that raised a warning | 59.9% (152 records) |
| Of the records parsed right, share that raised a warning | 0.2% |

Key stability is below 100% because a spelled-out unit or direction and its abbreviation are one record to a person,
and merging them is a rule of the key format ([`key-format.md`](key-format.md)).

**The private twin** (the same recipe with an unpublished seed, 0.5.0; the 0.6.0 run covered only the doorplate-only track: fields input 99.2% of 17,675 records): `natural` 98.4%, whole suite 93.2%, within 0.4
points of the public figures, so nothing here has been tuned to the public set.

Read with care: the suite is not a regression test or a work list; "improves the suite score" is never a reason for a
rule. Its case mix and styles are chosen, not measured, and it holds no building names.

## Geocode benchmark (one line, no commas)

The [geocoding address-parsing benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark): street
addresses with input errors injected, uppercase, one line (`120 OAK ST SPRINGFIELD IL 62704`), in splits that share no
street. It states no license, so it stays in `local-data/` and only aggregates are published. Cite it as:

```bibtex
@misc{yin2023chatgpt,
  title={Is ChatGPT a game changer for geocoding -- a benchmark for geocoding address parsing techniques},
  author={Zhengcong Yin and Diya Li and Daniel W. Goldberg},
  year={2023},
  eprint={2310.14360},
  archivePrefix={arXiv},
  primaryClass={cs.CL}
}
```

Whole address right, coarse, by build (0.4.0 equals 0.4.1 and 0.5.0 equals 0.5.1 on every split):

| Split (addresses) | 0.3.1 | 0.4.1 | 0.5.1 | 0.6.0 (`a6a7df4`) | usaddress |
|---|---|---|---|---|---|
| **dev** (60,522; the estimate) | 94.4% | 94.5% | 94.3% | **94.4%** | 88.1% |
| train80 (118,538; rules were fixed against it) | 94.4% | 94.4% | 94.2% | 94.3% | 88.1% |
| train20 (29,635; held out, never read) | 94.1% | 94.2% | 94.1% | 94.1% | 88.4% |
| test (30,622; optimistic) | 96.7% | 96.8% | 96.7% | 96.7% | 88.2% |

On `dev` (0.6.0), tokens are right for 98.8% against usaddress's 97.6%, and the whole address in the fine label set
for 84.3% against 80.2%.

- **Read `dev`, not `test`.** The rules and place list were first written while reading `test`'s errors; later fixes
  were made against `train80` and checked on `dev`. The held-out `train20` moves with the fitted splits, so there is no
  sign of over-fitting.
- **The 0.1 to 0.2 point drift since 0.4.1** is the letter after the house number again (98 of 112 lost `dev` strings),
  and about 80% of those are not a letter at all: a street name the benchmark split with a stray space on purpose
  (`512 D ARBY LN` for DARBY), where both of doorplate's readings are wrong. doorplate does not read through a stray
  space: in the seven large sources that join would be wrong far more often than right.
- **Spelled-out directions.** The benchmark abbreviates postdirectionals, so a rule tuned on it alone can overfit. The
  one-line Florida check (300,000 public records, private, true city known; `tools/compare/oneline_fl.py`, 0.6.0) has the city right for 94.7%, 76.6% of the 5,735 whose line 1 ends in a spelled-out compass word and 47.2%
  of the 8,702 whose city starts with one (`NORTH MIAMI`).

### What caps the geocode score

Half the addresses carry one or two of 21 injected error types (the paper's Table 1): a street name split by a space,
a road type written twice, a dropped road type, city, state or ZIP, a misspelled or abbreviated city, a compass word
added to the city. Its "city" is often a neighborhood. Every whole-address error on `dev` (a 0.6.0
pre-release build, `4b07638`, not re-run) sorted by cause:

| `dev`, 60,522 addresses | Coarse score | Paper's 8-label score |
|---|---|---|
| Right | 94.30% | 89.33% |
| Injected input errors (dropped parts, misspelled or abbreviated cities, a compass word added, doubled road types, misspelled route words) | 2,381 | 5,024 |
| A street name split by a space | 143 | 364 |
| A city no place list holds (subdivisions, neighborhoods), on one line with no commas | 565 | 566 |
| A documented doorplate reading (a letter A to D after the number is a unit; a compass word after the suffix is the postdirectional; a grid direction in a county road name) | 193 | 221 |
| Parser errors with a named shape | 126 | 268 |
| Other | 39 | 16 |

Counting the documented readings as agreements gives 94.6% (paper scoring 89.7%); reading split names through as well,
94.9% (90.3%). Only 71.5% of the `dev` cities are in the place list (86.4% on `test`), so the unlisted place is the
largest error that is not injected. The geocode score is not a target by itself.

### Next to the models in the benchmark's paper

The paper tests a BiLSTM-CRF, BERT, roBERTa and DistilBERT trained on `train`, and GPT-3.5 with three examples, on
`test`. It reports F1 per label and a *Parsing Score* (each label's F1 times the weight Texas A&M's geocoder gives it;
best 149). Scored the same way (`benchmarks/geocode_paper_compare.py`, entity level; 0.6.0):

| `test` split | BiLSTM-CRF | BERT | roBERTa | DistilBERT | GPT-3.5 | **doorplate** | usaddress |
|---|---|---|---|---|---|---|---|
| House number | .99977 | .99963 | .99976 | .99970 | .98810 | .99942 | .99282 |
| Predirectional | .99719 | .99378 | .98996 | .99579 | .70077 | .98761 | .98307 |
| Street base name | .99241 | .98963 | .98022 | .99061 | .83853 | .92405 | .91605 |
| Road type | .99705 | .99345 | .98543 | .99427 | .88328 | .93531 | .91820 |
| Postdirectional | .96739 | .96680 | .94003 | .96771 | .42917 | .92146 | .87065 |
| City | .99399 | .99293 | .98539 | .99341 | .90404 | .97947 | .93420 |
| State | .99993 | .99986 | .99894 | .99991 | .97505 | .99854 | .97611 |
| Postal code | 1.00000 | 1.00000 | .99987 | 1.00000 | .97851 | 1.00000 | .99989 |
| **Overall F1** | .99677 | .99545 | .99084 | .99590 | .90875 | **.97263** | .95598 |
| **Parsing Score** | 148.37 | 148.16 | 147.39 | 148.24 | 133.33 | **144.17** | 142.48 |

- The trained models learned this benchmark's own injected errors from 148,173 addresses; doorplate is rules and was not
  trained on it. 73% of its Parsing Score gap to the BiLSTM-CRF is the street base name (area words, spelled-out
  compass words, county roads), 15% the road type, 6% the city.
- `test` is optimistic for doorplate. On `dev` and `train` it has F1 .964 and Parsing Score 142.7 (usaddress .955 and
  142.3 on `dev`, 142.4 on `train`). At token level its `test` F1 is .983 (usaddress .970).

## Other checks

Secondary sets, each with a reason it is not a headline. Only aggregates of the private sets are published
([`data-policy.md`](data-policy.md)).

| Set | What it is | doorplate | usaddress | Read with care |
|---|---|---|---|---|
| [fastaddress](https://github.com/vinvomero/fastaddress)'s hand-labeled addresses (0.6.0) | 273 in-scope owner mailing addresses as county assessors wrote them (recipients, care-of, boxes); `compare_usaddress.py gold` | whole address 72.5%, tokens 94.9%; fine 60.4% and 92.1% | 59.3%, 92.9%; fine 48.0% and 89.9% | Selected, not sampled: over-represents usaddress's mistakes. Their `clean` set is usaddress's own output (87.3% against 100%). 0.5.1 scored 73.3% here: the letter convention |
| [Senzing's libpostal test set](https://github.com/Senzing/libpostal-data) (0.6.0) | 2,233 US rows of OpenStreetMap tags written as one line; house number, road, city, state and ZIP all right | 97.0%; with no state (554 rows) 94.0% | 89.5%; 70.0% | Clean and uniform, not messy. Not comparable with Senzing's own figure; libpostal was not run. Read once for a rule, so later scores are optimistic |
| [MessyStreets](https://github.com/EdGaere/MessyStreets) (Gaere and von Wangenheim, SIGSPATIAL '26, DOI 10.1145/3841645.3843362) | US-like web addresses from schema.org markup; gold and silver are held out, raw is the work list (table below) | gold: city 91.7%, street name 88.3% | | Labels are page markup, not hand-checked: a miss is a question, not a bug count |
| usaddress's own test files (0.6.0) | 2,248 addresses not in usaddress's training files | 99.1% | 100.0% | usaddress's regression tests: a compatibility check, not a contest |
| Golden corpus (0.6.1) | 1,279 whole addresses written with the parser (`doorplate corpus test`) | 1,275 (99.7%) | | A regression set: says nothing about new data |

MessyStreets by field (rows with an empty label for a field are left out of it). The first figure parses the dataset's
own `input` (0.5.0-dev, `7bc011f`), for comparison with geocoders; the second the cleaned fields joined with commas
(`--joined`, 0.5.1 round, `2e5441e`), as the review queue does. The input carries literal `NaN`, `undefined` and `null`,
which is why the city moves.

| Rows | ZIP5 | State | City | Street name |
|---|---|---|---|---|
| Gold (4,270, held out) | 99.9% / 99.9% | 98.3% / 98.8% | 91.7% / 97.7% | 88.3% / 89.6% |
| Silver (2,509, held out) | 99.8% / 99.8% | 97.9% / 98.4% | 88.8% / 97.7% | 87.8% / 90.2% |
| Raw (2,316, work list) | 99.8% / 99.9% | 97.8% / 98.4% | 88.6% / 97.8% | |

Not covered by any measured rate: addresses outside the US or not in English; building names. Rural routes, military
and general delivery are in the suite's templates and the corpus.
