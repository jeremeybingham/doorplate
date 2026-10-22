"""Shapes: an address with its letters turned into `a` and its digits into `9`.

`123 N OAK ST APT 4` is `9 a a a a 9`. A shape is a form of address, never an address, so
it may leave `local-data/` (docs/data-policy.md). The same rule as the `shape` macro of
tools/harness/shapes_report.py, in Python.
"""
import re

MAX_SHAPE = 48


def shape(text):
    """Letters to `a`, digits to `9`, runs collapsed. Punctuation and spacing stay."""
    s = re.sub(r"[^\W\d_]+", "a", text or "")
    return re.sub(r"\d+", "9", s)


def clip(s, n=MAX_SHAPE):
    return s if len(s) <= n else s[:n - 1] + "…"
