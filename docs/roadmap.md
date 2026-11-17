# Roadmap

What is planned, what waits, and what is not planned. `doorplate` is an alpha until 0.7.0, which is planned as the first beta: priorities follow the data people
bring, so the more real, messy addresses it sees, the sooner the items below can happen
([Sharing messy data](../CONTRIBUTING.md#sharing-messy-data)). Labels, milestones and ordering: [`backlog.md`](backlog.md).
What each release changed is in [`CHANGELOG.md`](../CHANGELOG.md).

**Last reviewed 2026-11-17.** 0.7.0 is planned as the first **beta** (below). 0.6.2 (a second speed release, no key change; the `k5` is as in 0.6.0) is released; 0.6.1 (speed and one label fix, no key change) is released. Open trackers: #417 (decided against); the 0.6.x tracker (#673) and the speed tracker (#672) are closed.

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

- **Speed leads at a 0.5% bar:** #703 (tokenizer trims, a hash index for the lexicon tables, place search, allocation groups), one measured pull request per group.
- **Shipped in 0.6.2:** the speed work of #701 and #703 G1 to G8 (about 25% less time per parse than 0.6.1, no output change); #712 keeps the leads left.
- **Shipped in 0.6.1:** the speed cuts of #672 (B, C, and the feature bitset and `Piece::sub` byte tests of D, about 27% less time per parse than 0.6.0), #652 (a letter written twice gets a label in `parse_tokens`), and the answer to #671 (the #614 rule, not a regression).
- **Blog post:** [doorplate 0.6.1](https://jeremeybingham.github.io/doorplate/2026/11/13/doorplate-0-6-1.html) (#491).

## Planned: 0.7.0, the first beta and the `k6`

The goals of 0.7.0, in the order they ship:

1. **Remove the state packs (#700, the last API break).** Florida's rows fold into the ordinary place list and base tables; `state_data_version`
   leaves `Diagnostics`, Python and the JSON provenance. No key and no parse output changes. After it, no break is planned.
2. **Puerto Rico improvements:** the rules below, researched first (#332).
3. **Better accuracy generally:** the key-affecting rules below, measured at P2 or above, each against the frozen `k5` keys before it merges.
4. **Beta:** the release pull request changes the "Alpha release" notice in the four READMEs, `docs/index.md`, `SECURITY.md` and the
   PyPI classifier (`Development Status :: 4 - Beta`) to a beta, and the key rules of the stability section above start to apply.
   The beta needs 1 and 3 done and the `k6` measured on the private sources; item 2 does not have to be finished (a Puerto Rico rule that
   misses the release moves to 0.8).

Working order (tracker #724; each group is one batch, unit rules one after another): **before the rules,** #700, then Puerto Rico (#332, #314, #318, #319, #92). Then the rules:

- **E. ZIP form:** #519.
- **A. Designator and suffix spellings (data only):** #289, #375, #471, #321 (the residual), #725 (misspelled suffix and unit words).
- **C. House-number letter shapes:** #311, #360, and the decision #312.
- **B. Boxes and routes:** #538, #304 with #307, #598.
- **D. Repeated, glued and multi-part units:** the decision #656, then #693 with #499, then #294.
- **F. Names beside the street:** #310, #351, #589, #341, shaped by #726 (named buildings with no building word).
- **G. Parentheses left after #291:** #644 (a warning), #645.
- **H. Other P2 rules:** #498, #274, #327, #357, #244, #272.

Issues below the P2 line are in on the owner's priorities or as members of a group; the list may be cut later.

## Waiting, on data or demand

One line per kind. Every open issue here is in the **Later** milestone (or **Tooling**, where noted); none is at the P2 line (200 rows; 2,500 for P1), and none is in a 0.7.0 group.

- **Units:** #243, #290, #295, #345, #238, #559, #534, #531, #558.
- **Boxes and routes:** #358.
- **House numbers and street names:** #594, #643, #560, #617.
- **City field and line 2:** #367, #480, #482, #483, #553, #596, #597.
- **ZIP forms and odd text:** #601, #602.
- **Parsing ideas:** #397, #435.
- **Review data and tooling:** #222, #225, #395, #403; the Tooling milestone (never shipped, never closed): #323, #609, and the parser showdown (its own repository).
- **Data, API, docs and speed:** #692, #233, #213, #11 (Won't Do), #88, #253.
- **Not yet issues:** a highway modifier before a city on one line, a comma
  after a directional, a PO box on line 2 beside a street with no number, a unit followed by business words, and
  `possibly_truncated` firing on some complete units.
- **A public Arrow result and a Polars expression namespace** only if there is demand.
- **usaddress labels** (#35): the drop-in module is done; more labels proceed when someone needs them. Recipient and name lines,
  landmarks and street corners stay out of scope; that text goes to `unparsed`.

## Researched, but not supported

International addresses are **not supported**. Two questions about them are researched, not planned: Canadian addresses (#203)
and a libpostal-shaped output ([`libpostal-compat.md`](libpostal-compat.md), #215). A result would become its own issue.

## Not planned

- **Address validation or deliverability.** That needs postal-service-certified data.
- **Geocoding, fuzzy matching, address correction.**
- **International addresses.**
- **A machine-learned model.** The parser is rules plus place data on purpose, so a fix is a rule or a line of data, and the
  same input gives the same output.
