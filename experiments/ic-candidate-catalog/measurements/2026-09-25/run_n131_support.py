#!/usr/bin/env python3
"""Enumerate exact four-sum support of the catalog's N131 d=7 base."""

from __future__ import annotations

import hashlib
from itertools import combinations_with_replacement
import json
from pathlib import Path
import platform
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / "experiments/nonfrobenius-ic/index_calculus.py"
sys.path.insert(0, str(SOURCE.parent))
import index_calculus as ic  # noqa: E402


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def main() -> None:
    out = HERE / "n131_poly_d7_exact_support.json"
    if out.exists():
        raise SystemExit("output already exists")
    ledger = ic.Ledger()
    curve, order = ic.setup("ecc2k130", ledger)
    start = time.perf_counter_ns()
    base = ic.factor_base(curve, order, 7)
    base_ns = time.perf_counter_ns() - start
    encoded = [ic.encode_point(point) for point in base]
    profile = next(p for p in json.loads((HERE.parents[1] / "profiles.json").read_text())["profiles"]
                   if p["id"] == "n131_poly_d7_m4")
    digest = hashlib.sha256(canonical(encoded).encode()).hexdigest()
    assert len(base) == 26 and digest == profile["base_digest"]

    start = time.perf_counter_ns()
    support = set()
    leaves = 0
    for indices in combinations_with_replacement(range(len(base)), 4):
        support.add(ic.point_sum(curve, base, indices))
        leaves += 1
    enumerate_ns = time.perf_counter_ns() - start

    start = time.perf_counter_ns()
    pair_sums = {curve.add(base[i], base[j])
                 for i in range(len(base)) for j in range(i, len(base))}
    pair_keys = list(pair_sums)
    pair_support = {curve.add(pair_keys[i], pair_keys[j])
                    for i in range(len(pair_keys)) for j in range(i, len(pair_keys))}
    replay_ns = time.perf_counter_ns() - start
    assert pair_support == support

    nonzero_support = len(support) - (None in support)
    report = {
        "kind": "exact_n131_d7_four_sum_support",
        "profile_id": profile["id"],
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "field_degree": 131,
        "subgroup_order": str(order),
        "factor_base_points": len(base),
        "factor_base_digest_sha256": digest,
        "tuple_leaves_unordered_with_repetition": leaves,
        "support_points_nonidentity": nonzero_support,
        "identity_supported": None in support,
        "uniform_nonidentity_query_coverage": nonzero_support / (order - 1),
        "pair_sum_keys": len(pair_sums),
        "independent_pair_sum_replay_matches": True,
        "phase_wall_ns": {
            "factor_base_build": base_ns,
            "four_sum_enumeration": enumerate_ns,
            "pair_sum_replay": replay_ns,
        },
        "ledger_operations": ledger.report(),
        "pdp_solver_cost": None,
        "complete_dlp_cost": None,
        "rho_speedup": None,
    }
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
