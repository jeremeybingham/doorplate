# Roadmap

What is planned, what waits, and what is not planned. `doorplate` is an alpha: priorities follow the data people
bring, so the more real, messy addresses it sees, the sooner the items below can happen
([Sharing messy data](../CONTRIBUTING.md#sharing-messy-data)). Labels, milestones and ordering: [`backlog.md`](backlog.md).
What each release changed is in [`CHANGELOG.md`](../CHANGELOG.md).

**Last reviewed 2026-11-12.** Open trackers: #416 (0.6.0, the `k5`: the release commit is on `main`, the tag and publish are next) and #417 (decided against).

## Stability while it is an alpha

- **Keys.** The match key is versioned and each version is a contract ([`key-format.md`](key-format.md)), but expect new
  versions: a parser fix that changes what an input produces changes its key. Store the version prefix with the keys.
- **API and warning codes.** Names may change before 1.0, with a note in the changelog.
- **Accuracy and speed** are measured on a few datasets ([`benchmarks.md`](benchmarks.md)), not on yours.

## Next: 0.6.0, the `k5`

The release commit is on `main` and its keys are `k5` (tracker #416). Each rule was measured row by row against the
0.5.1 keys before it merged.

- **Merged:** every rule that was planned for it (the list and the counts are in [`CHANGELOG.md`](../CHANGELOG.md)).
- **Open in the milestone:** the docs pass (#528), which closes with the release sweep.
- **Not in the list:** Puerto Rico street-first forms wait for the Puerto Rico research issue.

## Waiting, on data or demand

One line per kind. Every open issue is in the **Later** milestone unless noted; none is at the P2 line.

- **Units:** #243, #272, #289, #290, #294, #295, #321, #327, #345, #351, #375, #238, #471, #498, #499, #559, #534, #531, #558.
- **Boxes and routes:** #304, #307, #358, #538.
- **House numbers and street names:** #274, #310, #311, #312, #341, #360, #589, #594, #595, #652, #656, #643, #560, #617.
- **State and road forms:** #314, #316, #317; Puerto Rico (#318, #319, #332, #92).
- **City field and line 2:** #244, #357, #367, #469, #480, #482, #483, #553, #596, #597, #644, #645.
- **ZIP forms and odd text:** #519, #599, #598, #601, #602.
- **Parsing ideas:** #397, #435, #490 (shape-first parsing).
- **Review data and tooling:** #222, #225, #215, #395, #403; the Tooling milestone (never shipped, never closed): #323, #609, and the parser showdown (its own repository).
- **Data, API, docs and speed:** #213, #11 (Won't Do), #88, #253, #233, #418, and the post on how rule changes are tested (#491, with 0.6.1).
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
