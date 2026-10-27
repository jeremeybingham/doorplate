"""The Python reference (docs/python-api.md) is generated from the stubs; keep it complete (#107, phase 2). Needs no build.

    pytest tools/docs
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "crates" / "doorplate-py" / "python" / "doorplate"


def public_names():
    tree = ast.parse((PKG / "__init__.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "__all__" for t in node.targets):
            return [ast.literal_eval(e) for e in node.value.elts if not ast.literal_eval(e).startswith("__")]
    raise AssertionError("no __all__")


def test_every_public_name_is_on_the_reference_page():
    page = (ROOT / "docs" / "python-api.md").read_text()
    shown = set(re.findall(r"^::: doorplate\.(\w+)\b", page, re.M))
    missing = [n for n in public_names() if n not in shown]
    assert not missing, f"add ::: doorplate.NAME to docs/python-api.md for {missing}"
    for module in ("pandas", "polars", "duckdb", "compat"):
        assert module in shown, module


def test_every_public_function_class_and_method_in_the_stub_has_a_docstring():
    tree = ast.parse((PKG / "__init__.pyi").read_text())
    undocumented = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            if not ast.get_docstring(node) and not (
                isinstance(node, ast.ClassDef) and any(getattr(b, "id", "") == "TypedDict" for b in node.bases)
            ):
                undocumented.append(node.name)
        if isinstance(node, ast.ClassDef) and not any(getattr(b, "id", "") == "TypedDict" for b in node.bases):
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and (not f.name.startswith("_") or f.name == "__init__"):
                    if not ast.get_docstring(f) and not (f.name == "__init__" and len(f.args.args) <= 1):
                        undocumented.append(f"{node.name}.{f.name}")
    assert not undocumented, f"write a docstring in __init__.pyi for {undocumented}"


def test_the_pure_python_helpers_have_docstrings():
    for module in ("pandas", "polars", "duckdb", "compat"):
        tree = ast.parse((PKG / f"{module}.py").read_text())
        assert ast.get_docstring(tree), module
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in ("parse_column", "register", "parse", "tag"):
                assert ast.get_docstring(node), f"{module}.{node.name}"
