#!/usr/bin/env bash
# The standard measurement for a parse-rule PR, in one go (CLAUDE.md, "For each parse-rule PR"):
#   1. the seven-source key dump (`key_diff.py dump-all --unit`) of the build before and the build after, and the diff;
#   2. the one-line city checks (`city_diff.py` on four geocode splits, `oneline_fl.py`), both builds;
#   3. the Netsyms sample runs and `harness/compare.py`.
# Counts only: nothing here prints a name or a street. Output goes to local-data/keycompare/ (git-ignored).
#
#   job measure-NAME tools/compare/measure_rule_pr.sh BASE_REF NAME [AFTER_REF]
#
# BASE_REF is the commit before the rule (origin/main, or the parent of the merge); AFTER_REF defaults to HEAD
# of this checkout. Run it from the repository root, with ../venv present (maturin, duckdb, pyarrow). The base
# build lives in a detached worktree ../doorplate-base-NAME with its own venv; both are deleted at the end, as
# are the dumps (the diff and the city and sample reports stay). Needs about 4 GB of disk and 10 to 15 minutes.
set -euo pipefail

BASE_REF=${1:?usage: measure_rule_pr.sh BASE_REF NAME [AFTER_REF]}
NAME=${2:?usage: measure_rule_pr.sh BASE_REF NAME [AFTER_REF]}
AFTER_REF=${3:-HEAD}
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
KC=$ROOT/local-data/keycompare
BASE_WT=$ROOT/../doorplate-base-$NAME
BASE_VENV=$ROOT/../venv-base-$NAME
OUT=$KC/measure-$NAME
mkdir -p "$OUT"

step() { echo "##progress step=$1/$TOTAL label=$2"; }
TOTAL=9

[ "$(git rev-parse "$AFTER_REF")" = "$(git rev-parse HEAD)" ] || { echo "AFTER_REF must be the checked-out commit"; exit 2; }
if [ -n "$(git status --porcelain)" ]; then echo "working tree not clean: commit or stash first"; exit 2; fi
df -h / /mnt/c | tail -2

step 1 "base worktree and venv"
git worktree add --detach "$BASE_WT" "$BASE_REF" >/dev/null
ln -s "$ROOT/local-data" "$BASE_WT/local-data"
uv venv -q "$BASE_VENV"
VIRTUAL_ENV=$BASE_VENV uv pip install -q -p "$BASE_VENV/bin/python" maturin duckdb pyarrow

step 2 "builds (base and after, the extension and the CLI)"
(
  export VIRTUAL_ENV=$BASE_VENV PATH=$BASE_VENV/bin:$PATH
  cd "$BASE_WT/crates/doorplate-py" && maturin develop --release >"$OUT/build-base-py.log" 2>&1
  cd "$BASE_WT" && cargo build --release -p doorplate-cli >"$OUT/build-base-cli.log" 2>&1
) &
P1=$!
(
  export VIRTUAL_ENV=$ROOT/../venv PATH=$ROOT/../venv/bin:$PATH
  cd "$ROOT/crates/doorplate-py" && maturin develop --release >"$OUT/build-after-py.log" 2>&1
  cd "$ROOT" && cargo build --release -p doorplate-cli >"$OUT/build-after-cli.log" 2>&1
) &
P2=$!
wait $P1 || { echo "base build failed"; exit 1; }
wait $P2 || { echo "after build failed"; exit 1; }
BASE_CLI=$BASE_WT/target/release/doorplate
AFTER_CLI=$ROOT/target/release/doorplate
"$BASE_VENV/bin/python" -I -c "import doorplate; print('base build', doorplate.__version__)"
"$ROOT/../venv/bin/python" -I -c "import doorplate; print('after build', doorplate.__version__)"

step 3 "key dumps (both builds at once)"
(cd "$BASE_WT" && "$BASE_VENV/bin/python" -I tools/compare/key_diff.py dump-all --unit --out "$KC/base-$NAME" >"$OUT/dump-base.log" 2>&1) &
D1=$!
("$ROOT/../venv/bin/python" -I tools/compare/key_diff.py dump-all --unit --out "$KC/after-$NAME" >"$OUT/dump-after.log" 2>&1) &
D2=$!
wait $D1 || { echo "base dump failed"; exit 1; }
wait $D2 || { echo "after dump failed"; exit 1; }

step 4 "key diff"
# a changed key makes the exit status non-zero: that is the result, not a failure
"$ROOT/../venv/bin/python" -I tools/compare/key_diff.py diff "$KC/base-$NAME" "$KC/after-$NAME" >"$KC/diff-$NAME.txt" 2>&1 || true
tail -40 "$KC/diff-$NAME.txt"

step 5 "city_diff on the geocode splits"
for split in train80 train20_heldout dev test; do
  "$ROOT/../venv/bin/python" -I tools/compare/city_diff.py "$BASE_CLI" "$AFTER_CLI" "$split" 2>&1 | tee -a "$OUT/city_diff.txt"
done

step 6 "oneline_fl, base then after"
for who in base after; do
  bin=$AFTER_CLI; [ $who = base ] && bin=$BASE_CLI
  echo "== $who" | tee -a "$OUT/oneline_fl.txt"
  "$ROOT/../venv/bin/python" -I tools/compare/oneline_fl.py --binary "$bin" 2>&1 | tee -a "$OUT/oneline_fl.txt"
done

step 7 "sample run, base"
(cd "$BASE_WT" && "$BASE_VENV/bin/python" -I tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id "sample-base-$NAME" --confirm >"$OUT/sample-base.log" 2>&1)
step 8 "sample run, after, and compare"
"$ROOT/../venv/bin/python" -I tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id "sample-after-$NAME" --confirm >"$OUT/sample-after.log" 2>&1
"$ROOT/../venv/bin/python" -I tools/harness/compare.py "sample-base-$NAME" "sample-after-$NAME" >"$OUT/sample-compare.txt" 2>&1 || true
head -45 "$OUT/sample-compare.txt"

step 9 "cleanup (worktree, venv, dumps)"
git worktree remove --force "$BASE_WT"
rm -rf "$BASE_VENV" "$KC/base-$NAME" "$KC/after-$NAME"
echo "DONE: diff in local-data/keycompare/diff-$NAME.txt, other reports in local-data/keycompare/measure-$NAME/"
