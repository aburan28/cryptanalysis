#!/usr/bin/env python3
"""Fresh global-gauge versus local-gauge formula-count experiment.

Run through /Volumes/SSD990/cryptanalysis/sage -python. No CPU timing.
"""

from functools import lru_cache
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_stage as stage
import validate_scalar as full


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-global-gauge-20261007-v1"
BASES = 8
SCALARS_PER_BASE = 16


def plan(digits):
    """Minimize the declared M formula over all gauges and legal strides."""
    if not digits:
        return 0, (), 0
    top = len(digits) - 1
    assert digits[top][2]
    decisions = {}

    @lru_cache(None)
    def suffix(index, gauge):
        if index < 0:
            return int(gauge != 0)
        best = None
        for stride in (2, 1):
            if stride == 2 and (index == 0 or digits[index][2]):
                continue
            consumed = index - stride + 1
            power = digits[consumed][3] if digits[consumed][2] else None
            for next_gauge in range(3):
                change = (next_gauge - gauge) % 3
                step_cost = (4 if stride == 1 else 7 - int(change == 2))
                step_cost += int(power is not None and (power + next_gauge) % 3 != 0)
                score = step_cost + suffix(consumed - 1, next_gauge)
                # Prefer a pair on a tie, then the smaller resulting gauge.
                key = (score, -stride, next_gauge)
                if best is None or key < best[0]:
                    best = (key, (stride, consumed, next_gauge))
        assert best is not None
        decisions[index, gauge] = best[1]
        return best[0][0]

    best_start = min(
        (int((digits[top][3] + gauge) % 3 != 0) + suffix(top - 1, gauge), gauge)
        for gauge in range(3)
    )
    _, initial_gauge = best_start
    index, gauge = top - 1, initial_gauge
    steps = []
    while index >= 0:
        stride, consumed, next_gauge = decisions[index, gauge]
        steps.append((stride, consumed, next_gauge))
        index, gauge = consumed - 1, next_gauge
    return initial_gauge, tuple(steps), best_start[0]


def evaluate_global(curve, base, digits, beta):
    field = beta.parent()
    counts = {"tau_steps": 0, "tau_pairs": 0, "cheap_z_pairs": 0,
              "mixed_adds": 0, "digit_rotations": 0, "final_rotations": 0}
    if not digits:
        return curve(0), counts, 0
    initial_gauge, steps, optimized_variable_m = plan(digits)
    top_digit = digits[-1]
    initial_rotation = (top_digit[3] + initial_gauge) % 3
    jac = full.jac_add_mixed(
        (field(0), field(1), field(0)),
        (beta**initial_rotation * base[0], top_digit[2] * base[1]),
    )
    counts["mixed_adds"] += 1
    counts["digit_rotations"] += initial_rotation != 0
    gauge = initial_gauge
    for stride, index, next_gauge in steps:
        change = (next_gauge - gauge) % 3
        if stride == 2:
            jac = full.jac_tau_pair(jac, beta, change)
            counts["tau_pairs"] += 1
            counts["cheap_z_pairs"] += change == 2
        else:
            jac = full.jac_tau_scaled(jac, (1 - beta) * beta**change)
        counts["tau_steps"] += stride
        gauge = next_gauge
        digit = digits[index]
        if digit[2]:
            rotation = (digit[3] + gauge) % 3
            jac = full.jac_add_mixed(
                jac, (beta**rotation * base[0], digit[2] * base[1]))
            counts["mixed_adds"] += 1
            counts["digit_rotations"] += rotation != 0
    if gauge:
        jac = beta**((3 - gauge) % 3) * jac[0], jac[1], jac[2]
        counts["final_rotations"] += 1
    actual_variable_m = (4 * counts["tau_steps"] - counts["tau_pairs"] -
                         counts["cheap_z_pairs"] + counts["digit_rotations"] +
                         counts["final_rotations"])
    assert actual_variable_m == optimized_variable_m
    return full.affine(curve, jac), counts, optimized_variable_m


def main():
    field = GF(full.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(full.GX, full.GY)
    assert full.N * generator == curve(0)
    beta = field(2)**((full.P - 1) // 3)
    omega_generator = curve(beta * generator[0], generator[1])
    lambda_omega = None
    for seed in range(2, 100):
        root = pow(seed, (full.N - 1) // 3, full.N)
        if root != 1:
            for candidate in (root, root * root % full.N):
                if candidate * generator == omega_generator:
                    lambda_omega = candidate
                    break
        if lambda_omega is not None:
            break
    assert lambda_omega is not None
    lambda_tau = (1 - lambda_omega) % full.N
    basis = full.gauss_reduce((full.N, 0), (-lambda_tau, 1))

    digest = hashlib.sha256()
    cases = []
    totals = {"local_m": 0, "global_m": 0, "m_saved": 0,
              "local_pairs": 0, "global_pairs": 0,
              "local_cheap_z_pairs": 0, "global_cheap_z_pairs": 0,
              "local_rotations": 0, "global_rotations": 0}
    for base_index in range(BASES):
        base_scalar = 1 if base_index == 0 else full.deterministic_scalar(
            f"{LABEL}:base:{base_index}") or 1
        base = base_scalar * generator
        for scalar_index in range(SCALARS_PER_BASE):
            scalar = full.deterministic_scalar(
                f"{LABEL}:scalar:{base_index}:{scalar_index}") or 1
            digest.update(base_scalar.to_bytes(32, "big"))
            digest.update(scalar.to_bytes(32, "big"))
            a, b = full.short_representative(scalar, lambda_tau, basis)
            digits = full.recode(a, b)
            local_point, local_counts = full.evaluate(curve, base, digits, beta)
            global_point, global_counts, variable_m = evaluate_global(
                curve, base, digits, beta)
            expected = scalar * base
            assert local_point == global_point == expected
            assert local_counts["tau_steps"] == global_counts["tau_steps"]
            assert local_counts["mixed_adds"] == global_counts["mixed_adds"]
            local_m, global_m = (stage.formula_m(local_counts),
                                 stage.formula_m(global_counts))
            assert global_m == variable_m + 8 * global_counts["mixed_adds"]
            assert global_m <= local_m
            for key, amount in (
                ("local_m", local_m), ("global_m", global_m),
                ("m_saved", local_m - global_m),
                ("local_pairs", local_counts["tau_pairs"]),
                ("global_pairs", global_counts["tau_pairs"]),
                ("local_cheap_z_pairs", local_counts["cheap_z_pairs"]),
                ("global_cheap_z_pairs", global_counts["cheap_z_pairs"]),
                ("local_rotations", local_counts["digit_rotations"] +
                 local_counts["final_rotations"]),
                ("global_rotations", global_counts["digit_rotations"] +
                 global_counts["final_rotations"]),
            ):
                totals[key] += amount
            cases.append({
                "base_index": base_index, "scalar_index": scalar_index,
                "base_scalar_hex": f"{base_scalar:064x}",
                "scalar_hex": f"{scalar:064x}",
                "recode_length": len(digits),
                "recode_weight": sum(bool(digit[2]) for digit in digits),
                "local": local_counts, "global": global_counts,
                "local_formula_m": local_m, "global_formula_m": global_m,
                "formula_m_saved": local_m - global_m,
                "result_x_hex": f"{int(expected[0]):064x}",
                "result_y_hex": f"{int(expected[1]):064x}",
                "verified": True,
            })

    result = {
        "schema": 1, "kind": "256-bit-global-gauge-stage-diagnostic",
        "label": LABEL, "curve": "secp256k1", "base_count": BASES,
        "scalars_per_base": SCALARS_PER_BASE,
        "input_sha256": digest.hexdigest(),
        "control": "same_tau_unit_digits_local_carried_gauge",
        "candidate": "same_tau_unit_digits_globally_optimal_carried_gauge_and_stride",
        "formula_m": "4*tau_steps+8*mixed_adds+digit_rotations+final_rotations-tau_pairs-cheap_z_pairs",
        "cases": cases, "totals": totals,
        "positive_saving_cases": sum(case["formula_m_saved"] > 0 for case in cases),
        "zero_saving_cases": sum(case["formula_m_saved"] == 0 for case in cases),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "local_source_sha256": hashlib.sha256((HERE / "validate_scalar.py").read_bytes()).hexdigest(),
        "stage_source_sha256": hashlib.sha256((HERE / "compare_stage.py").read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(full.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
    }
    path = HERE / "global-gauge-result.json"
    if path.exists():
        raise SystemExit("global gauge result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(cases),
                      "totals": totals,
                      "positive_saving_cases": result["positive_saving_cases"],
                      "zero_saving_cases": result["zero_saving_cases"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
