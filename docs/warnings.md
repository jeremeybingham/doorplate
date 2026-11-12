# What each warning tells you

A warning is a finding about the **parse**, not a statement that the address is wrong, and a row without one is not
guaranteed right. The codes are stable snake_case strings (`Warning::code()`, the `warnings` list in Python, the JSON);
new ones may be added in a minor release ([`api-surface.md`](api-surface.md)). The two groups below are
documentation, not an API: nothing in the library separates "look at these" from "informational". The rules behind each
code are in [`usps-pub28-notes.md`](usps-pub28-notes.md).

**Measured rate** is, unless it says otherwise, the share of rows carrying the code whose part differs from the label,
among rows that have a label for that field, in a random 1,000,000-row sample of the National Address Database (NAD).
"Rows" is how many of those 1,000,000 carry the code. The baseline, over every row, is: number 0.9%, street name 3.1%,
unit 3.2%, suffix 0.1%. A warning is useful when its rate is far above the baseline. "Too few" means under about 50 rows.

## Look at these rows

The parse may be wrong or incomplete.

| Code | What it means | What to do | Measured rate |
|---|---|---|---|
| `unparsed_remainder` | Some text could not be placed; it is in `unparsed`. | Read `unparsed`; in NAD it is mostly a unit left over. | 17,106 rows: unit 37.8% (3,493 / 9,248), name 5.7%, number 6.1% |
| `missing_street_number` | A street with no house number, or a care-of or attention line with no street, box or unit (`C/O ACME TIRE`). The key is `None`. | Find the number elsewhere or drop the row. | 207 rows: number 100% (the labels have one) |
| `missing_street_name` | A house number with no street: with a unit (`123 APT 4`) or alone (`4871`). The key is `None`. | Find the street elsewhere or drop the row. | 65 rows: name 100% (64 / 64) |
| `ambiguous_street_number` | The number runs into a numbered street (`409742ND SQ`); the split is a guess. | Check the number and the street. | Too few |
| `multiple_addresses` | Several addresses in one input (`5210/5212 BRISTO ST`). | Split the input before parsing. | 1,390 rows: number 67.5% (938 / 1,390) |
| `possibly_truncated` | The input looks cut off at a field-length limit. | Treat the suffix and number as doubtful; get the full text. | 1,530 rows: suffix 86.7% (98 / 113), postdirectional 92.9% (13 / 14), name 21.2%, unit 8.3% |
| `missing_unit_number` | A designator that needs a number has none (`APT`, `#`). | Ask for the unit; the unit is blank. | 1,024 rows: unit 96.7% (528 / 546). NC voter (1,770 rows): unit 99.7% |
| `ambiguous_number_letter` | One letter after the house number may be a unit, the number's suffix or the start of the street (`123 B MAIN ST`). The parser reads `A` to `D` as a unit (house number 123, unit B), any other letter as the street name (`12 F OAK ST`). Not raised for a directional, a single-letter street (`123 A ST`) or a letter followed by an initial. Rule: [`usps-pub28-notes.md`](usps-pub28-notes.md). | Decide for your data whether the letter is part of the number; the providers disagree (see below). | 4,694 rows. Reviewers read `A` to `D` as a unit in 23 of 26 cards (88%). NAD labels the letter the number's suffix in 80% of flagged rows; the rule matches the labels in 84.9% (NAD) and 88.4% (NC voter) of letter rows |
| `glued_number_letter` | The number has a letter `A` to `D` stuck to it (`123B ELM ST`). The letter stays in the number, so the key differs from the spaced form (`123 B ELM ST`) and the unit form (`123 ELM ST APT B`), which key as `123`. Not raised for `E` to `Z`, a hyphenated letter (`12-B`) or a box number. | Find the rows and decide whether `123B` is a lettered door or a unit written tight. | Not yet measured against labels. In six key-comparison sources, 146,282 glued rows: 13% have a sibling with the bare number or the letter as a unit, 14% sit in a run of lettered numbers, 73% have no sibling |
| `second_line_in_street` | Line 2 became part of the street that line 1 began (a route, a suffix, a directional). | Check line 2 against the street. A lone directional after a suffix on line 1 is read as the unit and does not raise this. | 262 rows: postdirectional 91.0% (61 / 67), unit 50.5% (94 / 186), suffix 46.7%, name 46.9% |
| `invalid_zip` | A ZIP that is not 5 digits, or a ZIP+4 that is not 4. | Fix or drop the ZIP. | 1,320 rows: name 2.2%, below the baseline |
| `unknown_state` | A state-position token that is not a USPS code or a known name. | Check the state field. | Too few |

**Reading the group.** `missing_street_number`, `missing_street_name` and `missing_unit_number` are near 100% by
construction: the label has the part and the parse has none. `possibly_truncated` and `multiple_addresses` most
reliably point at a wrong suffix or number. `unparsed_remainder` is the broadest. `ambiguous_number_letter` is the one
where **the providers disagree**: NAD labels range from 98% number suffix (MA, NY, MD) to 40% (TX, KY), and NC county
parts are 46% suffix, 54% street name. The text alone cannot say, which is what the warning reports; the default for
`A` to `D` is the reviewers' reading, a unit, not the providers' labels. `glued_number_letter` marks the other spelling.

## Informational

The parser did something, or the input lacks a part. A parse with one of these is not necessarily wrong.

| Code | What it means | What to do | Measured rate |
|---|---|---|---|
| `missing_zip` | No ZIP in the input. | Nothing, unless you need it; the key then has no ZIP. | 71,219 rows: name 5.7%, number 1.2%, unit 3.0% |
| `missing_city` | No city in the input, or a placeholder or null city (`Not stated`, `Unknown`). The city is left empty and the original text keeps what was written. | Nothing; most such rows have no ZIP either, so the key is partial. | About 195,000 rows (9,747 of a 50,000-row sample). NC voter (308 rows, measured with `missing_state`): number 95.1% |
| `missing_state` | No state in the input. | As `missing_city`. | 0 rows. NC voter (259 rows): number 100% |
| `non_standard_abbreviation` | A spelling Pub 28 does not list was normalized (`TRC` for `TRACE`). | Nothing. | 107 rows: name 71.0%, suffix 30.8% (12 / 39); the labels write the name differently |
| `zero_street_number` | House number 0, usually vacant land; treated as no number. | Treat as no number. | 8 rows: number 100%. NC voter: 6,178 rows, number 100% |
| `dual_address` | A street address and a PO Box in one record; both kept. The key and slug use the street; the USPS output writes the PO Box. | Decide which one you need. | 6 rows: too few |
| `second_line_skipped` | Line 2 was a copy of the end of line 1 or a no-data line, and was dropped. | Nothing. | 34 rows: too few (unit 87.5%, 7 / 8) |
| `repeated_text` | Text appearing twice was read once: a line written twice (`812 ASHGROVE ST 812 ASHGROVE ST`), a cut-off copy before the address, or the city, state or ZIP repeated at the end of line 1. The key is unchanged. | Look at the source field; it repeated itself. | 106 rows. Over the seven large local sources 0.10% (38,422 of 36,920,703 rows) |
| `zip_repaired` | A nearly right ZIP was repaired so the last line could be placed: a leading zero restored (`NJ 7102` is `07102`), a short ZIP+4 extension dropped (`TX 75001-5`), or a seven- or eight-digit ZIP cut to five. | Check the ZIP if it matters; the key now carries state and ZIP. | 3 rows. Texas licensing file 0.30% (633 of 211,009) |
| `second_line_building` | Line 2 is the building name, which no emitter prints. | Read `building` if you need it. | 103 rows: number 1.9%, name 1.0% |
| `country_ignored` | A trailing `USA`, `US` or `UNITED STATES` was dropped, or a street field was only a country. | Nothing. | 66 rows: too few |
| `non_us_address` | The unplaced text ends in a country other than the United States (`LYON 69001 FRANCE`), or the country was read as the city. Nothing is parsed in a foreign format; the text stays in `unparsed`. A US state name is never a country; a name that is also a surname (`FRANCE`, `JORDAN`) counts only with a digit in the text. | Route the row out of a US pipeline. | 0 rows. 9,225 of 36,920,703 rows of the seven large sources (NC voter 7,998, mostly overseas mailing addresses). Not scored: no source labels a foreign address |
| `placeholder` | The street line is stand-in text (`NO SITUS`, `NOT GIVEN`, `SAME AS ABOVE`); the key is `None`. | Drop or repair the row. | 0 rows in NAD. NC voter: 278 rows, number 100%. 2,464 more rows of the seven sources are registry phrases |
| `intersection_detected` | Two streets joined by `&`, `AND`, `@` or `AT`. The first street is parsed, the second stays in `unparsed`, and the key is `None`. | Handle corners separately. | 18 rows: too few |
| `zip_city_mismatch` | The city is a known place but the place list does not give the ZIP to it. Only in a state with curated data (Florida). | Check the city and ZIP. | 0 rows; not measured (no labeled Florida sample) |
| `city_is_county` | The city is no place of the state but a county name (`HENNEPIN`, `MIAMI DADE`); `place` is empty. | Check the city. | 1,544 rows: name 3.0% (46 / 1,544), the baseline |
| `default_state_applied` | A `default_state` hint decided a place or a reading; `state` stays empty. | Nothing. | 0 rows; only with the option |
| `repeated_label` | Reported by `tag()` only: a usaddress label appears in two runs. | Nothing. | `tag()` only |
| `ambiguous_token` | Reserved: defined, but the parser does not raise it today. | Nothing. | None |

**Reading the group.** `missing_zip` is mild: the rest of the row is parsed without the ZIP's help, and the street-name
boundary is a little less certain (5.7% against 3.1%).

## How the numbers were measured

- **Sources.** NAD (`tools/harness/nad_score.py`) and the NC voter pair (the as-entered street of the current file against
  the county-entered parts of the March snapshot: 5,630,889 rows scored). Counts only; a row with several warnings counts
  under each.
- **The labels are providers' conventions, not ground truth.** A disagreement is a question, not a bug count.
- **Regenerate** with `tools/harness/label_score.py RECORDS --by-warning --confirm` after a rule change
  ([`tools/harness.md`](tools/harness.md)). Not measured: the city and ZIP (NAD gives them as separate fields), and
  rows with no warning, which are not clean: 40% to 79% of NAD's disagreements by field carried none.
