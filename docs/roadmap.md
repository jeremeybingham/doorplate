# Roadmap

What is planned, what waits, and what is not planned. `doorplate` is an alpha until 0.7.0, which is planned as the first beta: priorities follow the data people
bring, so the more real, messy addresses it sees, the sooner the items below can happen
([Sharing messy data](../CONTRIBUTING.md#sharing-messy-data)). Labels, milestones and ordering: [`backlog.md`](backlog.md).
What each release changed is in [`CHANGELOG.md`](../CHANGELOG.md).

**Last reviewed 2026-11-20.** 0.7.0 is planned as the first **beta** (below). 0.6.2 (a second speed release, no key change; the `k5` is as in 0.6.0) is released; 0.6.1 (speed and one label fix, no key change) is released. Open trackers: #417 (decided against); the 0.6.x tracker (#673) and the speed tracker (#672) are closed.

## Stability: alpha now, beta from 0.7.0

0.6.x is an alpha:

- **Keys.** The match key is versioned and each version is a contract ([`key-format.md`](key-format.md)), but expect new
  versions: a parser fix that changes what an input produces changes its key. Store the version prefix with the keys.
- **API and warning codes.** Names may change before 1.0, with a note in the changelog.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md)), not on yours.

From 0.7.0 (the beta; the plan is below) the three API surfaces and the warning codes are stable: a rename or removal is
announced one release ahead ([`api-surface.md`](api-surface.md), "Deprecation"). The `k6` is the key of the beta. Later rules that
change what an input produces still get a new key version, but only in a minor release (0.8 and later), never in a patch, and
the changelog says so. Nothing else in the API is planned to change.

## Next: 0.6.x, no key change

No tracker is open. Point releases carry speed, tooling and documentation, never a key change. A CI guard fails a pull request that adds more than 1% instructions per parse; the speed leads left are under Waiting, below.

- **Shipped in 0.6.2:** the speed work of #701 and #703 G1 to G8 (about 25% less time per parse than 0.6.1, no output change); the leads left are under Waiting.
- **Shipped in 0.6.1:** the speed cuts of #672 (B, C, and the feature bitset and `Piece::sub` byte tests of D, about 27% less time per parse than 0.6.0), #652 (a letter written twice gets a label in `parse_tokens`), and the answer to #671 (the #614 rule, not a regression).
- **Blog post:** [doorplate 0.6.1](https://jeremeybingham.github.io/doorplate/2026/11/13/doorplate-0-6-1.html).

## Planned: 0.7.0, the first beta and the `k6`

The goals of 0.7.0, in the order they ship:

1. **Remove the state data structure (#700, the last API break; done).** Florida's rows fold into the ordinary place list and base tables; `state_data_version`
   leaves `Diagnostics`, Python and the JSON provenance. No key and no parse output changes. After it, no break is planned.
2. **Puerto Rico improvements:** the rules below, researched first (#332).
3. **Better accuracy generally:** the key-affecting rules below, measured at P2 or above, each against the frozen `k5` keys before it merges.
4. **Beta:** the release pull request changes the "Alpha release" notice in the four READMEs, `docs/index.md`, `SECURITY.md` and the
   PyPI classifier (`Development Status :: 4 - Beta`) to a beta, and the key rules of the stability section above start to apply.
   The beta needs 1 and 3 done and the `k6` measured on the private sources; item 2 does not have to be finished (a Puerto Rico rule that
   misses the release moves to 0.8).

Working order (tracker #724; each group is one batch, unit rules one after another): **the regular rules first, then Puerto Rico** (owner, 2026-11-19).
Done before the rules: #700. Every regular rule measured at P2 or above is merged; what is left:

- **Boxes and routes:** #304 (glued box and route words) and #598 (`PO DRAWER C`), both P3, in on the owner's priorities. Done: #538 (`STAR RT`), #734 (a name line before a PO Box).
- **Names beside the street:** #341 (` - WORD` after the suffix; the rule is decided, its review queue decides which tails it covers) and #726 (a name line with no building word; the reading is decided, the rule waits on a second queue and moves to 0.8 if that queue is not read before the release). Done: #310.
- **Bug:** #787 (a span from the #244 rule on an empty line 2).
- **Puerto Rico (#332), after the rules:** #314 (the Texas `PR` guard, first), #318, #319, #747, #748, #749, and #92 (the Pub 28 sources). A Puerto Rico rule that misses the release moves to 0.8.
- **Done in the other groups:** spellings #289, #375, #471 (one data PR; #725 closed with no rule); house numbers #311, #617, #274; units #294, #693, #499, #498, #272; one-line separators #732, #733, #736; others #519, #327, #357, #244, #553, #750 (a period between two digits stays in the key).
- **Moved out (owner, 2026-11-19):** #321, #360, #312, #307, #351, #589, #644, #645 and #656 to Later; #729 (the RESO 2.1 full-word suffix as an option) to 0.7.x.

Issues below the P2 line are in on the owner's priorities or as members of a group; the list may be cut later.

## Waiting, on data or demand

One line per kind. Every open issue here is in the **Later** milestone (or **Tooling**, where noted); none is at the P2 line (200 rows; 2,500 for P1), and none is in a 0.7.0 group.

- **Units:** #243, #290, #295, #345, #238, #559, #534, #531, #558, #770 (a unit split from its designator, left over when #294 merged), #778 (left over from #498).
- **Boxes and routes:** #358, #307 (a route after a street), #774 (a box after the ZIP; no milestone, decided with pudl).
- **House numbers and street names:** #594, #643, #560, #360 and #312 (a letter before a direction or the number), #321 (designator words after the suffix).
- **Names beside the street and parentheses:** #351, #589, #644, #645.
- **City field and line 2:** #367, #480, #482, #483, #596, #597, #741, #742.
- **Glued strings (split and re-parse):** the tracker #761 with #762, #763, #764, #765, #766; #741 and #742 above are parts of it, as are #304 (in 0.7.0) and #656.
- **ZIP forms and odd text:** #601, #602.
- **Parsing ideas:** #397, #435.
- **Review data and tooling:** #222, #225, #395, #403; the Tooling milestone (never shipped, never closed): #323, #609, and the parser showdown (its own repository).
- **Data, API, docs and speed:** #233, #11 (Won't Do), #253, #712 (speed leads left).
- **usaddress dependents (no milestone, research):** the survey #723 and the pudl benchmark #728, with its rule list #731.
- **Not yet issues:** a highway modifier before a city on one line, a comma
  after a directional, a unit followed by business words, and
  `possibly_truncated` firing on some complete units.
- **A public Arrow result and a Polars expression namespace** only if there is demand.
- **usaddress labels** (#35): the drop-in module is done; more labels proceed when someone needs them. Recipient and name lines,
  landmarks and street corners stay out of scope; that text goes to `unparsed`.

## Researched, but not supported

International addresses are **not supported**. Two questions about them are researched, not planned: Canadian addresses (#203)
and a libpostal-shaped output ([`libpostal-compat.md`](libpostal-compat.md)). A result would become its own issue.

## Not planned

- **Address validation or deliverability.** That needs postal-service-certified data.
- **Geocoding, fuzzy matching, address correction.**
- **International addresses.**
- **A machine-learned model.** The parser is rules plus place data on purpose, so a fix is a rule or a line of data, and the
  same input gives the same output.
