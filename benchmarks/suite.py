#!/usr/bin/env python3
"""The benchmark suite runner: doorplate and usaddress on the same labeled addresses.

    python benchmarks/suite.py compare   [--suite DIR] [--out FILE]   # token labels, both libraries
    python benchmarks/suite.py doorplate [--suite DIR] [--out FILE]   # fields, standardized output, keys, warnings
    python benchmarks/suite.py speed     [--suite DIR] [--out FILE]   # parsing speed and peak memory
    python benchmarks/suite.py all                                    # the three, one after the other

The specification is docs/benchmark-suite.md; `benchmarks/README.md` says how to run it. Build the
extension with `maturin develop --release` first and install usaddress (`pip install usaddress`).

The runner puts itself in the reference resource profile (4 logical CPUs and 8 GB of memory, on Linux): it
pins the CPU affinity, sets RAYON_NUM_THREADS=4 and an 8 GB address-space limit. The header says what it
got. `--no-profile` turns that off. The comparison track is scored with `tools/compare/compare_usaddress.py`'s
rules (token by token, by character span, street parts folded for the coarse score), and the doorplate-only
track is never mixed into a doorplate-versus-usaddress figure.

This library formats and parses; it does not validate that an address exists.
"""
import argparse
import collections
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "compare"))
SUITE = ROOT / "benchmarks" / "suite" / "v1"
PROFILE_CPUS, PROFILE_GB = 4, 8


# ---- the resource profile ------------------------------------------------------------------------------

def apply_profile(threads=PROFILE_CPUS):
    """Pin 4 CPUs, RAYON_NUM_THREADS and an 8 GB address-space limit. Must run before doorplate is imported."""
    os.environ["RAYON_NUM_THREADS"] = str(threads)
    note = []
    if hasattr(os, "sched_setaffinity"):
        allowed = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, set(allowed[:PROFILE_CPUS]))
    else:
        note.append("no CPU affinity on this system")
    try:
        import resource
        limit = PROFILE_GB * 1024**3
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ImportError, ValueError, OSError):
        note.append("no address-space limit on this system")
    return note


def cpu_model():
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown CPU"


def header(profile, notes):
    import doorplate
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    limit = "none"
    try:
        import resource
        soft = resource.getrlimit(resource.RLIMIT_AS)[0]
        limit = "none" if soft == resource.RLIM_INFINITY else f"{soft / 1024**3:.0f} GB"
    except ImportError:
        pass
    try:
        rust = subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip() or "rustc not found"
    except OSError:
        rust = "rustc not found"
    try:
        ua = importlib.metadata.version("usaddress")
    except importlib.metadata.PackageNotFoundError:
        ua = "not installed"
    files = {n: hashlib.sha256((SUITE_DIR / n).read_bytes()).hexdigest()[:12] for n in ("compare.jsonl.gz", "doorplate.jsonl.gz")
             if (SUITE_DIR / n).exists()}
    lines = [
        f"- CPU: {cpu_model()}; CPUs available to the runner: {cpus}; RAYON_NUM_THREADS={os.environ.get('RAYON_NUM_THREADS', 'unset')}",
        f"- Address-space limit: {limit}; profile: {'on (4 CPUs, 8 GB)' if profile else 'off'}"
        + (f" ({'; '.join(notes)})" if notes else ""),
        f"- OS: {platform.system()} {platform.release()}; Python {platform.python_version()}; {rust}",
        f"- doorplate {getattr(doorplate, '__version__', '?')}; usaddress {ua}",
        f"- Suite: {SUITE_DIR.name}; files {', '.join(f'{n} {h}' for n, h in files.items())}",
    ]
    return "\n".join(lines)


# ---- scoring helpers -----------------------------------------------------------------------------------

def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def cell(k, n):
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({100 * lo:.1f} to {100 * hi:.1f})"


def load(name):
    with gzip.open(SUITE_DIR / name, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def predict(lib, strings):
    import doorplate
    import usaddress
    out = []
    for s in strings:
        try:
            out.append(list(doorplate.parse_tokens(s)) if lib == "doorplate" else list(usaddress.parse(s)))
        except Exception:  # noqa: BLE001  (an input a library rejects scores as wrong, not as a crash)
            out.append([])
    return out


def score_record(rec, pred, lib, C):
    """(coarse_right, fine_right, tokens_right, tokens_total) for one record, by character span."""
    s = rec["input"]
    gold = rec["tokens"]
    g_spans = C.byte_spans(s, [t for t, _ in gold])
    p_spans = [(a[0], a[1], lab) for a, (_, lab) in zip(C.byte_spans(s, [t for t, _ in pred]), pred) if a]
    coarse_ok = fine_ok = True
    right = total = 0
    for (tok, gl), span in zip(gold, g_spans):
        if not C.scored(tok):
            continue
        g = C.norm(gl)
        p = C.norm(C.overlap_label(span, p_spans))
        handled = lib == "doorplate" and g == "CountryName" and p is None  # dropped on purpose, `country_ignored`
        total += 1
        if handled or C.coarse(g) == C.coarse(p):
            right += 1
        else:
            coarse_ok = False
        if not (handled or g == p):
            fine_ok = False
    return coarse_ok, fine_ok, right, total


# ---- the comparison track ------------------------------------------------------------------------------

def run_compare(args):
    import compare_usaddress as C
    recs = load("compare.jsonl.gz")
    if args.limit:
        recs = recs[: args.limit]
    inputs = [r["input"] for r in recs]
    t0 = time.time()
    preds = {lib: predict(lib, inputs) for lib in ("doorplate", "usaddress")}
    res = {lib: [score_record(r, p, lib, C) for r, p in zip(recs, preds[lib])] for lib in preds}
    shared = [not any(C.norm(l) in C.OUT_OF_SCOPE for _, l in r["tokens"]) for r in recs]
    n = len(recs)
    out = [f"## Comparison track: token labels ({n:,} records)", "",
           "Each record is scored by every token's label at its character span; a record is right only when every "
           "scored token is. Coarse folds the street parts into `StreetName`; fine does not. Intervals are 95% Wilson.", ""]

    def row(name, idx, fold):
        a = sum(res["doorplate"][i][fold] for i in idx)
        b = sum(res["usaddress"][i][fold] for i in idx)
        return f"| {name} | {len(idx):,} | {cell(a, len(idx))} | {cell(b, len(idx))} |"

    allidx = list(range(n))
    sharedidx = [i for i in allidx if shared[i]]
    nat = [i for i in allidx if recs[i]["stratum"] == "natural"]
    nat_shared = [i for i in nat if shared[i]]
    out += ["### Headline (coarse, whole record right)", "",
            "The mix is fixed in the specification: 80% `natural` (the estimate for ordinary input), 15% `hard` (the known blind "
            "spots of either library, drawn on purpose) and 5% `hand`. Read the stratum rows below for any one of them.", "",
            "| Records | Count | doorplate | usaddress |", "|---|---|---|---|",
            row("`natural` only, shared labels", nat_shared, 0), row("`natural` only, all records", nat, 0),
            row("Whole suite, shared labels (no label doorplate leaves unmodeled)", sharedidx, 0),
            row("Whole suite, all records", allidx, 0), "",
            "Fine (street parts kept apart):", "", "| Records | Count | doorplate | usaddress |", "|---|---|---|---|",
            row("`natural` only, shared labels", nat_shared, 1), row("`natural` only, all records", nat, 1),
            row("Whole suite, shared labels", sharedidx, 1), row("Whole suite, all records", allidx, 1), ""]
    tok = {lib: (sum(r[2] for r in res[lib]), sum(r[3] for r in res[lib])) for lib in res}
    out += [f"Tokens right (coarse): doorplate {cell(*tok['doorplate'])}, usaddress {cell(*tok['usaddress'])}.", ""]
    both = sum(1 for i in allidx if res["doorplate"][i][0] and res["usaddress"][i][0])
    only_d = sum(1 for i in allidx if res["doorplate"][i][0] and not res["usaddress"][i][0])
    only_u = sum(1 for i in allidx if not res["doorplate"][i][0] and res["usaddress"][i][0])
    out += ["### Paired (coarse, all records)", "", "| Both right | Only doorplate | Only usaddress | Both wrong |", "|---|---|---|---|",
            f"| {both:,} | {only_d:,} | {only_u:,} | {n - both - only_d - only_u:,} |", ""]

    def group(title, keyf):
        groups = collections.defaultdict(list)
        for i, r in enumerate(recs):
            for k in keyf(r):
                groups[k].append(i)
        lines = [f"### By {title}", "", "| Group | Count | doorplate | usaddress |", "|---|---|---|---|"]
        lines += [row(k, idx, 0) for k, idx in sorted(groups.items()) if len(idx) >= args.min_group]
        return lines + [""]

    out += group("stratum", lambda r: [r["stratum"]]) + group("style", lambda r: [r["style"]] if r.get("style") else [])
    out += group("address type", lambda r: [r["type"]]) + group("modifier", lambda r: r.get("mods") or ["(none)"])
    out += group("blind-spot class or hand shape", lambda r: r["tags"])
    text = "\n".join(out)
    print(text)
    print(f"\n_Compared in {time.time() - t0:.0f} seconds._")
    return text


# ---- the doorplate-only track --------------------------------------------------------------------------

COMPONENTS = ("street_number", "street_dir_prefix", "street_name", "street_suffix", "street_dir_suffix", "unit_type",
              "unit_number", "city", "state", "zip5", "zip4", "po_box", "rural_route", "military", "military_post_office",
              "general_delivery")


def components(p):
    got = {k: getattr(p, k, None) for k in COMPONENTS}
    got["general_delivery"] = True if got["general_delivery"] else None
    return {k: (v or None) for k, v in got.items()}


def run_doorplate(args):
    import doorplate
    recs = load("doorplate.jsonl.gz")
    if args.limit:
        recs = recs[: args.limit]
    scored = [r for r in recs if r.get("expect")]
    comp_right = collections.Counter()
    comp_total = collections.Counter()
    fields_ok, usps_ok, usps_n = {}, {}, 0
    warned = {True: [0, 0], False: [0, 0]}
    for r in scored:
        f = r["fields"]
        try:
            p = doorplate.parse_fields(line1=f["line1"], line2=f["line2"], city=f["city"], state=f["state"], zip=f["zip"])
        except Exception:  # noqa: BLE001
            fields_ok[r["id"]] = False
            continue
        got = components(p)
        want = {k: (r["expect"].get(k) or None) for k in COMPONENTS}
        ok = got == want
        fields_ok[r["id"]] = ok
        for k in COMPONENTS:
            if want[k] is not None:
                comp_total[k] += 1
                comp_right[k] += got[k] == want[k]
        warned[ok][0] += 1
        warned[ok][1] += bool(p.warnings)
        if r.get("usps"):
            usps_n += 1
            u = p.to_usps()
            delivery = " ".join(x for x in (u.get("line1"), u.get("line2")) if x)
            usps_ok[r["id"]] = delivery == r["usps"]["delivery"] and u.get("last_line") == r["usps"]["last"]
    n = len(scored)
    right = sum(fields_ok.values())
    out = [f"## doorplate-only track ({len(recs):,} records; {n:,} with Pub 28 components)", "",
           "No usaddress counterpart exists for these measures, and no figure here belongs in a doorplate-versus-usaddress "
           "table. The components come from the NAD columns and the Pub 28 tables, never from a parser; an absent component "
           "must be empty.", "",
           "### Fields input (`parse_fields`), whole record right", "", "| Group | Count | Right |", "|---|---|---|",
           f"| All | {n:,} | {cell(right, n)} |"]
    for key in ("stratum", "type"):
        groups = collections.defaultdict(list)
        for r in scored:
            groups[r[key]].append(fields_ok[r["id"]])
        out += [f"| {key} = {k} | {len(v):,} | {cell(sum(v), len(v))} |" for k, v in sorted(groups.items()) if len(v) >= args.min_group]
    out += ["", "| Component | Records with it | Right |", "|---|---|---|"]
    out += [f"| {k} | {comp_total[k]:,} | {cell(comp_right[k], comp_total[k])} |" for k in COMPONENTS if comp_total[k]]
    out += ["", "### Standardized output (`to_usps`)", "", f"Delivery line and last line both match on {cell(sum(usps_ok.values()), usps_n)} "
            f"of {usps_n:,} records that have a USPS expectation.", ""]

    stable = total_k = 0
    keys = collections.Counter()
    for r in recs:
        ins = r.get("inputs") or []
        if len(ins) < 2:
            continue
        ks = []
        for s in ins:
            try:
                ks.append(doorplate.parse(s).key())
            except Exception:  # noqa: BLE001
                ks.append(None)
        total_k += 1
        stable += len(set(ks)) == 1 and ks[0] is not None
        if ks[0]:
            keys[ks[0]] += 1
    collide = sum(v for v in keys.values() if v > 1)
    out += ["### Key stability (`k2`)", "", f"The same record written in two to four styles gives one key: {cell(stable, total_k)} of {total_k:,} records.",
            f"Records whose key is shared with a different record: {collide:,} of {sum(keys.values()):,} ({100 * collide / max(1, sum(keys.values())):.2f}%).", ""]
    out += ["### Warnings", "", "| Fields-input result | Records | Raised a warning |", "|---|---|---|",
            f"| Parsed wrong | {warned[False][0]:,} | {cell(warned[False][1], warned[False][0])} |",
            f"| Parsed right | {warned[True][0]:,} | {cell(warned[True][1], warned[True][0])} |", ""]
    text = "\n".join(out)
    print(text)
    return text


# ---- speed and memory ----------------------------------------------------------------------------------

def speed_worker(args):
    """One process, one thread count: print a JSON line of timings and peak memory."""
    import resource
    import doorplate
    recs = load("compare.jsonl.gz")
    inputs = [r["input"] for r in recs]
    if args.limit:
        inputs = inputs[: args.limit]

    def best(fn, runs=3):
        t = []
        for _ in range(runs):
            t0 = time.perf_counter()
            fn()
            t.append(time.perf_counter() - t0)
        return min(t)

    res = {"threads": int(os.environ["RAYON_NUM_THREADS"]), "n": len(inputs),
           "parse_many": best(lambda: doorplate.parse_many(inputs)),
           "parse_tokens": best(lambda: [doorplate.parse_tokens(s) for s in inputs])}
    if args.with_usaddress:
        import usaddress
        res["usaddress_parse"] = best(lambda: [usaddress.parse(s) for s in inputs])
    res["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(json.dumps(res))


def run_speed(args):
    rows = {}
    for threads in (1, PROFILE_CPUS):
        env = dict(os.environ, RAYON_NUM_THREADS=str(threads))
        cmd = [sys.executable, __file__, "_speed_worker", "--suite", str(SUITE_DIR)]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        if threads == 1:
            cmd.append("--with-usaddress")
        if args.no_profile:
            cmd.append("--no-profile")
        p = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if p.returncode:
            sys.exit(p.stderr)
        rows[threads] = json.loads(p.stdout.strip().splitlines()[-1])
    one, four = rows[1], rows[PROFILE_CPUS]
    n = one["n"]
    ps = lambda secs: f"{n / secs:,.0f}"
    out = [f"## Speed and memory ({n:,} strings; the best of 3 runs; 1 and {PROFILE_CPUS} threads, never all cores)", "",
           "| | Time | Strings per second | Relative to usaddress `parse` |", "|---|---|---|---|"]
    ua = one["usaddress_parse"]
    out += [f"| usaddress `parse` (1 thread; it has no batch call) | {ua:.2f} s | {ps(ua)} | 1.0x |",
            f"| doorplate `parse_tokens` (1 thread) | {one['parse_tokens']:.2f} s | {ps(one['parse_tokens'])} | {ua / one['parse_tokens']:.1f}x |",
            f"| doorplate `parse_many` (1 thread) | {one['parse_many']:.2f} s | {ps(one['parse_many'])} | {ua / one['parse_many']:.1f}x |",
            f"| doorplate `parse_many` ({PROFILE_CPUS} threads) | {four['parse_many']:.2f} s | {ps(four['parse_many'])} | {ua / four['parse_many']:.1f}x |",
            "", f"Peak resident memory: {one['peak_rss_mb']:.0f} MB (1 thread, usaddress loaded), {four['peak_rss_mb']:.0f} MB "
            f"({PROFILE_CPUS} threads, doorplate only). Accuracy does not depend on the profile; speed does, so read the ratios, not the "
            "absolute figures.", ""]
    text = "\n".join(out)
    print(text)
    return text


# ---- main ----------------------------------------------------------------------------------------------

def main():
    global SUITE_DIR
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("what", choices=["compare", "doorplate", "speed", "all", "_speed_worker"])
    ap.add_argument("--suite", type=Path, default=SUITE)
    ap.add_argument("--out", type=Path, help="also write the Markdown here")
    ap.add_argument("--limit", type=int, help="only the first N records (a quick test)")
    ap.add_argument("--min-group", type=int, default=30, help="smallest group to print in a breakdown")
    ap.add_argument("--no-profile", action="store_true", help="do not pin CPUs, threads or memory")
    ap.add_argument("--with-usaddress", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    SUITE_DIR = args.suite
    threads = int(os.environ.get("RAYON_NUM_THREADS", PROFILE_CPUS)) if args.what == "_speed_worker" else PROFILE_CPUS
    notes = [] if args.no_profile else apply_profile(threads)
    if args.what == "_speed_worker":
        return speed_worker(args)
    text = ["# Benchmark suite run", "", header(not args.no_profile, notes), ""]
    print("\n".join(text))
    parts = {"compare": run_compare, "doorplate": run_doorplate, "speed": run_speed}
    for name in (["compare", "doorplate", "speed"] if args.what == "all" else [args.what]):
        text.append(parts[name](args))
    if args.out:
        args.out.write_text("\n".join(text))


SUITE_DIR = SUITE

if __name__ == "__main__":
    main()
