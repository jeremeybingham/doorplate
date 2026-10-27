"""A MkDocs hook: links from a page in docs/ to a file elsewhere in the repository.

The pages link to the repository with relative paths (`../benchmarks/accuracy.py`, `../tools/review/`),
which work on GitHub and in an editor. The documentation site holds only `docs/`, so those links would
break there. This hook rewrites them, in the site only, to the file on GitHub (the `main` branch);
the Markdown files are not touched. A link to another page of `docs/` stays a link inside the site.
A link to a repository path that does not exist is left alone, so the strict build reports it.
"""
import posixpath
import re
from pathlib import Path, PurePosixPath

REPO = "https://github.com/jeremeybingham/doorplate"
# [text](target) and reference-style definitions; skips images' targets only by being rewritten too.
LINK = re.compile(r"(\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")


def rewrite(markdown, src_path, docs_dir, repo_root):
    """`markdown` with each relative link that leaves `docs_dir` pointing at GitHub."""
    page_dir = PurePosixPath(src_path).parent

    def fix(m):
        target = m.group(2)
        if re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", target, re.I):
            return m.group(0)
        path, sep, anchor = target.partition("#")
        joined = posixpath.normpath(str(page_dir / path))
        if not joined.startswith(".."):
            return m.group(0)  # inside docs/: MkDocs resolves it
        rel = posixpath.normpath(posixpath.join("docs", joined))  # relative to the repository root
        if rel.startswith("..") or not (repo_root / rel).exists():
            return m.group(0)
        kind = "tree" if (repo_root / rel).is_dir() else "blob"
        return f"{m.group(1)}{REPO}/{kind}/main/{rel.rstrip('/')}{sep}{anchor}{m.group(3)}"

    return LINK.sub(fix, markdown)


# `#123` in prose: an issue or a pull request. Not in code, not inside a link (text or target), not an anchor (`](#123)`).
ISSUE = re.compile(r"(?<![\w/&#\[`-])(?<!\]\()#(\d{1,4})\b(?![\w-])")
CODE = re.compile(r"(```.*?```|`[^`\n]*`|\[[^\]\n]*\]\([^)\n]*\)|<https?://[^>\n]*>)", re.S)


def link_issues(markdown):
    """`markdown` with each `#123` in prose turned into a link to that issue on GitHub (GitHub does this itself)."""
    pieces = CODE.split(markdown)  # the odd pieces are code or links and stay as they are
    for i in range(0, len(pieces), 2):
        pieces[i] = ISSUE.sub(lambda m: f"[#{m.group(1)}]({REPO}/issues/{m.group(1)})", pieces[i])
    return "".join(pieces)


# [`warnings.md`](warnings.md): on GitHub a file name is a fine link text, on the site a reader wants the page's title.
FILE_LINK = re.compile(r"\[`[^`\n]+\.md`\]\(([^)\s#:]+\.md)((?:#[^)\s]*)?)\)")


def title_links(markdown, src_path, docs_dir):
    """`markdown` with each link whose text is a page's file name, to a page in docs_dir, showing that page's title."""
    page_dir = PurePosixPath(src_path).parent

    def fix(m):
        target = posixpath.normpath(str(page_dir / m.group(1)))
        path = Path(docs_dir) / target
        if target.startswith("..") or not path.is_file():
            return m.group(0)
        first = next((l for l in path.read_text(encoding="utf-8").splitlines() if l.startswith("# ")), None)
        return f"[{first[2:].strip()}]({m.group(1)}{m.group(2)})" if first else m.group(0)

    return FILE_LINK.sub(fix, markdown)


def on_page_markdown(markdown, page, config, files):
    repo_root = Path(config["config_file_path"]).resolve().parent
    src = page.file.src_path.replace("\\", "/")
    markdown = rewrite(markdown, src, config["docs_dir"], repo_root)
    markdown = title_links(markdown, src, config["docs_dir"])
    return link_issues(markdown)
