#!/usr/bin/env python3
"""Check that the roadmap, the backlog and the trackers agree with the issues on GitHub (#237).

    python tools/docs/issue_states.py          # needs `gh` (logged in) and the network; run by hand, not in CI

The roadmap and the backlog name issues by number (`#236`). They fall behind when issues close or move (#237 was a
week of drift). This reads the numbers in the prose, asks GitHub for every issue's state and milestone once, and
prints what no longer fits:

- an issue in a *planned* part of the roadmap (0.5.0, Waiting, Researched) or in the 0.5.0, Later or Tooling row of the
  backlog's milestone table that is closed (unless the line says it is done), or whose milestone is another;
- an open issue that neither page mentions;
- a tracker (#200, #201) box that is ticked for an open issue, or unticked for a closed one.

Exit code 1 when something is found. It reads the pages' text only: a wrong sentence is still for a person to find.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKERS = (200, 201)
DONE = re.compile(r"\b(done|closed|merged|shipped|released|fixed)\b", re.I)
ISSUE = re.compile(r"(?<![\w/&#\[`-])#(\d{1,4})\b")
CODE = re.compile(r"(```.*?```|`[^`\n]*`)", re.S)
# roadmap section heading (start of it) -> the milestone its issues belong to (None: open is enough)
ROADMAP_SECTIONS = {"After that": "0.5.0", "Waiting": None, "Researched": None}
# a bullet in "Waiting" that names a milestone
WAITING_BULLETS = {"- **Later**": "Later", "- **Tooling**": "Tooling"}
BACKLOG_ROWS = {"| **0.5.0** |": "0.5.0", "| **Later** |": "Later", "| **Tooling** |": "Tooling"}


def numbers(text):
    """The issue numbers in prose (not in code), in order."""
    out = []
    for i, piece in enumerate(CODE.split(text)):
        if i % 2 == 0:
            out += [int(n) for n in ISSUE.findall(piece)]
    return out


def _lines_of(text, heading_start):
    """The lines of the `## ` section whose heading starts with `heading_start`."""
    out, on = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            on = line[3:].startswith(heading_start)
            continue
        if on:
            out.append(line)
    return out


def _check_line(where, line, expected, issues, problems):
    for n in numbers(line):
        i = issues.get(n)
        if i is None:
            problems.append(f"{where}: #{n} is not an issue")
        elif i["state"] != "OPEN":
            if not DONE.search(line):
                problems.append(f"{where}: #{n} is closed but sits in a planned list ({line.strip()[:60]!r})")
        elif expected and i["milestone"] != expected:
            problems.append(f"{where}: #{n} is in milestone {i['milestone']!r}, listed under {expected!r}")


def check(docs, issues, trackers):
    """`docs`: {name: text}; `issues`: {number: {"state", "milestone", "title"}}; `trackers`: {number: body}."""
    problems = []
    road = docs.get("roadmap.md", "")
    for start, milestone in ROADMAP_SECTIONS.items():
        for line in _lines_of(road, start):
            expected = milestone
            for bullet, m in WAITING_BULLETS.items():
                if line.startswith(bullet):
                    expected = m
            _check_line(f"roadmap.md ({start})", line, expected, issues, problems)
    for line in docs.get("backlog.md", "").split("\n"):
        for row, m in BACKLOG_ROWS.items():
            if line.startswith(row):
                _check_line(f"backlog.md ({m} row)", line, m, issues, problems)
    mentioned = {n for text in docs.values() for n in numbers(text)}
    for n, i in sorted(issues.items()):
        if i["state"] == "OPEN" and n not in mentioned and n not in trackers:
            problems.append(f"#{n} is open and neither the roadmap nor the backlog mentions it ({i['title'][:50]!r})")
    for t, body in trackers.items():
        for m in re.finditer(r"^- \[([ xX])\] #(\d{1,4})\b", body, re.M):
            ticked, n = m.group(1) != " ", int(m.group(2))
            state = (issues.get(n) or {}).get("state")
            if ticked and state == "OPEN":
                problems.append(f"tracker #{t}: #{n} is ticked but open")
            if not ticked and state == "CLOSED":
                problems.append(f"tracker #{t}: #{n} is closed but not ticked")
    return problems


def gh(*args):
    return json.loads(subprocess.check_output(["gh", *args], text=True, cwd=ROOT))


def main():
    try:
        rows = gh("issue", "list", "--state", "all", "--limit", "2000", "--json", "number,state,title,milestone")
        issues = {r["number"]: {"state": r["state"], "title": r["title"], "milestone": (r["milestone"] or {}).get("title")} for r in rows}
        trackers = {t: gh("issue", "view", str(t), "--json", "body")["body"] for t in TRACKERS}
    except (OSError, subprocess.CalledProcessError) as e:
        sys.exit(f"could not read the issues with `gh` ({type(e).__name__}); is it installed and logged in?")
    docs = {n: (ROOT / "docs" / n).read_text(encoding="utf-8") for n in ("roadmap.md", "backlog.md")}
    problems = check(docs, issues, trackers)
    print("\n".join(problems) if problems else f"ok: {len(issues)} issues, the roadmap, the backlog and trackers {TRACKERS} agree")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
