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
  from `tools/ingest/specs/nad.toml`), scored 2026-10-27 with the label scorer of #112 on the current `main` (the extension built after the custom layer, #3; the parser has not changed since).
  NAD labels the house number, the directionals, the suffix, the unit and the street name.
- **NC voter pair:** the as-entered street of the current voter file against the county-entered parts of the March
  snapshot, 5,795,205 pairs joined, 164,316 dropped for a different ZIP, 5,630,889 scored (the residential address), for the unit and the others; scored 2026-10-27 as above.
- **Counts only.** A row with several warnings counts under each. "Differ" is the share of the rows with the warning
  where our part differs from the label, among the rows that have a label for that field. The first row of each source
  is the baseline, every row.
- **The labels are providers' conventions, not ground truth.** Many put the suffix inside the name, a unit may be spelled
  out, and two providers can label the same text two ways (see `ambiguous_number_letter`). A disagreement is a question,
  not a bug count.
- A warning is read against **the fields it is about**; the other columns of the full output are in the report. The
  figures are regenerated with `tools/harness/label_score.py RECORDS --by-warning --confirm`
  ([`docs/tools/harness.md`](tools/harness.md)), after a rule change.

Baselines (every row): in NAD the number differs on 0.9%, the street name on 3.1%, the unit on 3.2%, the suffix on 0.1%;
in the NC voter pair the number on 1.2%, the name on 2.1%, the unit on 0.4%, the suffix on 0.02% (the number figure
there includes voters who moved within a ZIP code). These moved since the first measurement (2026-10-23: name 4.4% and unit
3.6% in NAD; name 2.4%, unit 0.6% and suffix 0.1% in the NC pair) because of the quieter scorer (#112: `EXT`, a suffix inside the
name, a labeled unit that is not in the text) and the rules merged since.

## Look at these rows

The parse may be wrong or incomplete.

Each code has its own section: what it means, how many of the 1,000,000 NAD rows carry it, and how often those rows differ from the labels in the field the code is about.

### unparsed_remainder

Some text could not be placed; it is in `unparsed`.

- **Rows in NAD (of 1M):** 17,106
- **Measured:** unit 37.8% (3,493 / 9,248; baseline 3.2%), name 5.7%, number 6.1%

### missing_street_number

A street with no house number.

- **Rows in NAD (of 1M):** 207
- **Measured:** number 100% (the labels have one)

### missing_street_name

A house number with no street: with a unit (`123 APT 4`), or a lone number (`4871`, #130). The key is `None`.

- **Rows in NAD (of 1M):** 65
- **Measured:** name 100% (64 / 64)

### ambiguous_street_number

The number runs into a numbered street (`409742ND SQ`): a guess.

- **Rows in NAD (of 1M):** 0
- **Measured:** too few rows

### multiple_addresses

Several addresses in one input (`5210/5212 BRISTO ST`).

- **Rows in NAD (of 1M):** 1,390
- **Measured:** number 67.5% (938 / 1,390)

### possibly_truncated

The input looks cut off at a field-length limit.

- **Rows in NAD (of 1M):** 1,530
- **Measured:** suffix 86.7% (98 / 113), postdirectional 92.9% (13 / 14), name 21.2%, unit 8.3%

### missing_unit_number

A designator that needs a number has none (`APT`, `#`).

- **Rows in NAD (of 1M):** 1,024
- **Measured:** unit 96.7% (528 / 546). NC voter (1,770 rows): unit 99.7% (1,702 / 1,707)

### ambiguous_number_letter

One letter after the house number may be the number's suffix or the first word of the street (`123 A MAIN ST`). The parser reads the letters `A` to `D` as the number's suffix (`123A MAIN ST`, #270) unless the next word is a single letter (an initial: `100 J K DAVIS RD`), a street suffix (`123 A ST` is the street `A`), a direction, or a unit or box word; every other letter stays in the street name (`12 F OAK ST`). The warning is raised for both readings, because the text cannot decide it. A letter before a direction (`428 B SOUTH MAIN ST`) is the number's and carries no warning.

- **Rows in NAD (of 1M):** 4,694
- **Measured:** NAD labels the letter the number's suffix in 80% of the flagged rows. Against the labels, on non-direction letters with no direction or bare suffix after them: NAD 5,469 rows, NC voter snapshot 65,147 rows (county-entered parts). `A` and `B` are the number's suffix in 89% to 96% of rows in both sources, `C` and `D` in 73% to 82%, `J` to `T` mostly the street, and a single letter after the letter (an initial) is the street in 99%. The rule above matches the labels in 84.9% (NAD) and 88.4% (NC) of those rows; always "street name" (the reading before #270) 33.6% and 48.2%, always "number suffix" 66.4% and 51.8%.

### second_line_in_street

Line 2 became part of the street that line 1 began (a route, a suffix, a directional).

- **Rows in NAD (of 1M):** 262
- **Measured:** postdirectional 91.0% (61 / 67), unit 50.5% (94 / 186), suffix 46.7%, name 46.9%: a lone letter on line 2 is often a unit. Since #170 a lone directional after a suffix on line 1 is read as the unit and does not raise this, which is why the rows fell from 767 (2026-10-23) to 262

### invalid_zip

A ZIP that is not 5 digits, or ZIP+4 that is not 4.

- **Rows in NAD (of 1M):** 1,320
- **Measured:** name 2.2% (baseline 3.1%): no longer above the baseline (it was 13.4% against 4.4% on 2026-10-23)

### unknown_state

A state-position token that is not a USPS code or a known name.

- **Rows in NAD (of 1M):** 0
- **Measured:** too few rows


### Reading the first group

How to read the strongest ones: `missing_street_number`, `missing_street_name` and `missing_unit_number` are 100% or close
by construction (the label has the part, we have none). `possibly_truncated` and `multiple_addresses` are the
warnings that most reliably point at a wrong **suffix** or a wrong **number**. `unparsed_remainder` is the broadest: in NAD
it mostly means a unit left over (37.8% against 3.2% for every row); in the NC voter pair it is a short list (1,163 rows)
where the number differs on 92.1%. The first review of real rows (the IRS extract, 150 rows, one per failure shape, a lead
and not a measurement; issue #125) found the code right about a wrong parse in 12 of 16 `unparsed_remainder` rows, 56
of 90 `missing_street_number` rows and 26 of 41 `possibly_truncated` rows, with 4 noise rows of 144 judged.

`ambiguous_number_letter` is the one where **the providers disagree**: by state the NAD labels range from 98% number suffix
(MA, NY, MD) to 40% (TX, KY), and the NC county-entered parts are 46% number suffix and 54% street name. The text alone
cannot say, which is what the warning reports; the default for the letters `A` to `D` was decided in #270 from the
labels (see the section above).

## Informational

The parser did something, or the input lacks a part. A parse with one of these is not necessarily wrong.

Each code has its own section: what it means, how many of the 1,000,000 NAD rows carry it, and how often those rows differ from the labels in the field the code is about.

### missing_zip

No ZIP in the input.

- **Rows in NAD (of 1M):** 71,219
- **Measured:** name 5.7% (baseline 3.1%), number 1.2%, unit 3.0%. NC voter (361 rows): number 83.4%

### missing_city

No city in the input. `missing_state` is the same for the state; the two are measured together.

- **Rows in NAD (of 1M):** 66
- **Measured (both codes):** NAD: too few rows. NC voter (308 `missing_city` and 259 `missing_state` rows): number 95.1% and 100%, the one-line form is short of its own number

### missing_state

No state in the input.

- **Rows in NAD (of 1M):** 0
- **Measured:** together with `missing_city`, above.

### non_standard_abbreviation

A spelling Pub 28 does not list was normalized (`TRC` for `TRACE`).

- **Rows in NAD (of 1M):** 107
- **Measured:** name 71.0%, suffix 30.8% (12 / 39): the labels write the name differently

### zero_street_number

House number 0, usually vacant land; treated as no number.

- **Rows in NAD (of 1M):** 8
- **Measured:** number 100% (the label keeps the `0`); NC voter: 6,178 rows, number 100%

### dual_address

A street address and a PO Box in one record; both kept.

- **Rows in NAD (of 1M):** 6
- **Measured:** too few rows

### second_line_skipped

Line 2 was a copy or a no-data line and was dropped.

- **Rows in NAD (of 1M):** 34
- **Measured:** too few rows (unit 87.5%, 7 / 8)

### repeated_text

Text that appears twice in the input was read once and the copy dropped: a line written twice (`812 ASHGROVE ST 812 ASHGROVE ST`, `PO BOX 7 PO BOX 7`), a cut-off copy ahead of the address, or the city, state or ZIP written again at the end of line 1. The parse is the one with the copy removed and the key does not change; the warning says the input repeated itself, so a pipeline can look at those rows (#236). A repeated line 2 is `second_line_skipped`, and the warning is not raised with it. A repeat that is not dropped (the city again at the end of line 1 with a ZIP+4 in the ZIP field, so the street name keeps it) has no warning yet.

- **Rows in NAD (of 1M):** 106 (the copy is the city or the state at the end of line 1)
- **Measured:** too few rows. On the seven large local sources the warning is added to 38,422 of 36,920,703 rows (0.10%): amateur radio 0.50%, carrier census 0.20%, IRS 0.17%, NY corporations 0.09%, Netsyms 0.06%, NC voter 0.02%, NAD 0.01%; no key changes.

### zip_repaired

A ZIP that was nearly right was repaired so the last line could be placed: the leading zero of a four-digit ZIP restored in a state whose ZIPs start with `0` (`NJ 7102` is `07102`), or a ZIP+4 extension shorter than four digits dropped (`TX 75001-5` is `75001`). Without it the city, state and ZIP all stayed unplaced and the key had neither state nor ZIP (#275). The key now carries them; the warning says the input was changed to get there, so a pipeline can look at those rows.

- **Rows in NAD (of 1M):** 3
- **Measured:** too few rows. On the Texas licensing file the warning is on 633 of 211,009 rows (0.30%); on the seven large local sources on 308 of 36,920,703 rows.

### second_line_building

Line 2 is the building name, which no emitter prints.

- **Rows in NAD (of 1M):** 103
- **Measured:** number 1.9%, name 1.0%

### country_ignored

A trailing `USA`, `US` or `UNITED STATES` was dropped, or a street field that was only a country.

- **Rows in NAD (of 1M):** 66
- **Measured:** too few rows

### non_us_address

The text left unplaced ends in the name of a country other than the United States (`LYON 69001 FRANCE`, `AJAX ONTARIO L1Z0E4 CANADA`), or, with no state, the country was read as the city (`LYON 69001, FRANCE`). The address is probably foreign and the US reading of it (the city and state fields as given, a street guess) is only that. Nothing is parsed in a foreign format: the text stays in `unparsed`. A US state name is never a country (`NEW MEXICO`), and a name that is also a surname (`FRANCE`, `JORDAN`, `CHINA`) counts only with a digit in the text, such as a postal code (#361).

- **Rows in NAD (of 1M):** 0
- **Measured:** 9,225 of 36,920,703 rows of the seven large sources: NC voter 7,998 (overseas mailing addresses), IRS 522, carrier census 498, NY corporations 204, Netsyms 2, amateur radio 1. By country: United Kingdom, Germany, Canada, Spain, Japan, France, Australia. Not scored against labeled data (no source labels a foreign address); the NC voter review found 21 of 150 cards were this shape

### placeholder

The street line is stand-in text (`NO SITUS`); the key is `None`.

- **Rows in NAD (of 1M):** 0
- **Measured:** NC voter: 278 rows, number 100% (the snapshot has a number the stand-in text hides)

### intersection_detected

Two streets joined by `&`, `AND`, `@` or `AT`: a corner; the key is `None`.

- **Rows in NAD (of 1M):** 18
- **Measured:** too few rows

### zip_city_mismatch

The city is a known place, but the place list does not give the ZIP to it. Only in a state with curated data (Florida).

- **Rows in NAD (of 1M):** 0
- **Measured:** not measured: no labeled Florida sample

### city_is_county

The city is no place of the state but the name of one of its counties (`HENNEPIN`, `MIAMI DADE`); `place` is empty.

- **Rows in NAD (of 1M):** 1,544
- **Measured:** NAD: name 3.0% (46 / 1,544; baseline 3.1%), number 0.1%, so no more disagreements than other rows. On the self-entered sources it is on 0.013% (amateur licenses), 0.017% (tax-exempt list) and 0.024% (carrier census) of the rows, and 1 of 1,138,982 Netsyms sample rows

### default_state_applied

A `default_state` hint decided a place or a reading; the state stays empty.

- **Rows in NAD (of 1M):** 0
- **Measured:** only with the option

### repeated_label

Reported by `tag()` only: a usaddress label appears in two runs.

- **Rows in NAD (of 1M):** 0
- **Measured:** `tag()` only

### ambiguous_token

Reserved: defined, but the parser does not raise it today.

- **Rows in NAD (of 1M):** 0
- **Measured:** none


### Reading the second group

Why `missing_zip` is mild: the ZIP is the field it is about and NAD labels it in the input, so the rows are not wrong
about it; the rest of the row is parsed without the ZIP's help (the street-name boundary is less certain: 5.7% against
3.1% for every row).

## What is not measured

- **The city and ZIP fields.** NAD's records give them as separate fields, so a pre-split parse reads them back and
  cannot disagree. A measurement needs the one-line form against an independent label (the Florida one-line check,
  `tools/compare/oneline_fl.py`, does the city for one state).
- **Warnings the samples do not exercise:** the placeholder, intersection and truncation codes on addresses of other
  kinds, and the codes above marked "too few rows".
- **Rows with no warning** are not clean: in NAD, 79% of the predirectional disagreements, 66% of the suffix, 70% of the
  street-name, 40% of the number and 9% of the unit disagreements (1,162 of 1,473; 500 of 753; 21,372 of 30,515; 3,774 of
  9,396; 382 of 4,206) carried no warning at all (the reason a score was not built, issue #4). The baseline row shows the rate for every row; a warning is useful when its
  rate is far above it.
