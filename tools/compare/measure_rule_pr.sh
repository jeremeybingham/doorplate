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
# are the base dump and the base sample run when they are not cached. Needs about 4 GB of disk and 10 to 15 minutes.
#
# Baseline cache: the dump and the Netsyms sample run of a build are kept under a key of its code (the `crates`
# tree and Cargo.lock), in local-data/keycompare/cache/ (the last two dumps) and local-data/netsyms-runs/
# (`sample-KEY`). The next run uses them as its base when BASE_REF has the same key, which is so when main has
# not changed since, except to merge the rule that was measured (a merge of the same code has the same key).
# Any other change to the code under crates/ gives another key and the base is dumped and run again.
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
CACHE=$KC/cache
mkdir -p "$OUT" "$CACHE"

# A key of the code a build is made of (what the dump and the sample run depend on).
code_key() { { git rev-parse "$1:crates"; git rev-parse "$1:Cargo.lock"; } | sha1sum | cut -c1-12; }
BASE_KEY=$(code_key "$BASE_REF")
AFTER_KEY=$(code_key "$AFTER_REF")
BASE_DUMP=$CACHE/dump-$BASE_KEY
AFTER_DUMP=$CACHE/dump-$AFTER_KEY
BASE_RUN=sample-$BASE_KEY
AFTER_RUN=sample-$AFTER_KEY
RUNS=$ROOT/local-data/netsyms-runs
[ -e "$BASE_DUMP/.done" ] && CACHED_DUMP=1 || CACHED_DUMP=0
[ -e "$RUNS/$BASE_RUN/DONE" ] && CACHED_RUN=1 || CACHED_RUN=0
echo "base key $BASE_KEY (dump cached: $CACHED_DUMP, sample run cached: $CACHED_RUN); after key $AFTER_KEY"

step() { echo "##progress step=$1/$TOTAL label=$2"; }
TOTAL=9

[ "$(git rev-parse "$AFTER_REF")" = "$(git rev-parse HEAD)" ] || { echo "AFTER_REF must be the checked-out commit"; exit 2; }
if [ -n "$(git status --porcelain)" ]; then echo "working tree not clean: commit or stash first"; exit 2; fi
df -h / /mnt/c | tail -2

step 1 "base worktree and venv"
git worktree add --detach "$BASE_WT" "$BASE_REF" >/dev/null
ln -s "$ROOT/local-data" "$BASE_WT/local-data"
NEED_BASE_PY=0
[ $CACHED_DUMP = 0 ] || [ $CACHED_RUN = 0 ] && NEED_BASE_PY=1
if [ $NEED_BASE_PY = 1 ]; then
  uv venv -q "$BASE_VENV"
  VIRTUAL_ENV=$BASE_VENV uv pip install -q -p "$BASE_VENV/bin/python" maturin duckdb pyarrow
fi

step 2 "builds (base and after, the extension and the CLI)"
(
  if [ $NEED_BASE_PY = 1 ]; then
    export VIRTUAL_ENV=$BASE_VENV PATH=$BASE_VENV/bin:$PATH
    cd "$BASE_WT/crates/doorplate-py" && maturin develop --release >"$OUT/build-base-py.log" 2>&1
  fi
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
[ $NEED_BASE_PY = 0 ] || "$BASE_VENV/bin/python" -I -c "import doorplate; print('base build', doorplate.__version__)"
"$ROOT/../venv/bin/python" -I -c "import doorplate; print('after build', doorplate.__version__)"

step 3 "key dumps (the base from the cache when the code is the same)"
D1=
if [ $CACHED_DUMP = 0 ]; then
  rm -rf "$BASE_DUMP"
  (cd "$BASE_WT" && "$BASE_VENV/bin/python" -I tools/compare/key_diff.py dump-all --unit --out "$BASE_DUMP" >"$OUT/dump-base.log" 2>&1 && touch "$BASE_DUMP/.done") &
  D1=$!
else
  echo "base dump from the cache: $BASE_DUMP"
fi
D2=
if [ ! -e "$AFTER_DUMP/.done" ]; then
  rm -rf "$AFTER_DUMP"
  ("$ROOT/../venv/bin/python" -I tools/compare/key_diff.py dump-all --unit --out "$AFTER_DUMP" >"$OUT/dump-after.log" 2>&1 && touch "$AFTER_DUMP/.done") &
  D2=$!
fi
[ -z "$D1" ] || wait $D1 || { echo "base dump failed"; exit 1; }
[ -z "$D2" ] || wait $D2 || { echo "after dump failed"; exit 1; }

step 4 "key diff"
# a changed key makes the exit status non-zero: that is the result, not a failure
"$ROOT/../venv/bin/python" -I tools/compare/key_diff.py diff "$BASE_DUMP" "$AFTER_DUMP" >"$KC/diff-$NAME.txt" 2>&1 || true
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

step 7 "sample run, base (cached when the code is the same)"
if [ $CACHED_RUN = 0 ]; then
  (cd "$BASE_WT" && "$BASE_VENV/bin/python" -I tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id "$BASE_RUN" --confirm >"$OUT/sample-base.log" 2>&1)
else
  echo "base sample run from the cache: $BASE_RUN"
fi
step 8 "sample run, after, and compare"
if [ ! -e "$RUNS/$AFTER_RUN/DONE" ]; then
  "$ROOT/../venv/bin/python" -I tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id "$AFTER_RUN" --confirm >"$OUT/sample-after.log" 2>&1
fi
"$ROOT/../venv/bin/python" -I tools/harness/compare.py "$BASE_RUN" "$AFTER_RUN" >"$OUT/sample-compare.txt" 2>&1 || true
head -45 "$OUT/sample-compare.txt"

step 9 "cleanup (worktree, venv; the base and after dumps stay as the cache, the last two)"
git worktree remove --force "$BASE_WT"
rm -rf "$BASE_VENV"
# keep the two newest dumps (the after dump of this run is the next run's base)
ls -1dt "$CACHE"/dump-* 2>/dev/null | tail -n +3 | xargs -r rm -rf
echo "DONE: diff in local-data/keycompare/diff-$NAME.txt, other reports in local-data/keycompare/measure-$NAME/"
