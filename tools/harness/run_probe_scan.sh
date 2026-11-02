#!/usr/bin/env bash
# Start the unsampled probe scan (#465) in the foreground and say plainly when it ends.
#
#   tools/harness/run_probe_scan.sh INPUTS.txt RUN_ID [extra probe_scan.py options]
#
# Run it in a terminal you can leave (tmux): it prints the plan, runs the scan with --confirm, and ends with a banner
# (DONE, STOPPED or FAILED) and a terminal bell. A stopped or failed run resumes by running the same command again.
# Needs a go-ahead before it is started (docs/tools/harness.md); nothing here deletes anything.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${PYTHON:-$ROOT/../venv/bin/python}"
if [ "$#" -lt 2 ]; then
    echo "usage: $0 INPUTS.txt RUN_ID [probe_scan.py options]" >&2
    exit 2
fi
INPUTS="$1"
RUN_ID="$2"
shift 2
cd "$ROOT" || exit 2
RUN_DIR="local-data/probe-scan/$RUN_ID"
banner() {
    printf '\a\n==============================================================\n'
    printf '  PROBE SCAN %s  (%s)\n' "$1" "$RUN_ID"
    printf '  %s\n' "$2"
    printf '==============================================================\n'
}
if [ -n "$(git status --porcelain)" ]; then
    echo "note: the working tree has uncommitted changes; the manifest records that"
fi
START=$(date +%s)
"$PY" -I tools/harness/probe_scan.py "$INPUTS" --run-id "$RUN_ID" "$@" --confirm
STATUS=$?
MINUTES=$((($(date +%s) - START) / 60))
if [ "$STATUS" -eq 0 ] && [ -e "$RUN_DIR/DONE" ]; then
    banner DONE "after ${MINUTES} min. Counts: $RUN_DIR/summary.json. Tell Claude: the run id is $RUN_ID."
elif [ "$STATUS" -eq 3 ]; then
    banner "STOPPED OR HAD ERRORS" "after ${MINUTES} min. Run the same command again to resume. Log: $RUN_DIR/progress.log"
else
    banner FAILED "exit status $STATUS after ${MINUTES} min. The plan was refused or the tool crashed; read the lines above."
fi
exit "$STATUS"
