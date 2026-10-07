#!/usr/bin/env python3
"""Held-out 256-bit check of prepared unit orbits for width-four digits."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_width4 as control
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-orbit-prepared-20261007-v1"
BASES = 8
SCALARS_PER_BASE = 16


def prepare_orbits(seeds, beta):
    digest = hashlib.sha256()
    orbit = []
    for x, y in seeds:
        x1 = beta * x
        x2 = -x1 - x
        assert x2 == beta**2 * x
        row = ((x, y), (x1, y), (x2, y))
        orbit.append(row)
        for px, py in row:
            digest.update(int(px).to_bytes(32, "big"))
            digest.update(int(py).to_bytes(32, "big"))
    assert len(orbit) == 9
    return orbit, digest.hexdigest()


def planned_pairs(digits):
    if not digits:
        return 0
    assert digits[-1] is not None
    index = len(digits) - 1
    started, pairs = False, 0
    while index >= 0:
        if started and digits[index] is None and index > 0:
            pairs += 1
            index -= 2
        else:
            started |= digits[index] is not None
            index -= 1
    return pairs


def evaluate(curve, digits, orbit, beta):
    field = beta.parent()
    jac = field(0), field(1), field(0)
    counts = control.empty_counts()
    if not digits:
        return curve(0), counts
    expected_pairs = planned_pairs(digits)
    gauge = (-2 * expected_pairs) % 3
    index = len(digits) - 1
    while index >= 0:
        digit = digits[index]
        pair = jac[2] != 0 and digit is None and index > 0
        if pair:
            index -= 1
            digit = digits[index]
        if jac[2] != 0:
            if pair:
                jac = dense.jac_tau_pair(jac, beta, 2)
                gauge = (gauge + 2) % 3
                counts["tau_steps"] += 2
                counts["tau_pairs"] += 1
                counts["cheap_z_pairs"] += 1
            else:
                jac = dense.jac_tau_scaled(jac, 1 - beta)
                counts["tau_steps"] += 1
        if digit is not None:
            x, y = orbit[digit[2]][(digit[3] + gauge) % 3]
            jac = dense.jac_add_mixed(jac, (x, digit[4] * y))
            counts["mixed_adds"] += 1
        index -= 1
    assert counts["tau_pairs"] == expected_pairs
    assert gauge == 0
    assert counts["cheap_z_pairs"] == counts["tau_pairs"]
    assert counts["digit_rotations"] == counts["final_rotations"] == 0
    return dense.affine(curve, jac), counts


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = control.eigenvalue_and_basis(generator, curve, beta)
    digest = hashlib.sha256()
    cases, preparations = [], []
    totals = {arm: {"m": 0, "s": 0, "m_plus_s": 0,
                    "tau_steps": 0, "tau_pairs": 0, "cheap_z_pairs": 0,
                    "mixed_adds": 0, "rotations": 0}
              for arm in ("on_demand", "orbit_prepared")}
    for base_index in range(BASES):
        base_scalar = 1 if base_index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{base_index}") or 1
        base = base_scalar * generator
        seeds, seed_digest = control.prepared_seeds(curve, base, beta)
        orbit, orbit_digest = prepare_orbits(seeds, beta)
        preparations.append({
            "base_index": base_index, "base_scalar_hex": f"{base_scalar:064x}",
            "seed_point_sha256": seed_digest,
            "orbit_point_sha256": orbit_digest,
            "affine_seed_points": len(seeds), "affine_orbit_points": 3 * len(orbit),
            "orbit_preparation_m": len(orbit),
            "seed_construction_and_normalization_cost": None,
        })
        for scalar_index in range(SCALARS_PER_BASE):
            scalar = dense.deterministic_scalar(
                f"{LABEL}:scalar:{base_index}:{scalar_index}") or 1
            digest.update(base_scalar.to_bytes(32, "big"))
            digest.update(scalar.to_bytes(32, "big"))
            a, b = dense.short_representative(scalar, lambda_tau, basis)
            digits = control.width4.recode(a, b)
            assert control.width4.expand(digits) == (a, b)
            on_demand_point, on_demand_counts = control.evaluate_paired(
                curve, digits, seeds, beta)
            orbit_point, orbit_counts = evaluate(curve, digits, orbit, beta)
            expected = scalar * base
            assert on_demand_point == orbit_point == expected
            assert on_demand_counts["tau_steps"] == orbit_counts["tau_steps"]
            assert on_demand_counts["mixed_adds"] == orbit_counts["mixed_adds"]
            assert on_demand_counts["tau_pairs"] == orbit_counts["tau_pairs"]
            arms = {}
            for arm, counts in (("on_demand", on_demand_counts),
                                ("orbit_prepared", orbit_counts)):
                cost = control.generic_cost(counts)
                for key in ("m", "s", "m_plus_s"):
                    totals[arm][key] += cost[key]
                for key in ("tau_steps", "tau_pairs", "cheap_z_pairs",
                            "mixed_adds"):
                    totals[arm][key] += counts[key]
                totals[arm]["rotations"] += (counts["digit_rotations"] +
                                             counts["final_rotations"])
                arms[arm] = {"counts": counts, "generic_cost": cost}
            assert arms["orbit_prepared"]["generic_cost"]["m_plus_s"] <= (
                arms["on_demand"]["generic_cost"]["m_plus_s"])
            cases.append({
                "base_index": base_index, "scalar_index": scalar_index,
                "base_scalar_hex": f"{base_scalar:064x}",
                "scalar_hex": f"{scalar:064x}",
                "short_a_hex": hex(a), "short_b_hex": hex(b),
                "digit_length": len(digits),
                "digit_weight": sum(digit is not None for digit in digits),
                "arms": arms,
                "result_x_hex": f"{int(expected[0]):064x}",
                "result_y_hex": f"{int(expected[1]):064x}",
                "verified": True,
            })
    result = {
        "schema": 1, "kind": "256-bit-width4-prepared-unit-orbit-stage",
        "label": LABEL, "curve": "secp256k1", "base_count": BASES,
        "scalars_per_base": SCALARS_PER_BASE,
        "input_sha256": digest.hexdigest(),
        "preparations": preparations,
        "orbit_preparation_m_total": sum(row["orbit_preparation_m"] for row in preparations),
        "seed_construction_and_normalization_cost": None,
        "cases": cases, "totals": totals,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "width4_control_sha256": hashlib.sha256((HERE / "compare_width4.py").read_bytes()).hexdigest(),
        "width4_recode_sha256": hashlib.sha256(control.WIDTH4_SOURCE.read_bytes()).hexdigest(),
        "scalar_source_sha256": hashlib.sha256((HERE / "validate_scalar.py").read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
    }
    path = HERE / "orbit-prep-result.json"
    if path.exists():
        raise SystemExit("orbit-prep result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(cases),
                      "input_sha256": result["input_sha256"],
                      "orbit_preparation_m_total": result["orbit_preparation_m_total"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
