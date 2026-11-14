#!/usr/bin/env bash
# CI guard for parse speed (#672 D4): instructions per parse, base against head, under callgrind.
#
#   tools/perf/callgrind_guard.sh BASE_REF [LIMIT_PERCENT]
#
# Builds `profile_loop` at BASE_REF (in a temporary worktree) and at the checkout, runs both under
# callgrind on the first 4,000 inputs of the suite's `natural` mix (public data, 5 passes = 20,000 parses),
# prints both counts, and exits 1 when the checkout executes more than LIMIT_PERCENT (default 1.0) more
# instructions than the base. Counts repeat to within a few instructions, so no noise margin is needed. Comparing two
# builds in one run (not against a stored number) keeps a compiler update from tripping the guard.
# Needs valgrind and python3. Needs a few minutes (two release builds with fat LTO).
set -euo pipefail

base_ref=${1:?usage: callgrind_guard.sh BASE_REF [LIMIT_PERCENT]}
limit=${2:-1.0}
root=$(git rev-parse --show-toplevel)
work=$(mktemp -d)
cleanup() {
	git -C "$root" worktree remove --force "$work/base" 2>/dev/null || true
	rm -rf "$work"
}
trap cleanup EXIT

python3 "$root/benchmarks/profile_inputs.py" "$work/in" >/dev/null
head -n 4000 "$work/in/mix.txt" >"$work/inputs.txt"

# One target directory per build: both checkouts have the same package path inside their workspace, so a shared
# directory made the head reuse the base's build-script output when a change touched build.rs (found in #703 G6).
build() { # SRC_DIR OUT_BINARY
	(cd "$1" && cargo build --release -q -p doorplate --example profile_loop --target-dir "$2.target")
	cp "$2.target/release/examples/profile_loop" "$2"
}
count() { # BINARY -> instructions
	valgrind --tool=callgrind --callgrind-out-file="$work/cg.out" "$1" "$work/inputs.txt" 1 >/dev/null 2>&1
	awk '/^summary:/ {print $2; exit}' "$work/cg.out"
}

git -C "$root" worktree add --detach -q "$work/base" "$base_ref"
build "$work/base" "$work/base_loop"
build "$root" "$work/head_loop"

base=$(count "$work/base_loop")
head=$(count "$work/head_loop")
pct=$(awk -v b="$base" -v h="$head" 'BEGIN {printf "%.2f", (h - b) / b * 100}')
line="callgrind, 20,000 parses: base ($base_ref) $base Ir, head $head Ir, change ${pct}% (limit +${limit}%)"
echo "$line"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then echo "$line" >>"$GITHUB_STEP_SUMMARY"; fi

if awk -v p="$pct" -v l="$limit" 'BEGIN {exit !(p > l)}'; then
	echo "FAIL: parsing now takes more instructions than the base allows. If the increase is intended" \
		"(a new rule), say why in the pull request and add the label perf-ok." >&2
	exit 1
fi
