# Data policy

What data this project uses, what may be committed, and what may be said about data
that is not ours to publish. It applies to people and to AI agents. This library
formats and parses; it does not validate that an address exists or can receive mail,
and none of the data below is used to claim otherwise.

## Principles

1. **`local-data/` is git-ignored and stays that way.** Source files, extracts, samples,
   profiles and reports live there. Never commit anything from it.
2. **Aggregate numbers and our own fixes ship; source rows do not.** Counts, rates and
   scores can be published. Rows, street names, house numbers, coordinates and
   personal names cannot, in commits, issues, pull requests, docs or comments.
3. **Examples are invented.** A corpus case, a doc example or a bug report uses an
   invented address of the same shape (`CONTRIBUTING.md#sharing-messy-data`).
4. **Never print personal names** from private data, in a terminal log that is pasted
   anywhere or in an agent transcript that is shared.
5. **Every addition to the shipped data cites a source** (`docs/usps-pub28-notes.md`,
   `docs/places.md`, `docs/packs/`), and the source's terms allow the use.

## Sources

| Data | Where it is | May ship? | Terms |
|---|---|---|---|
| Pub 28 tables, Census Gazetteer and 2020 reference lists | `crates/doorplate/data/`, `local-data/places/` | Yes | Public domain (USPS Publication 28; US Census Bureau) |
| GeoNames postal codes | `crates/doorplate/data/` | Yes | CC BY 4.0; attribution in `NOTICE` |
| usaddress test data | `tests/external/usaddress/` | Yes | MIT (datamade) |
| Florida public-record address data | `crates/doorplate/data/packs/fl/` (city/ZIP pairs and street spellings only; no names) | Yes | Public record (Chapter 119, Florida Statutes) |
| Florida DBPR licensee files (names, mailing and location addresses; 293 CSV, 10 XLS) | `local-data/florida-dbpr/` | **No** (aggregates only) | Public record (Chapter 119, Florida Statutes). Contains personal names: only city, ZIP and street-key aggregates may be used, as for the other Florida exports |
| Geocode benchmark (`test`, `dev`, `train`) | `local-data/geocode-benchmark/` | **No** | No license stated. Only aggregate scores ship (`docs/benchmarks.md`). |
| National Address Database (NAD) r24, text file | `local-data/nad-2026/` | **No** (extracts only, see below) | Work of the US federal government, no copyright (17 U.S.C. § 105); the metadata says it is available for re-use without limitation or restriction |
| Netsyms Address Database 2026-05 | `local-data/netsyms-2026/` | **No** (see below) | No formal license; see the next section |
| Florida exports with names, the labeled Florida sample, comparison reports | `local-data/` | **No** | Private; contain personal names or rows |

## The National Address Database (NAD)

The US Department of Transportation's [National Address Database](https://www.transportation.gov/gis/national-address-database)
aggregates address points from state, local and tribal providers (99,226,272 records in
release 24, compiled 2026-09-30; the text file `TXT.zip` from
https://data.transportation.gov/d/fc2s-wawr). Its metadata says it is a work of the federal
government, not subject to copyright, and available for re-use without limitation or
restriction. It also says the data is provided "as is", is not intended for use as a mailing
list, and is subject to state statutes that prohibit that use. We treat it as follows:

- **Use:** parser testing and aggregate statistics only. No mailing lists, and no claim that
  an address exists or can receive mail.
- **Row-level data stays in `local-data/`.** The file is large (42 GB of text) and its
  providers are credited in its own metadata; we do not redistribute it. Aggregate counts
  and our own fixes ship, with invented examples in corpus cases, as for the other sources.
- **Place names:** a name found in `Uninc_Comm`, `Nbrhd_Comm` or the other place columns may
  ship when the counts show it is real and used (rows and distinct providers, cited as
  aggregates), citing NAD as the source. Because NAD is public domain, it can serve as the
  public confirming source itself; keep a threshold written down for any new rule.
- **What we have done with it** (2026-10-19, aggregate results only; scripts in
  `tools/netsyms/`, results in issue #29):
  - *Profile:* 99,226,272 records in 47 jurisdictions (no HI, MI, MS, NH, NV or PR); fill rates
    for each column and state; 95 `NAD_Source` values.
  - *Place names:* 89,490 community and neighborhood names (`Uninc_Comm`, `Nbrhd_Comm`) differ
    from the postal city outside MA and CT, but only 68 of 6,020 city names in the geocode
    benchmark's `train` place-name gap are among them. **Nothing from NAD ships in the place
    data**; the gap is area words and neighborhood labels no address database holds (the area-word
    rule, #62, came from that triage instead).
  - *Scorecard:* a 1,000,000-row random sample scored against NAD's labeled parts
    (`tools/netsyms/nad_score.py`). It confirmed the parser against labeled data and found one
    bug, fixed with corpus `rg-207` to `rg-211`: a trailing directional equal to the city's first
    word (`MAIN ST WEST` / `WEST POINT`) was dropped as a copy of the city.
  - *Evaluated and not used:* NAD's `Addr_Type`, `AddrClass`, `Lifecycle` and `DeliverTyp`
    (mostly `Unknown`, empty or unnormalized), and the GNIS populated-places file (#52: about a tenth
    of the place-name gap, so nothing shipped).
- **If anything derived ships**, cite NAD in `docs/places.md` or the pack doc that uses it.
  The metadata's credit line asks for acknowledgment of the Department of Transportation,
  the Census Bureau's Geography Division and the contributing providers; follow it.

## The Netsyms data

[Netsyms](https://netsyms.com/gis/addresses) publishes a national address database
compiled from open sources (county and state feeds, National Address Database,
OpenAddresses). It has no formal license. Its page says that facts are not
copyrightable and are in the public domain, asks that people "send other people here
instead of giving them the file", and notes that some rows came from free county web map
viewers. We treat it as follows:

- **We do not redistribute the file or any rows from it.** The archive and extracts stay
  in `local-data/netsyms-2026/`.
- **We may publish aggregate results derived from it**: counts, rates, warning classes
  and per-state or per-source summaries. Evidence in commits, docs and issues is
  aggregate counts only (for example, "seen in 312 rows from 4 sources"), with no street
  names, house numbers or coordinates, even as examples. Parser bugs found in it become
  corpus cases with **invented** addresses of the same shape.
- **Place names found in it do not ship on its evidence alone.** A city or community
  spelling is added to the shipped place data (`crates/doorplate/data/places/`, a state
  pack) only when **both** hold:
  1. the Netsyms counts show it is real and used (rows and distinct sources, cited as
     aggregates), and
  2. a **public source confirms it**: the Census Gazetteer or reference lists, GeoNames,
     a state or USPS list, or another source whose terms allow the use.
  The entry cites both. Netsyms is evidence of frequency, never the sole source. A pack
  keeps its own threshold for how many rows count as enough (the Florida pack uses 10
  distinct addresses, `docs/packs/fl.md`); write the threshold down for any new rule.
- **If anything derived from it ships**, add Netsyms to `NOTICE` with a link
  (https://netsyms.com/gis/addresses) and mention it in the data doc that uses it
  (`docs/places.md` or the pack doc). That honors their request without implying a
  license.
- This is a project policy, not legal advice. If the terms change or a rule here becomes
  doubtful, stop using the data and ask.

## The geocode benchmark

The [geocoding address-parsing benchmark](https://github.com/zhengcongyin/geocoding-address-parsing-benchmark)
states no license. Its three splits are downloaded into `local-data/geocode-benchmark/`
and never committed; `docs/benchmarks.md` publishes scores only. Which splits were read
while the rules were written is recorded there: `test` was read, `dev` and `train` were
not, and `dev`'s most common error classes have since been listed. Fix against `train`
and check on `dev` (issue #29).

## Private rows and personal data

Exports from public-record sources and the labeled Florida sample contain personal names
and addresses of real people. Treat them as private even when the source is public
record: only city, ZIP and street-key aggregates, as in the Florida pack, are used. A
corpus case is never a real row; use an invented one with the same shape.

## Checklist before committing data-derived changes

- [ ] No file under `local-data/` is staged (`git status` shows none; it is git-ignored).
- [ ] Nothing in the diff, the PR text or an issue comment contains a real row, street
      name, house number, coordinate or personal name from private data.
- [ ] Every added place, spelling or rule cites its source, and a Netsyms-derived addition
      cites a public source as well.
- [ ] Corpus cases use invented addresses.
- [ ] `NOTICE` and the data doc mention any new third-party source.
