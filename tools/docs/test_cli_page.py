"""docs/cli.md lists every command and option of the CLI usage text (#107, phase 2). Needs no build.

    pytest tools/docs
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def usage():
    src = (ROOT / "crates" / "doorplate-cli" / "src" / "main.rs").read_text()
    return re.search(r'const USAGE: &str = "(.*?)";', src, re.S).group(1)


def test_every_command_and_option_in_the_usage_text_is_on_the_page():
    text = usage()
    page = (ROOT / "docs" / "cli.md").read_text().split("## Usage text")[0]  # the prose, not the pasted usage
    options = set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*|-o)\b", text))
    commands = set(re.findall(r"doorplate (parse-file|parse|layer check|anonymize|corpus test)", text))
    assert options and commands
    for o in sorted(options):
        assert o in page, f"{o} is in the usage text but not described on docs/cli.md"
    for c in sorted(commands):
        assert f"doorplate {c}" in page, c


def test_the_page_quotes_the_usage_text_as_it_is():
    page = (ROOT / "docs" / "cli.md").read_text()
    body = usage().replace("\\\\", "\\").replace('\\"', '"')
    assert body.strip().splitlines()[1].strip() in page
