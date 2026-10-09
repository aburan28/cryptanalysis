#!/usr/bin/env python3
"""Bounded matched Sage/Singular Groebner controls for mixed and Boolean S4.

Supervisor uses the repository's checked Sage launcher for every worker.  The
two encodings use the same Sage ideal.groebner_basis entry point and fixed
target cells.  This is not an msolve F4 comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
LAUNCHER = HERE.parents[1] / "sage"


def worker(target_index: int, encoding: str):
    sys.path.insert(0, str(PRIOR))
    from sage.all import GF, PolynomialRing
    from boolean_core import ANFField
    from sage_probes import bits, candidate_x_points, curve, field, planted_targets
    K, modulus = field(19)
    E = curve(K)
    basis, points = candidate_x_points(E, K, 2)
    targets = planted_targets(points, 3, 12)
    Q, _ = targets[target_index]
    xq = Q[0]
    started = time.perf_counter_ns()
    if encoding.startswith("mixed"):
        R = PolynomialRing(K, names=[f"u{i}" for i in range(6)] + ["z"])
        u = R.gens()
        leaves = [sum((basis[j]*u[2*i+j] for j in range(2)), R(0))
                  for i in range(3)]
        z = u[-1]
        def s3(a, b, c):
            return (a*b+a*c+b*c)**2+a*b*c+1
        polys = [s3(leaves[0], leaves[1], z),
                 s3(z, leaves[2], xq)]
        polys += [v*v+v for v in u[:-1]]
        if encoding == "mixed_exact":
            polys.append(z**(2**19)+z)
    elif encoding == "boolean":
        R = PolynomialRing(GF(2), names=[f"w{i}" for i in range(25)])
        variables = R.gens()
        anf = ANFField(19, modulus)
        leaves = [anf.linear([2*i, 2*i+1], [bits(b) for b in basis])
                  for i in range(3)]
        middle = anf.linear(list(range(6, 25)), [1 << i for i in range(19)])
        eqs = anf.s3(leaves[0], leaves[1], middle)
        eqs += anf.s3(middle, leaves[2], anf.constant(bits(xq)))
        def as_sage(poly):
            result = R(0)
            for term in poly:
                value = R(1)
                while term:
                    bit = term & -term
                    value *= variables[bit.bit_length()-1]
                    term ^= bit
                result += value
            return result
        polys = [as_sage(eq) for eq in eqs if eq]
        polys += [v*v+v for v in variables]
    else:
        raise ValueError(encoding)
    built = time.perf_counter_ns()
    basis_result = R.ideal(polys).groebner_basis(algorithm="libsingular:std")
    finished = time.perf_counter_ns()
    result = {"target_index": target_index,
              "target_point": [bits(Q[0]), bits(Q[1])],
              "encoding": encoding, "variables": R.ngens(),
              "input_equations": len(polys),
              "maximum_input_degree": max(int(p.total_degree()) for p in polys),
              "basis_size": len(basis_result),
              "basis_maximum_degree": max((int(p.total_degree()) for p in basis_result),
                                          default=0),
              "build_ns_exploratory": built-started,
              "groebner_ns_exploratory": finished-built,
              "algorithm": "Sage ideal.groebner_basis(libsingular:std)"}
    print(json.dumps(result, sort_keys=True))


def supervise(args):
    if args.output.exists():
        raise FileExistsError(args.output)
    rows = []
    for index in args.target_indices:
        for encoding in ("mixed_unconstrained", "mixed_exact", "boolean"):
            command = [str(LAUNCHER), "-python", str(Path(__file__).resolve()),
                       "--worker", "--target-index", str(index),
                       "--encoding", encoding]
            started = time.perf_counter_ns()
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           timeout=args.limit_seconds, check=False)
                elapsed = time.perf_counter_ns()-started
                row = {"target_index": index, "encoding": encoding,
                       "supervisor_wall_ns_exploratory": elapsed,
                       "process_exit_code": completed.returncode,
                       "status": "completed" if completed.returncode == 0 else "error"}
                if completed.returncode == 0:
                    row.update(json.loads(completed.stdout.splitlines()[-1]))
                else:
                    row["stderr_tail"] = completed.stderr[-2000:]
            except subprocess.TimeoutExpired:
                row = {"target_index": index, "encoding": encoding,
                       "status": "timeout", "limit_seconds": args.limit_seconds,
                       "supervisor_wall_ns_exploratory":
                           time.perf_counter_ns()-started}
            rows.append(row)
            print(json.dumps({"target_index": index, "encoding": encoding,
                              "status": row["status"]}), flush=True)
            # Save each failure and timeout as soon as it occurs.
            result = {"schema_version": 1, "proposal_id": "G4",
                      "candidate_id": None, "run_id": None,
                      "field_degree": 19, "target_indices": args.target_indices,
                      "per_worker_limit_seconds": args.limit_seconds,
                      "rows": rows,
                      "scope": "matched Sage/Singular Groebner diagnostic; no msolve F4 performance or DLP claim",
                      "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "prior_sources_sha256": {
                          name: hashlib.sha256((PRIOR / name).read_bytes()).hexdigest()
                          for name in ("boolean_core.py", "sage_probes.py")}}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--target-index", type=int, default=0)
    parser.add_argument("--encoding", choices=("mixed_unconstrained",
                                                 "mixed_exact", "boolean"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--target-indices", type=int, nargs="+", default=[0, 2])
    parser.add_argument("--limit-seconds", type=int, default=90)
    args = parser.parse_args()
    if args.worker:
        worker(args.target_index, args.encoding)
    else:
        if args.output is None:
            parser.error("--output required for supervisor")
        supervise(args)


if __name__ == "__main__":
    main()
