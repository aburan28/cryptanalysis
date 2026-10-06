#!/usr/bin/env python3
"""PDP2ht on the factor base of the repository's F4 above-limit IC1 runs (f4-gpu-20260925).

Rebuilds `IC1N23Cka1fb2071PDP2f4...`'s factor base: on y^2 + xy = x^3 + x^2 + 1 over
F_2[z]/(z^23 + z^5 + 1), the kernel of g(tau) for irreducible factor 0 of x^23 - 1 (degree 11,
Frobenius-stable, 2071 geometric points, 45 effective columns). Here d = 10, above the limit
(n + 2)/3 = 8.3. The script then:

- checks PDP2ht (Python half-trace solver) and the C enumeration against the exact pair table on
  ordinary targets and on planted (decomposable) targets;
- times both per attempt on ordinary subgroup targets (the C path both with a Python projection
  per target and as whole C attempts, ht_attempt_batch), for comparison with the F4 arms' recorded
  PDP wall per attempt in ../f4-gpu-20260925/runs.jsonl (same VM class, one core).

The F4 runs drew their queries from Rust's StdRng, which is not reproduced here, so the
comparison is on the same curve, factor base and query law, not the same query points.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pdp-degree-heuristics"))
sys.path.insert(0, str(HERE))

from factor_base import FactorBase, cyclotomic_factors, kernel_basis  # noqa: E402
from htsolver import HalfTraceSolver  # noqa: E402
from residual import ht_attempts, htenum, residual_systems  # noqa: E402
from search import decomposition_lookup  # noqa: E402
from toycurve import ToyCurve  # noqa: E402

F4_RUNS = HERE.parent / "f4-gpu-20260925" / "runs.jsonl"


def f4_base(C: ToyCurve, index: int = 0) -> list[int]:
    K = C.K
    _, facs = cyclotomic_factors(C.n)
    p = facs[index]
    cols = []
    for j in range(C.n):
        acc = 0
        for i in range(p.bit_length()):
            if (p >> i) & 1:
                acc ^= K.frob(1 << j, i)
        cols.append(acc)
    return kernel_basis(cols, C.n)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", type=int, default=300)
    ap.add_argument("--planted", type=int, default=100)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    C = ToyCurve(23, a2=1)
    basis = f4_base(C)
    fb = FactorBase(C, "invariant", 11, 0, basis=basis, params={"cyclotomic_factor": 0})
    rec = fb.record()
    sv = HalfTraceSolver(fb)
    truth = decomposition_lookup(fb)
    rng = random.Random("f4-pair|EC1N23Cka1")
    pts = list(truth)
    planted = [pts[rng.randrange(len(pts))] for _ in range(args.planted)]
    ordinary = [C.random_subgroup_point(rng)[1] for _ in range(args.targets)]

    mism_py = mism_c = 0
    ht_py, ht_c, decomp = [], [], 0
    for kind, targets in (("planted", planted), ("ordinary", ordinary)):
        for R in targets:
            t0 = time.perf_counter_ns()
            got_py = bool(sv.decompose(R))
            t1 = time.perf_counter_ns()
            hits = 0
            for rs in residual_systems(sv, R[0]):
                hits += htenum(sv, rs, R[0])["hits"]
            t2 = time.perf_counter_ns()
            exact = R in truth
            mism_py += got_py != exact
            mism_c += (hits > 0) != exact
            if kind == "ordinary":
                ht_py.append(t1 - t0)
                ht_c.append(t2 - t1)
                decomp += exact

    batch = ht_attempts(sv, [R[0] for R in ordinary])
    mism_batch = sum((h > 0) != (R in truth) for R, h in zip(ordinary, batch["hits"]))

    f4 = {}
    for line in F4_RUNS.read_text().splitlines():
        r = json.loads(line)
        if "Cka1fb2071" not in r["candidate_id"]:
            continue
        f4.setdefault(r["candidate_id"], []).append(r["phase_wall_ns"]["pdp"] / r["counts"]["pdp_attempts"])
    import hashlib

    from stage_ids import PROJECTION, RESIDUAL
    from toycurve import sha256_hex

    labels = {}
    for variant in ("ht-python", "ht-c"):
        spec = RESIDUAL[variant]
        pd = {**PROJECTION, **{k: v for k, v in spec.items() if k != "sources"},
              "implementation": {"rule": "content hashes of the executed sources",
                                 "sha256": {s: hashlib.sha256((HERE.parent.parent / s).read_bytes()).hexdigest()
                                            for s in spec["sources"]}},
              "limits": "none"}
        digest = sha256_hex({"factor_base": rec, "point_decomposition": pd})
        labels[variant] = f"PS1N{C.n}C{C.tag}fb{rec['actual_usable_point_count']}PDP2hth{digest[:12]}"
    wrec = {"schema": "fb-search-workload/1", "curve_id": C.curve_id, "subgroup_order": str(C.r),
            "prng": "CPython random.Random seeded with the string (version-2 seeding)",
            "target_stream": "f4-pair|EC1N23Cka1",
            "target_law": f"{args.planted} planted points of the exact pair table, then {args.targets} "
            "R = [k]G with k uniform on [1, r-1]", "target_count": args.planted + args.targets,
            "cache_state": "cold"}
    wid = sha256_hex(wrec)[:12]
    out = {
        "candidate_id": None, "stage_config_ids": labels, "workload_id": wid,
        "run_ids": {v: f"{s}W{wid}R1" for v, s in labels.items()}, "workload": wrec,
        "curve": C.curve_id, "factor_base": {k: rec[k] for k in ("actual_usable_point_count", "geometric_point_count",
                                                                 "effective_columns", "quotient_rule", "nominal_dimension")},
        "d": max(0, fb.l + sv.dim_V2 - C.n - 1 + int(all(C.K.trace(v) == 0 for v in basis))),
        "dim_V2": sv.dim_V2,
        "exact_check": {"planted": args.planted, "ordinary": args.targets, "mismatch_python": mism_py,
                        "mismatch_c": mism_c},
        "ordinary_decomposable_fraction": round(decomp / args.targets, 3),
        "pdp2ht_python_ms_per_attempt_median": round(statistics.median(ht_py) / 1e6, 3),
        "pdp2ht_c_ms_per_attempt_median": round(statistics.median(ht_c) / 1e6, 3),
        "pdp2ht_c_batch_ms_per_attempt": round(batch["wall_ns"] / len(ordinary) / 1e6, 4),
        "c_batch_mismatch": mism_batch,
        "f4_ms_per_attempt": {cid: [round(v / 1e6, 2) for v in vals] for cid, vals in f4.items()},
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    if args.out:
        Path(args.out).write_text(json.dumps(out, sort_keys=True, indent=1) + "\n")


if __name__ == "__main__":
    main()
