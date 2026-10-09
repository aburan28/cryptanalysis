#!/usr/bin/env python3
"""Extend the frozen N53 scan to 600 folded columns and close under Z[tau].

This is an exact factor-base geometry stage.  It does not collect relations or
measure a one-target discrete logarithm solve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, set_random_seed

from boolean_core import ANFField
from sage_probes import bits, curve, from_bits, multiplier_orbit, norm_multipliers

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
GEOMETRY = (REPO / "experiments/koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting"
            / "input/factor_base_geometry.json")
RHO = (REPO / "experiments/koblitz-n53-rcsample-generalization-20260930-v2-launcher-fix"
       / "runs/target_00/rho/rho.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trace_and_order(n):
    old, current = 2, -1  # trace over F2 for y^2+xy=x^3+1
    for _ in range(2, n+1):
        old, current = current, -current-2*old
    return current, (1 << n)+1-current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=600)
    parser.add_argument("--max-scan-x", type=int, default=2000)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve prior receipt")
    if args.columns < 1 or args.max_scan_x < 1:
        parser.error("positive columns and scan bound required")
    started = time.perf_counter_ns()
    set_random_seed(20261008)
    frozen = json.loads(GEOMETRY.read_text())
    rho = json.loads(RHO.read_text().splitlines()[0])
    assert frozen["n"] == rho["n"] == 53
    assert frozen["subgroup_order"] == rho["subgroup_order"]
    assert frozen["a"] == rho["a"] == 0
    r, lam = frozen["subgroup_order"], rho["lambda"]
    assert (lam*lam+lam+2) % r == 0 and pow(lam, 53, r) == 1
    terms = rho["field_modulus_low_terms"]
    F = PolynomialRing(GF(2), "t")
    t = F.gen()
    K = GF(2**53, "z53", modulus=t**53+sum((t**i for i in terms), F(0)))
    E = curve(K)
    field_modulus_bits = (1 << 53) | sum(1 << i for i in terms)
    square_images = ANFField(53, field_modulus_bits).reductions[::2]
    def square_bits(value):
        answer = 0
        while value:
            low = value & -value
            answer ^= square_images[low.bit_length()-1]
            value ^= low
        return answer
    def canon(P):
        x, y = bits(P[0]), bits(P[1])
        best = (x, y)
        for _ in range(53):
            best = min(best, (x, y), (x, y ^ x))
            x, y = square_bits(x), square_bits(y)
        return best
    trace, order = trace_and_order(53)
    assert order % r == 0
    cofactor = order // r
    source_representatives = [E(from_bits(K, x), from_bits(K, y))
                              for x, y in frozen["representative_points"]]
    assert len(source_representatives) == frozen["orbit_columns"]
    assert all((r*P).is_zero() for P in source_representatives[:4])
    assert lam*source_representatives[0] == E(source_representatives[0][0]**2,
                                             source_representatives[0][1]**2)
    representatives = {canon(P): P for P in source_representatives}
    assert len(representatives) == frozen["orbit_columns"]
    scan_end = frozen["factor_base_scanned_x"]
    for xbits in range(scan_end+1, args.max_scan_x+1):
        if len(representatives) >= args.columns:
            break
        scan_end = xbits
        try:
            P = E.lift_x(from_bits(K, xbits))
        except ValueError:
            continue
        P = cofactor*P
        if P.is_zero():
            continue
        assert (r*P).is_zero()
        representatives.setdefault(canon(P), P)
    status = "COMPLETE" if len(representatives) >= args.columns else "SCAN_LIMIT"
    if status == "COMPLETE":
        # The frozen prefix is retained; any overshoot would be explicit.
        representatives = dict(list(representatives.items())[:args.columns])
    multipliers = norm_multipliers(16)
    classes = sorted({multiplier_orbit((a+b*lam) % r, lam, 53, r)
                      for a, b, _ in multipliers})
    closure = set()
    for scalar in classes:
        for P in representatives.values():
            closure.add(canon(scalar*P))
    assert set(representatives).issubset(closure)
    all_generic = all(P[0] != P[0]**2 for P in representatives.values())
    answer = {
        "schema_version": 1, "proposal_id": "A1", "candidate_id": None,
        "run_id": None, "status": status, "curve_id": "EC1N53Ckb1h888961ed110e",
        "field_degree": 53, "field_modulus_low_terms": terms,
        "field_modulus_bits": field_modulus_bits,
        "curve_model": "y^2+xy=x^3+1", "curve_trace": trace,
        "curve_order": order, "subgroup_order": r, "cofactor": cofactor,
        "frobenius_scalar": lam,
        "source_scan_end_x": frozen["factor_base_scanned_x"],
        "extended_scan_end_x": scan_end, "max_scan_x": args.max_scan_x,
        "source_folded_columns": frozen["orbit_columns"],
        "requested_seed_folded_columns": args.columns,
        "seed_folded_columns": len(representatives),
        "seed_actual_usable_B": len(representatives)*106 if all_generic else None,
        "seed_generic_106_point_orbits": all_generic,
        "multipliers_up_to_sign": len(multipliers),
        "multiplier_classes_after_sign_frobenius": len(classes),
        "multiplier_class_scalars": classes,
        "closure_folded_columns": len(closure),
        "closure_actual_usable_B": len(closure)*106 if all_generic else None,
        "closure_factor": len(closure)/len(representatives),
        "scalar_image_operations": len(classes)*len(representatives),
        "seed_representative_keys_sha256": hashlib.sha256(json.dumps(
            sorted(representatives), separators=(",", ":")).encode()).hexdigest(),
        "closure_representative_keys_sha256": hashlib.sha256(json.dumps(
            sorted(closure), separators=(",", ":")).encode()).hexdigest(),
        "source_sha256": sha(Path(__file__)),
        "frozen_geometry_sha256": sha(GEOMETRY), "rho_fixture_sha256": sha(RHO),
        "stage_wall_ns": time.perf_counter_ns()-started,
        "scope": "N53 base geometry and norm closure at 600 seed folded columns; no natural relation probes, weighted matrix rank, or target solve",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({k: answer[k] for k in (
        "status", "extended_scan_end_x", "seed_folded_columns",
        "closure_folded_columns", "scalar_image_operations")}, sort_keys=True))


if __name__ == "__main__":
    main()
