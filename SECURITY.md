# Security policy

## Supported versions

doorplate is an alpha. Security fixes go into the latest release only (see
[`CHANGELOG.md`](CHANGELOG.md)); please upgrade before reporting an issue you found in
an older version.

## Reporting a vulnerability

Please report a vulnerability **privately**, not in a public issue:

1. Open the [Security tab](https://github.com/jeremeybingham/doorplate/security) of this
   repository.
2. Choose **Report a vulnerability** and describe the problem.

Include the version (`python -c "import doorplate; print(doorplate.__version__)"` or the
crate version), the input or steps that trigger it, and what you expected. Use invented
or public addresses; do not send personal data.

You can expect an acknowledgement within about a week. This is a small project maintained
by one person, so there is no guaranteed fix time, but a confirmed vulnerability gets
priority, and you will be credited in the release notes if you wish.

## What counts

doorplate parses and formats text and has no network access, no file access in the
library and no code execution. The issues that matter most are:

- a panic, hang or unbounded memory use on some input (the library promises it never panics
  on input; fuzzing covers this),
- a flaw in the Python extension that could crash the interpreter,
- a problem in a published package or its build and release process.

A wrong parse is a bug, not a vulnerability: please
[open an issue](https://github.com/jeremeybingham/doorplate/issues/new?template=misparse-or-messy-data.md).

This library formats and parses; it does not validate that an address exists or can
receive mail, so that is not a security property either.
