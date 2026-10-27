"""Tests for the MkDocs hook tools/docs/links.py (the documentation site, #107). Needs no MkDocs.

    pytest tools/docs
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import links  # noqa: E402

ROOT = HERE.parents[1]
BLOB = "https://github.com/jeremeybingham/doorplate/blob/main/"


def rw(text, src="how-it-works.md"):
    return links.rewrite(text, src, ROOT / "docs", ROOT)


def test_a_link_out_of_docs_goes_to_github_and_keeps_its_anchor():
    assert rw("[x](../README.md)") == f"[x]({BLOB}README.md)"
    assert rw("[x](../README.md#install)") == f"[x]({BLOB}README.md#install)"
    assert rw('[x](../CHANGELOG.md "log")') == f'[x]({BLOB}CHANGELOG.md "log")'


def test_a_folder_is_a_tree_link():
    assert rw("[x](../tools/review/)") == "[x](https://github.com/jeremeybingham/doorplate/tree/main/tools/review)"


def test_a_page_in_a_subfolder_resolves_from_its_own_folder():
    assert rw("[x](../../README.md)", src="states/fl.md") == f"[x]({BLOB}README.md)"
    assert rw("[x](../places.md)", src="states/fl.md") == "[x](../places.md)"  # inside docs/: left to MkDocs


def test_links_inside_docs_anchors_urls_and_missing_files_are_left_alone():
    for t in ("[x](places.md)", "[x](places.md#a)", "[x](#top)", "[x](https://example.com/a)", "[x](mailto:a@b.c)",
              "[x](../no/such/file.md)"):
        assert rw(t) == t
