"""A MkDocs hook: links from a page in docs/ to a file elsewhere in the repository.

The pages link to the repository with relative paths (`../benchmarks/README.md`, `../tools/review/`),
which work on GitHub and in an editor. The documentation site holds only `docs/`, so those links would
break there. This hook rewrites them, in the site only, to the file on GitHub (the `main` branch);
the Markdown files are not touched. A link to another page of `docs/` stays a link inside the site.
A link to a repository path that does not exist is left alone, so the strict build reports it.
"""
import posixpath
import re
from pathlib import PurePosixPath

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


def on_page_markdown(markdown, page, config, files):
    from pathlib import Path

    repo_root = Path(config["config_file_path"]).resolve().parent
    return rewrite(markdown, page.file.src_path.replace("\\", "/"), config["docs_dir"], repo_root)
