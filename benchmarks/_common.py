"""Shared helpers for the benchmark scripts."""
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "target" / "release" / "doorplate"
GEOCODE = ROOT / "local-data" / "geocode-benchmark"


def usable_cpus():
    """CPUs this process may use: the affinity mask when there is one (taskset, the suite runner), else all."""
    return len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()


def machine():
    """One line: CPU, cores, RAM, OS, Python, Rust."""
    cpu = "unknown CPU"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        cpu = platform.processor() or cpu
    ram = ""
    try:
        kb = int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1))
        ram = f", {kb / 1048576:.0f} GB RAM"
    except (OSError, AttributeError):
        pass
    try:
        rust = subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()
    except OSError:
        rust = "rustc not found"
    return (f"{cpu}, {usable_cpus()} threads{ram}; {platform.system()} {platform.release()}; "
            f"Python {platform.python_version()}; {rust}")


def corpus_inputs():
    """The single-line inputs of the golden corpus (committed, invented)."""
    out = []
    for path in sorted((ROOT / "tests" / "corpus").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                s = json.loads(line).get("input")
                if s:
                    out.append(s)
    return out


def geocode_inputs():
    """The geocode benchmark's addresses as one-line strings, or [] if absent.
    The file is IOB-labeled: `TOKEN LABEL` lines, one blank line between
    addresses, `-END-` closing each."""
    path = GEOCODE / "test.txt"
    if not path.exists():
        return []
    out, cur = [], []
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts or parts[0] == "-END-":
            if cur:
                out.append(" ".join(cur))
                cur = []
            continue
        cur.append(parts[0])
    if cur:
        out.append(" ".join(cur))
    return out


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, **kw).stdout


def best(fn, runs=5):
    import time

    times = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    return min(times)


# ---- the usaddress cache ---------------------------------------------------------------------------------
# usaddress does not change between runs of this repository's benchmarks, and timing it is most of a run. With
# the cache switched on (--cache-usaddress, in speed_python.py and suite.py) a usaddress result is reused when
# the usaddress version, the inputs and (for a timing) the machine are the same, and is stored when it is not.
# Delete the file to start again. Timings are only reused on the machine that made them.

USADDRESS_CACHE = ROOT / "local-data" / "benchmarks" / "usaddress-cache.json"


def usaddress_version():
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("usaddress")
    except PackageNotFoundError:
        return None


def machine_id():
    """The CPU model, the CPUs this process may use and the OS: what a stored timing belongs to."""
    cpu = "unknown CPU"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        cpu = platform.processor() or cpu
    return f"{cpu}; {usable_cpus()} threads; {platform.system()}"


def inputs_id(texts):
    """A short fingerprint of a list of input strings."""
    import hashlib

    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode("utf-8", "replace"))
        h.update(b"\n")
    return f"{len(texts)}:{h.hexdigest()[:16]}"


def cache_get(key, timing, path=None):
    """(value, stamp) of a stored usaddress result, or None. A timing also needs the same machine."""
    path = path or USADDRESS_CACHE
    try:
        entry = json.loads(path.read_text()).get(key)
    except (OSError, ValueError):
        return None
    if not entry or entry.get("usaddress") != usaddress_version():
        return None
    if timing and entry.get("machine") != machine_id():
        return None
    return entry["value"], entry.get("stamp", "an earlier run")


def cache_put(key, value, timing, path=None):
    import datetime

    path = path or USADDRESS_CACHE
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    data[key] = {"value": value, "usaddress": usaddress_version(), "stamp": datetime.date.today().isoformat(),
                 "machine": machine_id() if timing else None}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def need_cli():
    if not CLI.exists():
        sys.exit(f"{CLI} not found: cargo build --release -p doorplate-cli")
