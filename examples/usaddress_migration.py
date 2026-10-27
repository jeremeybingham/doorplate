"""Move a usaddress script to doorplate by changing one import (every address is invented).

    python examples/usaddress_migration.py

`doorplate.compat` has usaddress's `parse` and `tag` (and `RepeatedLabelError`). The call
sites below are written as they would be for usaddress; the only line that differs is the
import. The labels are usaddress's, but this is label compatibility, not identical output: a
rules parser and a statistical model disagree at the edges (`docs/usaddress-compat.md`). This
library formats and parses; it does not validate that an address exists or can receive mail.
"""
import doorplate.compat as usaddress  # was: import usaddress

LINES = [
    "123 N Main St Apt 4, Miami FL 33101",
    "PO Box 12, Tampa FL 33601",
    "123 Main St Apt 4 Apt 5, Miami FL 33101",  # a label in two runs
    "Main St & 1st Ave, Tampa FL",              # an intersection: not modeled
    "",
]


def main():
    results = []
    for line in LINES:
        print(f"\n{line!r}")
        print("  parse:", usaddress.parse(line))
        try:
            parts, kind = usaddress.tag(line)
        except usaddress.RepeatedLabelError:  # only with strict=True, see below
            parts, kind = {}, "repeated"
        print("  tag:  ", dict(parts), kind)
        results.append((parts, kind))
    # usaddress raises RepeatedLabelError for the two-unit line; doorplate joins the runs
    # unless you ask for the exception.
    try:
        usaddress.tag(LINES[2], strict=True)
    except usaddress.RepeatedLabelError as e:
        print("\nstrict=True raises:", e.repeated_label)
    # tag_mapping renames labels, as in usaddress.
    print(dict(usaddress.tag(LINES[0], {"PlaceName": "City", "StateName": "State"})[0]))
    # Extras usaddress does not have: a state hint for input with no state.
    print(usaddress.tag("281 Evelyn Dr Dothan", default_state="AL")[0].get("PlaceName"))
    return results


if __name__ == "__main__":
    main()
