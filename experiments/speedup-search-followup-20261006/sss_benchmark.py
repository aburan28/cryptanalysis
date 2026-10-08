"""Five-fixture Smooth Subsum Search positive control.

Question.  Does an existing *collision-generated* smoothness-candidate
collector (Hittmeir's SSS, 2023) beat scanning sieves on matched inputs?
This is the positive control for the "construct smoothness-correlated
candidates without scanning the whole interval" behaviour the AVW lead was
looking for, and the comparator any theorem-based proposal must beat.  It
predates AVW and is not a new asymptotic result.

Protocol (frozen before running).
  * Upstream: https://github.com/sbaresearch/smoothsubsumsearch at the pinned
    revision PINNED_REV, cloned into a cache directory at run time.  It is not
    vendored because the repository exposes no license file; the SHA-256 of
    every upstream file imported is recorded instead.
  * Comparators: the pSIQS (primefac) and SymPy SIQS scripts *bundled in that
    repository* (psiqs.py, ssiqs.py), with the parameter table of its test.py.
  * Fixtures: five 30-digit semiprimes drawn by the same law as upstream
    test.py (p in [1e14, 5e14], q in [5e14, 2.5e15], both prime, |N| = 30
    digits) from a fixed seed, written to results/sss/fixtures.json.
  * Every (algorithm, fixture) pair runs in a fresh process; import time is
    excluded; algorithm order rotates per fixture.
  * Verification: parsed factors must multiply to N, be nontrivial and prime.
    A run with no verified factorisation is kept as a row and excluded from
    the ratio.
  * Metric: per-fixture wall time, five-fixture total, geometric mean of the
    per-fixture ratio to SSS.  Wall time on a shared 4-vCPU cloud VM; this is
    a bounded comparison of Python implementations, labelled as such.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time

import math
import statistics

from sympy import isprime, nextprime

from hardware_manifest import collect, proc_stat_snapshot, steal_delta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "results", "sss")
UPSTREAM_URL = "https://github.com/sbaresearch/smoothsubsumsearch"
PINNED_REV = "8dbaf6d39ab88a40380965d25ec2c363d7f27358"
CACHE = os.environ.get("SSS_UPSTREAM_DIR", os.path.join(tempfile.gettempdir(), "sss-upstream-" + PINNED_REV[:12]))
ALGORITHMS = ["sss", "psiqs", "ssiqs"]
FIXTURE_SEED = 20261006
REPS = 3
DIGITS = 30


def ensure_upstream() -> dict:
    if not os.path.isdir(os.path.join(CACHE, ".git")):
        subprocess.run(["git", "clone", "-q", UPSTREAM_URL, CACHE], check=True)
    subprocess.run(["git", "-C", CACHE, "checkout", "-q", PINNED_REV], check=True)
    head = subprocess.run(["git", "-C", CACHE, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    assert head == PINNED_REV, head
    files = ["sssif/sss.py", "sssif/mstep.py", "psiqs.py", "ssiqs.py", "test.py"]
    return {
        "url": UPSTREAM_URL,
        "revision": head,
        "file_sha256": {f: hashlib.sha256(open(os.path.join(CACHE, f), "rb").read()).hexdigest() for f in files},
        "license_note": "upstream repository exposes no license file; code is fetched at run time, not vendored",
    }


def fixtures() -> list[int]:
    path = os.path.join(OUT_DIR, "fixtures.json")
    if os.path.exists(path):
        return json.load(open(path))["N"]
    import random

    rng = random.Random(FIXTURE_SEED)
    out = []
    l, u = 10 ** (DIGITS // 2 - 1), 5 * 10 ** (DIGITS // 2 - 1)
    while len(out) < 5:
        p = nextprime(rng.randint(l, u))
        q = nextprime(rng.randint(5 * l, 5 * u))
        N = p * q
        if len(str(N)) == DIGITS and N not in out and p != q:
            out.append(N)
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(
        {
            "digits": DIGITS,
            "law": "p = nextprime(U[1e14,5e14]), q = nextprime(U[5e14,2.5e15]), |N| = 30 digits (upstream test.py ranges)",
            "seed": FIXTURE_SEED,
            "N": out,
        },
        open(path, "w"),
        indent=1,
    )
    return out


def run_one(alg: str, N: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        out_path = tf.name
    try:
        before = proc_stat_snapshot()
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "sss_runner.py"), CACHE, alg, str(N), out_path],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        rec = json.load(open(out_path)) if os.path.exists(out_path) and os.path.getsize(out_path) else {"algorithm": alg, "N": N, "elapsed_s": None, "factors": None, "returncode": proc.returncode}
        rec["stderr_tail"] = proc.stderr[-400:]
        rec["host_during_run"] = steal_delta(before, proc_stat_snapshot())
    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)
    f = rec.get("factors")
    rec["verified"] = bool(f) and f[0] * f[1] == N and 1 < f[0] < N and isprime(f[0]) and isprime(f[1])
    return rec


def versions() -> dict:
    import gmpy2
    import numpy
    import sympy

    try:
        import primefac

        pf = getattr(primefac, "__version__", "installed (bundled psiqs.py is what runs)")
    except Exception:
        pf = None
    return {
        "python": platform.python_version(),
        "gmpy2": gmpy2.version(),
        "sympy": sympy.__version__,
        "numpy": numpy.__version__,
        "primefac_pip": pf,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    upstream = ensure_upstream()
    Ns = fixtures()
    rows = []
    for rep in range(REPS):
        for i, N in enumerate(Ns):
            k = (i + rep) % 3
            order = ALGORITHMS[k:] + ALGORITHMS[:k]
            for alg in order:
                t = time.time()
                rec = run_one(alg, N)
                rec["fixture_index"] = i
                rec["repetition"] = rep
                rec["order_in_fixture"] = order.index(alg)
                rows.append(rec)
                print(f"rep {rep} fixture {i} {alg:6s}: {rec['elapsed_s']!s:>10} s  verified={rec['verified']}  (wall incl. launch {time.time()-t:.1f}s)", flush=True)
                with open(os.path.join(OUT_DIR, f"run_r{rep}_f{i}_{alg}.json"), "w") as fh:
                    json.dump(rec, fh, indent=1)
    # Per-fixture statistic is the median over repetitions of verified runs;
    # a fixture with any unverified repetition is reported but excluded.
    summary = {}
    med = {}
    for alg in ALGORITHMS:
        med[alg] = {}
        for i in range(len(Ns)):
            runs = [r for r in rows if r["algorithm"] == alg and r["fixture_index"] == i]
            if all(r["verified"] for r in runs):
                med[alg][i] = statistics.median(r["elapsed_s"] for r in runs)
    for alg in ALGORITHMS:
        ok = [r for r in rows if r["algorithm"] == alg and r["verified"]]
        complete = len(med[alg]) == len(Ns) and len(med["sss"]) == len(Ns)
        total = sum(med[alg].values())
        ratios = [med[alg][i] / med["sss"][i] for i in med[alg] if i in med["sss"]]
        gm = math.prod(ratios) ** (1 / len(ratios)) if ratios else None
        summary[alg] = {
            "verified_runs": f"{len(ok)}/{len(Ns) * REPS}",
            "five_fixture_total_of_medians_s": round(total, 3) if complete else None,
            "geometric_mean_ratio_to_sss": round(gm, 3) if gm and complete else None,
            "per_fixture_median_s": [round(med[alg][i], 4) for i in sorted(med[alg])],
            "per_fixture_min_s": [round(min(r["elapsed_s"] for r in rows if r["algorithm"] == alg and r["fixture_index"] == i and r["verified"]), 4) for i in range(len(Ns))],
            "per_fixture_max_s": [round(max(r["elapsed_s"] for r in rows if r["algorithm"] == alg and r["fixture_index"] == i and r["verified"]), 4) for i in range(len(Ns))],
            "per_fixture_median_process_cpu_s": [round(statistics.median(r["process_cpu_s"] for r in rows if r["algorithm"] == alg and r["fixture_index"] == i and r["verified"]), 4) for i in range(len(Ns))],
            "peak_rss_kB_max": max(r["peak_rss_kB"] for r in ok) if ok else None,
            "steal_fraction_max_during_runs": max((r["host_during_run"]["steal_fraction"] or 0.0) for r in ok) if ok else None,
        }
    result = {
        "protocol": f"see module docstring; one fresh process per (algorithm, fixture, repetition), {REPS} repetitions; import excluded; order rotated per fixture and repetition; per-fixture statistic = median",
        "upstream": upstream,
        "versions": versions(),
        "hardware_manifest": collect(),
        "execution": {"threads": 1, "affinity": "inherited (not pinned)", "process_per_run": True, "warmup": "none; import excluded, first call timed", "pairing": "same fixtures, same host, order rotated per (fixture, repetition)", "censored_runs": 0},
        "fixtures": Ns,
        "summary": summary,
        "rows": rows,
        "claim_boundary": "bounded wall-clock comparison of Python implementations on a shared cloud VM; not an asymptotic statement and not an AVW result",
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as fh:
        json.dump(result, fh, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
