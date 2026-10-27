"""Every relative link in a tracked Markdown file points at a file or folder that exists (#229).

A file that moves leaves links behind; the MkDocs build only checks the pages in docs/, so this checks the
rest (the READMEs, CONTRIBUTING.md, AGENTS.md, the pages beside the tools). It needs no MkDocs.

    pytest tools/docs
"""
import posixpath
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# [text](target) and reference definitions; the target ends at a space, a quote or a closing bracket.
LINK = re.compile(r"(?:\]\(|^\[[^\]]+\]:\s*)<?([^)\s>]+)", re.M)
SKIP = ("CHANGELOG.md",)  # history: entries name the paths of their day; site/ is Jekyll, its tags look like links


def tracked_markdown():
    out = subprocess.check_output(["git", "ls-files", "*.md"], cwd=ROOT, text=True)
    return [f for f in out.split("\n") if f and f not in SKIP and not f.startswith("site/") and (ROOT / f).exists()]


def test_relative_links_in_tracked_markdown_resolve():
    broken = []
    for f in tracked_markdown():
        text = (ROOT / f).read_text(encoding="utf-8")
        text = re.sub(r"```.*?```", "", text, flags=re.S)  # examples in code blocks are not links
        for m in LINK.finditer(text):
            target = m.group(1)
            if re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", target, re.I):
                continue
            path = target.partition("#")[0]
            if path and not (ROOT / posixpath.normpath(posixpath.join(posixpath.dirname(f), path))).exists():
                broken.append(f"{f}: {target}")
    assert not broken, "broken relative links:\n" + "\n".join(broken)
