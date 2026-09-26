#!/usr/bin/env python3
"""Run the matched fixed-phase vs phase-free orbit-key experiment."""
from __future__ import annotations
import argparse, json, math, platform, sys
from pathlib import Path

from orbit_core import (
    degree_consistency, koblitz_order, m3_truths, m4_stats, mobius_anf,
    model, planted_targets, poisson_prediction,
)

SEED = 20260926
CASES = (
    # Reuse normal generators from the earlier Frobenius experiments.
    (13, 4, 5475),
    (19, 6, 112679),
)


def run_case(n, s, beta):
    M = model(n, s, beta)
    t3, w3 = planted_targets(M, 3, 8, (0, 1, 2), SEED)
    fixed3, fixed_stats = m3_truths(M, t3, "fixed")
    orbit3, orbit_stats = m3_truths(M, t3, "orbit")
    combined = fixed3 + orbit3
    degrees = (5, 6) if n == 13 else (8, 9)
    out = {
        "model": {
            "n": n, "s": s, "normal_generator": beta,
            "subgroup_order": M["r"], "frobenius_eigenvalue": M["lam"],
            "valid_orbit_keys": len(M["keys"]), "keys": M["keys"],
            "signed_frobenius_orbit_size": len(M["H"]),
        },
        "m3": {
            "targets": t3, "planted_witnesses": w3,
            "fixed_phase": fixed_stats,
            "phase_free": orbit_stats,
            "uniform_orbit_prediction": poisson_prediction(n, M["r"], 3),
            "first_target_full_cube_anf": {
                "fixed_phase": mobius_anf(fixed3[0], 3 * s),
                "phase_free": mobius_anf(orbit3[0], 3 * s),
            },
            "valid_domain_degree_tests": [
                degree_consistency(combined, M["keys"], s, d) for d in degrees
            ],
            "rhs_order": "first 8 fixed-phase predicates, then 8 phase-free predicates",
        },
    }
    if n == 19:
        t4, w4 = planted_targets(M, 4, 8, (0, 1, 2, 3), SEED)
        out["m4"] = {
            "targets": t4, "planted_witnesses": w4,
            "fixed_phase": m4_stats(M, t4, "fixed"),
            "phase_free": m4_stats(M, t4, "orbit"),
            "uniform_orbit_prediction": poisson_prediction(n, M["r"], 4),
        }
    return out


def degree131_projection():
    n = 131
    r = koblitz_order(n) // 4
    raw = (1 << 26) - 1
    # Prior degree-131 fixture: 68 accepted r-torsion point orbits from 256
    # distinct sampled nonzero payloads. This is an empirical projection only.
    acceptance = 68 / 256
    K = raw * acceptance
    mu4 = (2 * n) ** 4 / r
    return {
        "n": n,
        "subgroup_order": r,
        "subgroup_order_log2": math.log2(r),
        "raw_nonzero_quotient_keys": raw,
        "sample_acceptance": acceptance,
        "estimated_usable_orbit_keys": K,
        "estimated_usable_orbit_keys_log2": math.log2(K),
        "m4_mean_witnesses_per_key_tuple": mu4,
        "m4_mean_witnesses_per_key_tuple_log2": math.log2(mu4),
        "m4_key_tuple_space_log2": 4 * math.log2(K),
        "m4_sign_phase_space_per_key_tuple_log2": 4 * math.log2(2 * n),
        "m4_total_witness_space_log2": 4 * math.log2(K) + 4 * math.log2(2 * n),
        "estimated_relations_per_target_over_full_key_space": K ** 4 * mu4,
        "rho_reference_log2": 60.8,
        "relation_collection_budget_per_relation_log2_ignoring_LA":
            60.8 - math.log2(K),
        "scope": "sample-derived scaling heuristic; not a measured n=131 relation collector",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = {
        "schema": 1,
        "seed": SEED,
        "python": sys.version,
        "platform": platform.platform(),
        "cases": [run_case(*case) for case in CASES],
        "degree131_projection": degree131_projection(),
        "claims": {
            "phase_free_definition":
                "existence of signs and independent Frobenius phases for each orbit key",
            "fixed_phase_definition":
                "phases (0,1,2) or (0,1,2,3), with signs still free",
            "degree_test":
                "exact Boolean interpolation only on valid orbit keys; invalid payload membership is separate",
            "not_claimed":
                "no degree-131 solve, no attack exponent, no Groebner/SAT speedup, no lower bound",
        },
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
