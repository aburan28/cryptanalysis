"""Bounded same-host comparison with Sage/PolyBoRi on the same GB contract."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def workloads():
    cases = [dict(c) for c in json.loads((HERE.parent / "fixtures.json").read_text()) if c["nvars"] == 12]
    rng = random.Random(2026092403)
    for n in (12, 16, 20):
        planted = rng.randrange(1 << n)
        support = [0] + [1 << i for i in range(n)] + [1 << i | 1 << j for i in range(n) for j in range(i)]
        equations = []
        for _ in range(n):
            g = {m for m in support if rng.randrange(2)}
            if sum((m & planted) == m for m in g) % 2:
                g.symmetric_difference_update((0,))
            equations.append(sorted(g))
        cases.append({"name": f"planted-dense-mq-{n}", "nvars": n, "equations": equations,
                      "planted": planted, "seed": 2026092403})
    return cases


def child(index):
    from sage.all import BooleanPolynomialRing, GF, PolynomialRing
    c = json.loads((HERE / "external-fixtures.json").read_text())[index]
    n, equations = c["nvars"], c["equations"]
    ring = BooleanPolynomialRing(n, "x", order="degrevlex")
    x = ring.gens()
    def poly(g):
        p = ring.zero()
        for m in g:
            term = ring.one()
            for i in range(n):
                if m & (1 << i):
                    term *= x[i]
            p += term
        return p
    polynomials = [poly(g) for g in equations]
    data = f"{n} {len(equations)} 0 0\n" + "".join(f'{len(g)} {" ".join(map(str,g))}\n' for g in equations)
    raw = subprocess.run([str(HERE / "build/boolean-dual")], input=data, text=True,
                         capture_output=True, check=True, timeout=15, env=dict(os.environ, GB_BENCH_INNER="31"))
    candidate = sorted(list(map(int, row.split()))[1:] for row in raw.stdout.splitlines()[1:])
    samples = []
    cpu_samples = []
    for _ in range(5):
        start, cpu = time.perf_counter(), time.process_time()
        basis = ring.ideal(polynomials).groebner_basis()
        cpu_samples.append(time.process_time()-cpu)
        samples.append(time.perf_counter()-start)
    # Convert by variable NAME. Boolean monomial iteration order is not a
    # reliable variable-to-bit map across Sage monomial orderings.
    ordinary = PolynomialRing(GF(2), n, names="x", order="degrevlex")
    expected = []
    for g in basis:
        p = ordinary(str(g))
        expected.append(sorted(sum(1 << i for i,e in enumerate(powers) if e) for powers in p.dict()))
    expected.sort()
    assert candidate == expected, (c["name"], candidate, expected)
    return {"name": c["name"], "nvars": n, "status": "verified", "canonical_basis_equal": True,
            "polybori_seconds": samples, "polybori_cpu_seconds": cpu_samples,
            "polybori_median_seconds": statistics.median(samples),
            "polybori_median_cpu_seconds": statistics.median(cpu_samples),
            "dual_seconds": float(raw.stdout.splitlines()[0].split()[2]),
            "dual_metrics": json.loads(raw.stderr),
            "basis_sha256": hashlib.sha256(json.dumps(candidate).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", type=int)
    args = parser.parse_args()
    if args.child is not None:
        print(json.dumps(child(args.child)))
        return
    cases = workloads()
    corpus = HERE / "external-fixtures.json"
    corpus.write_text(json.dumps(cases, indent=2) + "\n")
    report = {"scope": "Boolean reduced grevlex basis only, ring/input construction and process startup excluded; fresh PolyBoRi ideals in a resident ring; 5 repeated solves, internal caches not flushed; serial solver comparisons",
              "claim": "Exploratory same-machine external comparison; not a global ranking or high-regularity claim",
              "child_limit_seconds": 30, "load_at_start": os.getloadavg(), "cells": [],
              "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest()}
    for i, c in enumerate(cases):
        start = time.perf_counter()
        try:
            run = subprocess.run(["sage", "-python", str(Path(__file__).resolve()), "--child", str(i)],
                                 text=True, capture_output=True, timeout=30)
            if run.returncode:
                value = {"name": c["name"], "status": "error", "returncode": run.returncode,
                         "stderr": run.stderr[-3000:]}
            else:
                value = json.loads(run.stdout)
        except subprocess.TimeoutExpired:
            value = {"name": c["name"], "status": "timeout", "censored": True, "limit_seconds": 30}
        value["child_wall_seconds"] = time.perf_counter() - start
        report["cells"].append(value)
        (HERE / "results/external-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
        print(c["name"], value["status"], flush=True)


if __name__ == "__main__":
    main()
