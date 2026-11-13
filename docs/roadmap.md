# Roadmap

What is planned, what waits, and what is not planned. `doorplate` is an alpha: priorities follow the data people
bring, so the more real, messy addresses it sees, the sooner the items below can happen
([Sharing messy data](../CONTRIBUTING.md#sharing-messy-data)). Labels, milestones and ordering: [`backlog.md`](backlog.md).
What each release changed is in [`CHANGELOG.md`](../CHANGELOG.md).

**Last reviewed 2026-11-13.** 0.6.1 (speed and one label fix, no key change; the `k5` is as in 0.6.0) is released. Open trackers: #417 (decided against); the 0.6.x tracker (#673) and the speed tracker (#672) are closed.

## Stability while it is an alpha

- **Keys.** The match key is versioned and each version is a contract ([`key-format.md`](key-format.md)), but expect new
  versions: a parser fix that changes what an input produces changes its key. Store the version prefix with the keys.
- **API and warning codes.** Names may change before 1.0, with a note in the changelog.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md)), not on yours.

## Next: 0.6.x, no key change

No tracker is open. Point releases carry speed, tooling and documentation, never a key change. A CI guard fails a pull request that adds more than 1% instructions per parse; the speed leads left are under Waiting, below.

- **Shipped in 0.6.1:** the speed cuts of #672 (B, C, and the feature bitset and `Piece::sub` byte tests of D, about 27% less time per parse than 0.6.0), #652 (a letter written twice gets a label in `parse_tokens`), and the answer to #671 (the #614 rule, not a regression).
- **On hold:** #491 (the blog post).

## Planned: 0.7.0, the `k6`

Key-affecting rules measured at P2 or above, each against the frozen `k5` keys before it merges.

- **Units:** #289, #375 and the `SP` part of #471, as one data-only change (misspelled and odd designators).
- **House numbers and street names:** #311, #360, #538.
- **Puerto Rico:** #332 (research first), #319, #318, #92, and #314 (the guard for the Puerto Rico rules).

## Waiting, on data or demand

One line per kind. Every open issue here is in the **Later** milestone (or **Tooling**, where noted); none is at the P2 line.

- **Units:** #243, #272, #290, #294, #295, #321, #327, #345, #351, #238, #498, #499, #559, #534, #531, #558.
- **Boxes and routes:** #304, #307, #358.
- **House numbers and street names:** #693, #274, #310, #312, #341, #589, #594, #656, #643, #560, #617.
- **City field and line 2:** #244, #357, #367, #480, #482, #483, #553, #596, #597, #644, #645.
- **ZIP forms and odd text:** #519, #598, #601, #602.
- **Parsing ideas:** #397, #435.
- **Review data and tooling:** #222, #225, #395, #403; the Tooling milestone (never shipped, never closed): #323, #609, and the parser showdown (its own repository).
- **Data, API, docs and speed:** #692, #233, #213, #11 (Won't Do), #88, #253.
- **Not yet issues:** named buildings without a building word (`THE GARRETT`), a highway modifier before a city on one line, a comma
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
