# What each warning tells you

A warning is a finding about the **parse**, not a statement that the address is wrong, and not a guarantee that a row
without one is right. This page says what each code means and how often rows that carry it disagree with labeled data,
so a pipeline can decide what to review. The codes are stable snake_case strings (`Warning::code()`, the
`warnings` list in Python, the JSON); the set is not closed, new codes may be added in a minor release
([`api-surface.md`](api-surface.md)). The list with a short sentence each is in [`how-it-works.md`](how-it-works.md);
the details of the rules are in [`usps-pub28-notes.md`](usps-pub28-notes.md).

The groups below are documentation, not an API: nothing in the library separates "needs review" from "informational".

## How the numbers were measured

- **NAD:** a random 1,000,000-row sample of the National Address Database (`tools/harness/nad_score.py`, records file
  from `tools/ingest/specs/nad.toml`), scored 2026-10-23 at the 0.4.0 checkpoint plus the two warnings of #45 and #102.
  NAD labels the house number, the directionals, the suffix, the unit and the street name.
- **NC voter pair:** the as-entered street of the current voter file against the county-entered parts of the March
  snapshot, 2,000,000 pairs (1,943,528 scored after the ZIP guard; the residential address), for the unit and the others.
- **Counts only.** A row with several warnings counts under each. "Differ" is the share of the rows with the warning
  where our part differs from the label, among the rows that have a label for that field. The first row of each source
  is the baseline, every row.
- **The labels are providers' conventions, not ground truth.** Many put the suffix inside the name, a unit may be spelled
  out, and two providers can label the same text two ways (see `ambiguous_number_letter`). A disagreement is a question,
  not a bug count.
- A warning is read against **the fields it is about**; the other columns of the full output are in the report. The
  table is regenerated with `tools/harness/label_score.py RECORDS --by-warning --confirm`
  ([`tools/harness/README.md`](../tools/harness/README.md)), after a rule change.

Baselines (every row): in NAD the number differs on 0.9%, the street name on 4.4%, the unit on 3.6%, the suffix on 0.1%;
in the NC voter pair the number on 1.2%, the name on 2.4%, the unit on 0.6%, the suffix on 0.1% (the number figure
there includes voters who moved within a ZIP code).

## Look at these rows

The parse may be wrong or incomplete.

| Code | What it means | Rows in NAD (of 1M) | Measured (differ / labeled, in the field it is about) |
|---|---|---|---|
| `unparsed_remainder` | Some text could not be placed; it is in `unparsed`. | 17,245 | unit 38.6% (3,593 / 9,319; baseline 3.6%), name 8.5%, number 6.1% |
| `missing_street_number` | A street with no house number. | 262 | number 100% (the labels have one) |
| `missing_street_name` | A house number with no street: with a unit (`123 APT 4`), or a lone number (`4871`, #130). The key is `None`. | 11 | name 100% |
| `ambiguous_street_number` | The number runs into a numbered street (`409742ND SQ`): a guess. | 0 | too few rows |
| `multiple_addresses` | Several addresses in one input (`5210/5212 BRISTO ST`). | 1,390 | number 67.5% (938 / 1,390) |
| `possibly_truncated` | The input looks cut off at a field-length limit. | 1,549 | suffix 76.3% (100 / 131), postdirectional 92.9% (13 / 14), name 21.0%, unit 15.4% |
| `missing_unit_number` | A designator that needs a number has none (`APT`, `#`). | 1,101 | unit 97.1% (569 / 586) |
| `ambiguous_number_letter` | One letter after the house number was read into the street name (`123 A MAIN ST`): it may be the number's suffix. | 4,676 | NAD labels it the number's suffix: number 79.8%, name 80.2%. NC voter: number 1.0%, name 0.5% (3,139 rows) |
| `second_line_in_street` | Line 2 became part of the street that line 1 began (a route, a suffix, a directional). | 767 | postdirectional 91.0% (61 / 67), unit 88.8% (584 / 658): a lone letter on line 2 is often a unit; since #170 a lone directional after a suffix on line 1 is read as the unit and does not raise this |
| `invalid_zip` | A ZIP that is not 5 digits, or ZIP+4 that is not 4. | 1,320 | name 13.4% (baseline 4.4%) |
| `unknown_state` | A state-position token that is not a USPS code or a known name. | 0 | too few rows |

How to read the strongest ones: `missing_street_number`, `missing_street_name` and `missing_unit_number` are 100% or close
by construction (the label has the part, we have none). `possibly_truncated` and `multiple_addresses` are the
warnings that most reliably point at a wrong **suffix** or a wrong **number**. `unparsed_remainder` is the broadest: in NAD
it mostly means a unit left over (38.6% against 3.6% for every row); in the NC voter pair it is a short list (398 rows)
where the number differs on 91.7%. The first review of real rows (the IRS extract, 150 rows, one per failure shape, a lead
and not a measurement; issue #125) found the code right about a wrong parse in 12 of 16 `unparsed_remainder` rows, 56
of 90 `missing_street_number` rows and 26 of 41 `possibly_truncated` rows, with 4 noise rows of 144 judged.

`ambiguous_number_letter` is the one where **the providers disagree**: NAD calls the letter the number's suffix in about
80% of the flagged rows, the NC county-entered parts call it part of the name in 99%. The text alone cannot say, which is
what the warning reports. (Changing which reading is the default would change keys; it is not decided here.)

## Informational

The parser did something, or the input lacks a part. A parse with one of these is not necessarily wrong.

| Code | What it means | Rows in NAD (of 1M) | Measured |
|---|---|---|---|
| `missing_zip` | No ZIP in the input. | 71,219 | name 9.9% (baseline 4.4%), number 1.2%, unit 3.2%. NC voter (112 rows): number 83% |
| `missing_city`, `missing_state` | No city, or no state, in the input. | 66, 0 | NAD: too few rows. NC voter (94 and 78 rows): number 94% and 100%, the one-line form is short of its own number |
| `non_standard_abbreviation` | A spelling Pub 28 does not list was normalized (`TRC` for `TRACE`). | 94 | name 77.7%, suffix 37.0%: the labels write the name differently |
| `zero_street_number` | House number 0, usually vacant land; treated as no number. | 8 | number 100% (the label keeps the `0`) |
| `dual_address` | A street address and a PO Box in one record; both kept. | 6 | too few rows |
| `second_line_skipped` | Line 2 was a copy or a no-data line and was dropped. | 34 | too few rows (unit 87.5%, 7 / 8) |
| `second_line_building` | Line 2 is the building name, which no emitter prints. | 103 | number and name within 2% |
| `country_ignored` | A trailing `USA`, `US` or `UNITED STATES` was dropped, or a street field that was only a country. | 66 | too few rows |
| `placeholder` | The street line is stand-in text (`NO SITUS`); the key is `None`. | 0 | NC voter: 86 rows, number 100% (the snapshot has a number the stand-in text hides) |
| `intersection_detected` | Two streets joined by `&`, `AND`, `@` or `AT`: a corner; the key is `None`. | 18 | too few rows |
| `zip_city_mismatch` | The city is a known place, but the place list does not give the ZIP to it. Only in a state with curated data (Florida). | 0 | not measured: no labeled Florida sample |
| `city_is_county` | The city is no place of the state but the name of one of its counties (`HENNEPIN`, `MIAMI DADE`); `place` is empty. | 0 | not measured: no labeled sample. On the self-entered sources it is on 0.013% (amateur licenses), 0.017% (tax-exempt list) and 0.024% (carrier census) of the rows, and 1 of 1,138,982 Netsyms sample rows |
| `default_state_applied` | A `default_state` hint decided a place or a reading; the state stays empty. | 0 | only with the option |
| `repeated_label` | Reported by `tag()` only: a usaddress label appears in two runs. | 0 | `tag()` only |
| `ambiguous_token` | Reserved: defined, but the parser does not raise it today. | 0 | none |

Why `missing_zip` is mild: the ZIP is the field it is about and NAD labels it in the input, so the rows are not wrong
about it; the rest of the row is parsed without the ZIP's help (the street-name boundary is less certain: 9.9% against
4.4% for every row).

## What is not measured

- **The city and ZIP fields.** NAD's records give them as separate fields, so a pre-split parse reads them back and
  cannot disagree. A measurement needs the one-line form against an independent label (the Florida one-line check,
  `tools/compare/oneline_fl.py`, does the city for one state).
- **Warnings the samples do not exercise:** the placeholder, intersection and truncation codes on addresses of other
  kinds, and the codes above marked "too few rows".
- **Rows with no warning** are not clean: 78.7% of the label disagreements in the sample carried no warning at all (the
  reason a score was not built, issue #4). The baseline row shows the rate for every row; a warning is useful when its
  rate is far above it.
