---
layout: post
title: "How doorplate's rules get written: 150 addresses at a time, with Claude Code doing the tedious part"
description: "A rules-based address parser was never the fashionable choice, because the rules are tedious to write and worse to maintain. This is the loop I use to find and test new doorplate rules: I label a batch of misparsed addresses, Claude Code does the bookkeeping, and nothing changes without a measurement."
date: 2026-10-29
tags: [address-parsing, claude-code, rust, open-source, process]
---

[doorplate](https://github.com/jeremeybingham/doorplate) is a rules-based US address parser. That is an unusual thing to build now. The two
best-known open-source parsers, [libpostal](https://github.com/openvenues/libpostal) and
[usaddress](https://github.com/datamade/usaddress), are both trained models (conditional random fields): you label a lot of addresses once, train, and
let the model generalize. Part of the reason is the cost of rules. A real address parser needs a great many of them, each one interacts with the others, and a person who has to
write, test and keep all of them in their head tends to give up.

I think that is changing, and not in the way the headlines say. This post is about the workflow I use on doorplate, and about where in that workflow
a person still has to be the one deciding. *(doorplate parses and formats addresses. It does not validate that an address exists or can receive mail.)*

## What a rule is, and why there are so many

`46 A Linden Ave` is house number `46A` on Linden Avenue. `44 West Ave 2B` is a street called West with a unit, not a westbound `Ave 2B`.
`PO Box 12` over `Acme Corp` has a company name on line 2, which is an attention line and not a second street. None of these is hard on its own. The
trouble is that there are so many of them, they are written differently in every database, and a fix for one can break another (a rule for
`BOX 18` after a street name with no suffix has to leave `RR 1 Box 5` and `100 Box Canyon Rd` alone).

A model hides this by averaging over its training data. That works, and it is why those libraries are good, but it also means a wrong answer has no
line of code behind it. You cannot point at the reason, and you cannot fix one case without retraining. A rules parser is the opposite: every
decision is a line you can read, and every fix is a diff. The cost is the tedium, and that is the cost I am now handing to a machine.

## The loop

Each turn of the loop is the same, and it ends with a pull request. The steps where a person is needed are marked.

1. **Build a queue.** A script samples a real public source (a state business registry, a licensing file, a city's address list) and parses every
   string with both doorplate and usaddress. Where the two read a string differently, the row is a candidate. I read the source's notes first
   and choose which fields to sample, because a source can fill a field with something that is not an address. Then the script keeps about 150
   rows, grouped so a hundred cards do not show the same shape a hundred times. *(Human: choosing the source and the fields.)*
2. **Label them.** A local web page shows one row at a time: the input, doorplate's reading in colored parts, usaddress's reading, and where they
   differ. I press a key: doorplate was right, usaddress was right, both were right (a different convention), both were wrong, I can't tell, this is
   not an address. If both were wrong, I type the string the way it should be, or mark the parts myself, and I write a note about what went wrong.
   *(Human: this is the step the whole loop exists for.)*
3. **Gather it consistently.** Every answer is saved with the same fields, whatever I was thinking at the time: verdict, correction, note, and both
   parses with the library version. Claude Code reads the export, groups the answers by what changed (a deleted leading word, a unit moved out of
   the street name, a ZIP repaired) and counts them. A hundred and fifty notes become a short list of patterns with counts.
4. **Find the patterns worth fixing.** Claude proposes candidate rules from the groups and files one issue per rule, each with a count, the shape
   of the failing input and an invented example. I decide which are real. Some are not: a pattern may be a labeling convention, a quirk of the
   source, or something the reviewed rows do not support. *(Human: deciding what counts as right.)*
5. **Write the rule, then measure it.** Claude writes the rule in Rust, a test case with an invented address, and a row in the ledger that says where
   the rule comes from (the USPS publication, or data, and which). Then it parses about 37 million rows from seven sources before and after the change
   and compares the results row by row. The pull request reports how many keys changed and in which source.
6. **Dogfood.** The next queue is parsed with the fixed build, so the fix is on the next batch of cards, and the rows that used to fail either pass or
   fail in a new way. Then back to step 2.

## What I do, and what I don't

The division of labor is the part I find most interesting, because it is not "AI writes the code, human reviews it." Most of the code review comes
last. What comes first is a judgment that nothing else can make: *what is the right answer for this string?*

There is no ground truth for a messy real address. `STE 410 RM 7` over `40 Elm St` could be two units, a unit and a room, or a typo. Whether
`46 A Linden Ave` means house `46A` or a street named `A Linden` depends on how the people who typed it wrote their addresses, and that is a
decision about the data, not about code. I make those calls, one card at a time, and I write down why. A note like "the unit is on the street
line, not the name" is the most valuable thing in the whole system, because it is a fact about the world that I know and the machine does not.

What I no longer do:

- **Count.** "How many of these 150 were the same kind of mistake?" is a query, not an afternoon.
- **Remember.** A rule added in October has to still hold in December. The ledger, the test corpus and the full-corpus measurement remember for me.
- **Check for side effects across 37 million rows.** Nobody reads that many addresses. A program can compare them all, and it did catch what I
  would have missed: one early measurement found that a rule I had called key-neutral by reading the code was not.
- **Write the third variant.** Once the first two spellings of a pattern are in the corpus, the third is a mechanical extension.

## Why every queue ends in a number

Opinions on a sample are not evidence on their own, so each round is reported before it is acted on. Some figures from the rounds so far (all counts
and shares, with invented examples in the issues):

- **Six queues of 150 rows have been labeled so far**: the IRS exempt-organization file, the FMCSA carrier census, FCC amateur licensees, New York
  corporations, Texas licensing and Boston's address list. Each produced a handful of issues, and each issue has the counts behind it.
- In the FCC round, **43 of 105 "silent" rows** (rows doorplate parsed without a single warning, but usaddress read differently) were real misses.
  That is why the comparison queue is the default and not a queue of rows that doorplate already flagged: a flagged queue cannot show you what the
  parser is confidently wrong about.
- In the Boston round, **doorplate was right on 89% of the rows the sample represented**, usaddress on 2%. In the Texas licensing round, doorplate
  was right on 56% and usaddress on 17%. In the FCC round usaddress was right more often than doorplate on the rows represented (29.5% vs 25.8%).
  The review shows where each reading is the better one, not which is "more accurate" overall.
- A review sample stands for its group, so shares are weighted by group size and the cards are not treated as a simple random sample. The
  full-file counts, which are not samples, are in the issues.
- A rule that ships has a measurement, not a feeling. A recent one, for words alone on line 2 under a PO Box, was reported like this: **343 rows
  change, none of the 36,920,000 keys change** (NC voter 168, New York corporations 120, IRS 55). Another changes 266 keys, all of them the trailing
  `PO BOX` words leaving the street name, so it is held for the next key version and does not ship now.

Those figures are not a benchmark and I do not present them as one. The [benchmark suite](https://github.com/jeremeybingham/doorplate/blob/main/docs/benchmark-suite.md)
is separate, frozen, and kept out of the review queues on purpose: the queue builders refuse it, so a rule is never tuned to the score.

## Where the process went wrong, and what that taught me

- **I built a queue without reading the source's notes.** The first New York queue included the CEO role, whose first line is a person's name in
  97% of rows. 59 of 150 rows were noise. Claude had followed the order in the tracker without reading the notes, and I found out after twenty answers. The fix
  went into the project's instructions: read the notes first, choose the roles, and build the comparison queue.
- **The review page was running an old parser.** The second review used a build five days out of date: 20 of 150 cards showed a reading that the code no
  longer produced. The page now compares the build's time to the source and prints a warning in red.
- **I was retyping the same fix.** About 40 of the 92 corrections in the first review were me retyping a whole string to move a welded name to the
  care-of line. That became a keystroke on the page. The tool's gaps are visible in the labels: when the same motion repeats, the interface is wrong.
- **A reading of the code is not a measurement.** One change I had described as not affecting keys did. Now the claim "no key changes" comes from the
  row-by-row comparison, or it is not made.

None of these needed a smarter model. They needed the loop to be honest about what it knew.

## Why this wasn't practical before

I might have written a first version of this parser by hand. I would not have kept it maintained. Each rule needs a source, a test, an entry in the ledger, a change in the
changelog, a before-and-after measurement across the corpus, updates to four READMEs and the documentation, and a check that nothing else moved. Each
is easy. Doing all of them for every rule, indefinitely, is what turns a solo project into a pile of regressions, and it is the
reason the field moved to trained models, which have a different maintenance problem (the data) but a smaller one per fix.

An agent changes the arithmetic. It does not get bored of the fortieth ledger row. It re-runs the measurement without being asked twice. It reads a
hundred and fifty notes and tells me there are three of one kind. The cost per rule falls enough that the rules approach, which gives you
readable and fixable decisions, becomes affordable again.

It also changes who does what. I spend my time on the single step that has to be a person: looking at a real string and deciding what a human who
wrote it meant. I would argue that is a good use of a person, and that it generalizes. In any project with a pile of mechanical work around a
small core of judgment, the useful question is: *which step here can only a person do correctly?* Put the person there, and hand everything else
to something that does not get tired.

## What this is not

- **Nothing is trained on my answers.** The labels are a way of finding rules and checking them. A rule still needs a public source, an invented
  test case and a measurement, and my opinion of one address is a lead, not ground truth.
- **It is not finished.** doorplate is an alpha, the next key version will carry the rules that change stored keys, and there are queues I have not
  yet labeled.
- **It does not remove me, or the need to be careful.** The reviewed rows are real people's and companies' addresses from public sources. They stay
  on my machine, and what leaves it is counts, shapes and invented examples. The same applies to anything I ask Claude to read: only sources I have
  cleared, and only for the session.
- **The comparison is against usaddress, which may be wrong where I am wrong.** Rows both parsers misread the same way are never queued.

If you have addresses that doorplate gets wrong, [the anonymizer](https://github.com/jeremeybingham/doorplate/blob/main/docs/anonymizing.md) makes a
safe sample, and [an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md) is the most useful thing you
can send. The review tool is described in [its documentation](https://github.com/jeremeybingham/doorplate/blob/main/docs/tools/review.md), and the
rule-by-rule changes are in the [changelog](https://github.com/jeremeybingham/doorplate/blob/main/CHANGELOG.md).
