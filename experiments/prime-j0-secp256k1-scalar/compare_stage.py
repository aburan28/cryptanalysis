#!/usr/bin/env python3
"""Paired 256-bit formula-count comparison on fresh scalar inputs.

Run through the checked repository Sage launcher. This deliberately does
not time the Python prototype or claim a CPU speedup.
"""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import validate_scalar as full


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-stage-comparison-20261007-v1"
BASES = 8
SCALARS_PER_BASE = 16


def evaluate_free_gauge_no_pair(curve, base, digits, beta):
    field = beta.parent()
    jac = field(0), field(1), field(0)
    counts = {"tau_steps": 0, "tau_pairs": 0, "cheap_z_pairs": 0,
              "mixed_adds": 0, "digit_rotations": 0, "final_rotations": 0}
    if not digits:
        return curve(0), counts
    lowest_nonzero = next(i for i, digit in enumerate(digits) if digit[2])
    gauge = 0
    for index in range(len(digits) - 1, -1, -1):
        digit = digits[index]
        power = digit[3] if digit[2] else None
        next_gauge = full.free_gauge(power, index == lowest_nonzero) if (
            power is not None) else gauge
        if jac[2] != 0:
            change = (next_gauge - gauge) % 3
            jac = full.jac_tau_scaled(jac, (1 - beta) * beta**change)
            counts["tau_steps"] += 1
        if power is not None:
            gauge = next_gauge
            rotation = (power + gauge) % 3
            point = beta**rotation * base[0], digit[2] * base[1]
            jac = full.jac_add_mixed(jac, point)
            counts["mixed_adds"] += 1
            counts["digit_rotations"] += rotation != 0
    if jac[2] != 0 and gauge:
        jac = beta ** ((3 - gauge) % 3) * jac[0], jac[1], jac[2]
        counts["final_rotations"] += 1
    return full.affine(curve, jac), counts


def formula_m(counts):
    return (4 * counts["tau_steps"] + 8 * counts["mixed_adds"] +
            counts["digit_rotations"] + counts["final_rotations"] -
            counts["tau_pairs"] - counts["cheap_z_pairs"])


def main():
    field = GF(full.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(full.GX, full.GY)
    assert full.N * generator == curve(0)
    beta = field(2) ** ((full.P - 1) // 3)
    omega_generator = curve(beta * generator[0], generator[1])
    lambda_omega = None
    for seed in range(2, 100):
        root = pow(seed, (full.N - 1) // 3, full.N)
        if root == 1:
            continue
        for candidate in (root, root * root % full.N):
            if candidate * generator == omega_generator:
                lambda_omega = candidate
                break
        if lambda_omega is not None:
            break
    assert lambda_omega is not None
    lambda_tau = (1 - lambda_omega) % full.N
    basis = full.gauss_reduce((full.N, 0), (-lambda_tau, 1))

    input_digest = hashlib.sha256()
    cases = []
    totals = {"control_m": 0, "candidate_m": 0, "m_saved": 0,
              "tau_steps": 0, "mixed_adds": 0, "fused_pairs": 0,
              "cheap_z_pairs": 0, "control_rotations": 0,
              "candidate_rotations": 0}
    for base_index in range(BASES):
        base_scalar = 1 if base_index == 0 else full.deterministic_scalar(
            f"{LABEL}:base:{base_index}") or 1
        base = base_scalar * generator
        for scalar_index in range(SCALARS_PER_BASE):
            scalar = full.deterministic_scalar(
                f"{LABEL}:scalar:{base_index}:{scalar_index}") or 1
            input_digest.update(base_scalar.to_bytes(32, "big"))
            input_digest.update(scalar.to_bytes(32, "big"))
            a, b = full.short_representative(scalar, lambda_tau, basis)
            digits = full.recode(a, b)
            control, control_counts = evaluate_free_gauge_no_pair(
                curve, base, digits, beta)
            candidate, candidate_counts = full.evaluate(curve, base, digits, beta)
            expected = scalar * base
            assert control == candidate == expected
            assert control_counts["tau_steps"] == candidate_counts["tau_steps"]
            assert control_counts["mixed_adds"] == candidate_counts["mixed_adds"]
            control_m = formula_m(control_counts)
            candidate_m = formula_m(candidate_counts)
            saving = control_m - candidate_m
            for key, amount in (
                ("control_m", control_m), ("candidate_m", candidate_m),
                ("m_saved", saving), ("tau_steps", candidate_counts["tau_steps"]),
                ("mixed_adds", candidate_counts["mixed_adds"]),
                ("fused_pairs", candidate_counts["tau_pairs"]),
                ("cheap_z_pairs", candidate_counts["cheap_z_pairs"]),
                ("control_rotations", control_counts["digit_rotations"] +
                 control_counts["final_rotations"]),
                ("candidate_rotations", candidate_counts["digit_rotations"] +
                 candidate_counts["final_rotations"]),
            ):
                totals[key] += amount
            cases.append({
                "base_index": base_index, "scalar_index": scalar_index,
                "base_scalar_hex": f"{base_scalar:064x}",
                "scalar_hex": f"{scalar:064x}",
                "recode_length": len(digits),
                "recode_weight": sum(digit[2] != 0 for digit in digits),
                "control": control_counts, "candidate": candidate_counts,
                "control_formula_m": control_m,
                "candidate_formula_m": candidate_m,
                "formula_m_saved": saving,
                "result_x_hex": f"{int(expected[0]):064x}",
                "result_y_hex": f"{int(expected[1]):064x}",
                "verified": True,
            })

    result = {
        "schema": 1, "kind": "256-bit-paired-scalar-stage-diagnostic",
        "label": LABEL, "curve": "secp256k1", "base_count": BASES,
        "scalars_per_base": SCALARS_PER_BASE,
        "input_sha256": input_digest.hexdigest(),
        "lambda_tau_hex": f"{lambda_tau:064x}",
        "control": "same_tau_unit_digits_free_gauge_no_fused_stride",
        "candidate": "same_tau_unit_digits_carried_gauge_fused_stride",
        "formula_m": "4*tau_steps+8*mixed_adds+digit_rotations+final_rotations-tau_pairs-cheap_z_pairs",
        "cases": cases, "totals": totals,
        "positive_saving_cases": sum(case["formula_m_saved"] > 0 for case in cases),
        "zero_saving_cases": sum(case["formula_m_saved"] == 0 for case in cases),
        "negative_saving_cases": sum(case["formula_m_saved"] < 0 for case in cases),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scalar_source_sha256": hashlib.sha256((HERE / "validate_scalar.py").read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(full.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
    }
    path = HERE / "stage-result.json"
    if path.exists():
        raise SystemExit("stage result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(cases),
                      "totals": totals, "positive_saving_cases": result["positive_saving_cases"],
                      "negative_saving_cases": result["negative_saving_cases"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
