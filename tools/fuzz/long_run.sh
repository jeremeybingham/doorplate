#!/usr/bin/env bash
# Long unattended fuzz run of both targets in fuzz/, side by side.
#
# Usage: tools/fuzz/long_run.sh [HOURS] [WORKERS_PER_TARGET]
#   HOURS               fuzzing time per target (default 5; both run at once)
#   WORKERS_PER_TARGET  libFuzzer -fork workers (default: half the cores, minus one)
#
# Everything lands in fuzz/runs/<UTC time>/ (git-ignored): the libFuzzer logs,
# the crash/timeout/oom inputs, a replay of each one and summary.md. The
# corpus in fuzz/corpus/<target> grows across runs; seeds come from the golden
# corpus (tools/fuzz/seed.py). Needs nightly and cargo-fuzz.
set -uo pipefail

hours=${1:-5}
cores=$(nproc)
workers=${2:-$(( cores / 2 > 1 ? cores / 2 - 1 : 1 ))}
seconds=$(awk -v h="$hours" 'BEGIN { printf "%d", h * 3600 }')
targets=(parse parse_fields)
flags=(-max_len=512 -timeout=10 -rss_limit_mb=2048 -print_final_stats=1
       -ignore_crashes=1 -ignore_timeouts=1 -ignore_ooms=1)

root=$(cd "$(dirname "$0")/../.." && pwd)
fuzz="$root/fuzz"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
run="$fuzz/runs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$run"
cd "$fuzz" || exit 1

log() { echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$run/progress.log"; }
count() { find "$1" -maxdepth 1 -type f 2>/dev/null | wc -l; }

log "run dir $run; $hours h ($seconds s) per target, $workers workers each, $cores cores"
python3 "$root/tools/fuzz/seed.py" "$run/seeds" | tee -a "$run/progress.log"
log "building targets"
if ! cargo +nightly fuzz build >"$run/build.log" 2>&1; then
    log "build failed; see $run/build.log"
    exit 1
fi

declare -A before pids
for t in "${targets[@]}"; do
    mkdir -p "corpus/$t" "$run/$t/artifacts"
    before[$t]=$(count "corpus/$t")
    log "starting $t (corpus ${before[$t]} files)"
    # A hard stop 15 minutes past the libFuzzer limit, in case a worker hangs.
    timeout --signal=INT --kill-after=60 $(( seconds + 900 )) \
        cargo +nightly fuzz run "$t" "corpus/$t" "$run/seeds/$t" -- \
        -fork="$workers" -max_total_time="$seconds" "${flags[@]}" \
        -artifact_prefix="$run/$t/artifacts/" \
        >"$run/$t/fuzz.log" 2>&1 &
    pids[$t]=$!
done

declare -A status
for t in "${targets[@]}"; do
    wait "${pids[$t]}"
    status[$t]=$?
    log "$t exited with status ${status[$t]}"
done

# Replay each saved input once so the panic message and backtrace are on disk.
for t in "${targets[@]}"; do
    mkdir -p "$run/$t/replay"
    for a in "$run/$t/artifacts"/*; do
        [ -f "$a" ] || continue
        name=$(basename "$a")
        {
            echo "== bytes"
            python3 -c 'import sys; print(repr(open(sys.argv[1], "rb").read()))' "$a"
            echo "== input (cargo fuzz fmt)"
            cargo +nightly fuzz fmt "$t" "$a" 2>&1
            echo "== replay"
            RUST_BACKTRACE=1 timeout 120 cargo +nightly fuzz run "$t" "$a" -- -runs=1 2>&1
        } >"$run/$t/replay/$name.txt"
    done
done

{
    echo "# Fuzz run $(basename "$run")"
    echo
    echo "- commit: $(git -C "$root" rev-parse HEAD)$(git -C "$root" diff --quiet HEAD || echo ' (dirty)')"
    echo "- toolchain: $(rustc +nightly --version); $(cargo fuzz --version)"
    echo "- machine: $cores cores, $workers fork workers per target"
    echo "- time per target: $hours h ($seconds s)"
    echo "- flags: ${flags[*]}"
    echo "- started: $started; finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    for t in "${targets[@]}"; do
        echo
        echo "## $t"
        echo
        echo "- exit status: ${status[$t]}"
        echo "- corpus files: ${before[$t]} before, $(count "corpus/$t") after"
        for kind in crash timeout oom slow-unit leak; do
            n=$(find "$run/$t/artifacts" -name "$kind-*" | wc -l)
            echo "- $kind inputs: $n"
        done
        echo
        echo "Last status lines:"
        echo
        echo '```'
        grep -E '^#[0-9]+:' "$run/$t/fuzz.log" | tail -3
        grep -E '^(stat::|INFO: exiting|==[0-9]+== (ERROR|libFuzzer))' "$run/$t/fuzz.log" | tail -12
        echo '```'
        for r in "$run/$t/replay"/*.txt; do
            [ -f "$r" ] || continue
            echo
            echo "### $(basename "$r" .txt)"
            echo
            echo '```'
            sed -n '2p' "$r"
            grep -m1 -A1 'panicked at' "$r"
            grep -m1 -E 'ERROR: libFuzzer|SUMMARY' "$r"
            echo '```'
        done
    done
} >"$run/summary.md"

log "done; summary in $run/summary.md"
