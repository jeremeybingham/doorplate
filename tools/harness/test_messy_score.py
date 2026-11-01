"""Tests for tools/harness/messy_score.py on invented values (no private data).

    pytest tools/harness
"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("doorplate")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import messy_score as ms  # noqa: E402
from doorplate import parse_many  # noqa: E402


def a():
    return parse_many(["12 N Oak Street Apt 4, Springfield, IL 62704 US"])[0]


def test_norm_and_state():
    assert ms.norm("St. Paul,") == "ST PAUL"
    assert ms.norm("nan") == "" and ms.norm(None) == ""
    assert ms.state("Illinois") == "IL" and ms.state("il") == "IL"


def test_fields():
    p = a()
    assert ms.pass_("zip", "62704-1234", p, None) is True
    assert ms.pass_("zip", "62705", p, None) is False
    assert ms.pass_("zip", "nan", p, None) is None
    assert ms.pass_("state", "Illinois", p, None) is True
    assert ms.pass_("state", "nan", p, None) is None
    assert ms.pass_("city", "SPRINGFIELD", p, None) is True
    assert ms.pass_("city", "Shelbyville", p, None) is False


def test_street_name_is_found_in_the_verified_street():
    p = a()
    assert ms.pass_("street", None, p, "NORTH OAK STREET") is True
    assert ms.pass_("street", None, p, "ELM STREET") is False
    assert ms.pass_("street", None, p, None) is None


def test_joined_is_the_queue_string():
    assert ms.joined("12 Oak St", None, "Springfield", "IL", "62704") == "12 Oak St, Springfield, IL 62704"
    assert ms.joined("12  Oak St", "Suite 3", None, "IL", None) == "12 Oak St, Suite 3, IL"
    assert ms.joined("12 Oak St", None, None, None, None) == "12 Oak St"
