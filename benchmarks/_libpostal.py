"""libpostal timing for the speed and size benchmarks (issue 215, step 5).

libpostal runs in its own build folder and virtualenv (`tools/compare/compare_usaddress.py` explains how it is found), so the timing
is made by `tools/compare/libpostal_worker.py` in speed mode: each process loads the model, says READY, waits for GO, then parses its
share of the strings `reps` times and reports its fastest pass. With more than one process the strings are split in equal contiguous
parts and all processes start together, so the time of the run is the slowest process's fastest pass. One process is one thread; a
`parse_address` call holds the GIL, so processes are the way to use more cores, and every process loads its own copy of the model.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "compare"))
import compare_usaddress as C


def pss_mb(pid):
    """Proportional set size of a process in MB (a page shared by N processes counts 1/N to each), from /proc."""
    try:
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
            if line.startswith("Pss:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def bench(texts, procs=1, reps=5, home=None):
    """{"seconds", "procs", "load_seconds" (the slowest process), "rss_after_load_mb", "rss_peak_mb" (the largest process), "pss_total_mb" (all processes, models loaded, before parsing)}."""
    home = C.libpostal_home(home)
    py = os.path.join(home, "venv", "bin", "python")
    if not os.path.exists(py):
        sys.exit(f"no libpostal virtualenv at {home} (set LIBPOSTAL_HOME or --libpostal-home; see docs/libpostal-compat.md)")
    env = dict(os.environ, LD_LIBRARY_PATH=os.path.join(home, "install", "lib"))
    worker = str(ROOT / "tools" / "compare" / "libpostal_worker.py")
    size = -(-len(texts) // procs)
    parts = [texts[i * size : (i + 1) * size] for i in range(procs)]
    ps = []
    for part in parts:
        p = subprocess.Popen([py, "-I", worker], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True)
        p.stdin.write(json.dumps({"bench": reps, "strings": part}) + "\n")
        p.stdin.flush()
        ps.append(p)
    for p in ps:
        if p.stdout.readline().strip() != "READY":
            sys.exit("a libpostal worker did not start")
    pss = sum(pss_mb(p.pid) for p in ps)  # all models loaded, nothing parsing yet
    for p in ps:
        p.stdin.write("GO\n")
        p.stdin.flush()
    results = [json.loads(p.stdout.readline()) for p in ps]
    for p in ps:
        p.wait()
    return {
        "seconds": max(r["best_seconds"] for r in results),
        "procs": procs,
        "load_seconds": max(r["load_seconds"] for r in results),
        "rss_after_load_mb": max(r["rss_after_load_mb"] for r in results),
        "rss_peak_mb": max(r["rss_peak_mb"] for r in results),
        "pss_total_mb": pss,
    }
