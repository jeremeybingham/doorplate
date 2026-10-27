"""The row of a queue entry as one line, as the review page starts the correction box (helpers.js mirrors it)."""


def one_line(inp):
    if inp.get("last_line"):
        parts = [inp.get("line1"), inp.get("line2"), inp["last_line"]]
    else:
        last = " ".join(x for x in (inp.get("state"), inp.get("zip")) if x)
        parts = [inp.get("line1"), inp.get("line2"), inp.get("city"), last]
    return ", ".join(x for x in parts if x)
