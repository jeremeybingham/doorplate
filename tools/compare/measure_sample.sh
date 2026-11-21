#!/usr/bin/env bash
# The second half of the standard measurement for a parse-rule PR: the Netsyms sample runs of the base and the
# after build, `harness/compare.py`, and the cleanup of the base worktree and venv. Run it after
# measure_rule_pr.sh has finished, from the same checkout and commit:
#
#   job sample-NAME tools/compare/measure_sample.sh NAME
#
# It reads local-data/keycompare/measure-NAME/state.env. A sample run is cached by the key of its code
# (local-data/netsyms-runs/sample-KEY), so the base run is skipped when the last measurement's after build had the
# same code; then the job takes about 13 minutes, else about 27. If the job dies, run the same command again:
# `run.py` resumes a run with the same run id. Counts only.
set -euo pipefail

NAME=${1:?usage: measure_sample.sh NAME}
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
OUT=$ROOT/local-data/keycompare/measure-$NAME
BASE_WT=$ROOT/../doorplate-base-$NAME
BASE_VENV=$ROOT/../venv-base-$NAME
RUNS=$ROOT/local-data/netsyms-runs
[ -e "$OUT/state.env" ] || { echo "no $OUT/state.env: run measure_rule_pr.sh first"; exit 2; }
# shellcheck source=/dev/null
. "$OUT/state.env"
[ "$AFTER_COMMIT" = "$(git rev-parse HEAD)" ] || { echo "HEAD is not the measured commit $AFTER_COMMIT"; exit 2; }
BASE_RUN=sample-$BASE_KEY
AFTER_RUN=sample-$AFTER_KEY

step() { echo "##progress step=$1/3 label=$2"; }

step 1 "sample run, base (cached when the code is the same)"
if [ ! -e "$RUNS/$BASE_RUN/DONE" ]; then
  [ -x "$BASE_VENV/bin/python" ] || { echo "no base venv at $BASE_VENV: run measure_rule_pr.sh again"; exit 2; }
  (cd "$BASE_WT" && "$BASE_VENV/bin/python" -I tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id "$BASE_RUN" --confirm >>"$OUT/sample-base.log" 2>&1)
else
  echo "base sample run from the cache: $BASE_RUN"
fi

step 2 "sample run, after, and compare"
if [ ! -e "$RUNS/$AFTER_RUN/DONE" ]; then
  "$ROOT/../venv/bin/python" -I tools/harness/run.py --db local-data/netsyms-2026/sample.sqlite --table sample --run-id "$AFTER_RUN" --confirm >>"$OUT/sample-after.log" 2>&1
fi
"$ROOT/../venv/bin/python" -I tools/harness/compare.py "$BASE_RUN" "$AFTER_RUN" >"$OUT/sample-compare.txt" 2>&1 || true
head -45 "$OUT/sample-compare.txt"

step 3 "cleanup (base worktree and venv)"
[ ! -d "$BASE_WT" ] || git worktree remove --force "$BASE_WT"
rm -rf "$BASE_VENV"
echo "DONE: sample comparison in local-data/keycompare/measure-$NAME/sample-compare.txt"
