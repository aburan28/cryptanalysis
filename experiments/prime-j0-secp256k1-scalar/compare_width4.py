#!/usr/bin/env python3
"""256-bit checked-Sage control using the existing width-four tau digit table."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF

import validate_scalar as dense


HERE = Path(__file__).resolve().parent
WIDTH4_SOURCE = HERE.parent / "prime-j0-cost-aware-chain" / "run.py"
sys.path.insert(0, str(WIDTH4_SOURCE.parent))
import run as width4  # noqa: E402


LABEL = "prime-j0-secp256k1-width4-control-20261007-v1"
BASES = 8
SCALARS_PER_BASE = 16


def empty_counts():
    return {"tau_steps": 0, "tau_pairs": 0, "cheap_z_pairs": 0,
            "mixed_adds": 0, "digit_rotations": 0, "final_rotations": 0}


def prepared_seeds(curve, base, beta):
    omega_base = curve(beta * base[0], base[1])
    tau_base = base - omega_base
    digest = hashlib.sha256()
    seeds = []
    for a, b in width4.SEEDS:
        point = a * base + b * tau_base
        assert point != curve(0)
        seeds.append((point[0], point[1]))
        digest.update(int(point[0]).to_bytes(32, "big"))
        digest.update(int(point[1]).to_bytes(32, "big"))
    return seeds, digest.hexdigest()


def digit_point(digit, seeds, beta, gauge):
    x, y = seeds[digit[2]]
    rotation = (digit[3] + gauge) % 3
    return (beta**rotation * x, digit[4] * y), int(rotation != 0)


def evaluate_horner(curve, digits, seeds, beta):
    field = beta.parent()
    jac = field(0), field(1), field(0)
    counts = empty_counts()
    for digit in reversed(digits):
        if jac[2] != 0:
            jac = dense.jac_tau_scaled(jac, 1 - beta)
            counts["tau_steps"] += 1
        if digit is not None:
            point, rotation = digit_point(digit, seeds, beta, 0)
            jac = dense.jac_add_mixed(jac, point)
            counts["mixed_adds"] += 1
            counts["digit_rotations"] += rotation
    return dense.affine(curve, jac), counts


def evaluate_paired(curve, digits, seeds, beta):
    field = beta.parent()
    jac = field(0), field(1), field(0)
    counts = empty_counts()
    if not digits:
        return curve(0), counts
    lowest_nonzero = next(i for i, digit in enumerate(digits)
                          if digit is not None)
    gauge = 0
    index = len(digits) - 1
    while index >= 0:
        digit = digits[index]
        pair = jac[2] != 0 and digit is None and index > 0
        if pair:
            index -= 1
            digit = digits[index]
        power = digit[3] if digit is not None else None
        last = index == lowest_nonzero
        next_gauge = (dense.paired_gauge(gauge, power, last) if pair else
                      dense.free_gauge(power, last) if power is not None
                      else gauge)
        if jac[2] != 0:
            change = (next_gauge - gauge) % 3
            if pair:
                jac = dense.jac_tau_pair(jac, beta, change)
                counts["tau_steps"] += 2
                counts["tau_pairs"] += 1
                counts["cheap_z_pairs"] += int(change == 2)
            else:
                jac = dense.jac_tau_scaled(jac, (1 - beta) * beta**change)
                counts["tau_steps"] += 1
        if power is not None or pair:
            gauge = next_gauge
        if digit is not None:
            point, rotation = digit_point(digit, seeds, beta, gauge)
            jac = dense.jac_add_mixed(jac, point)
            counts["mixed_adds"] += 1
            counts["digit_rotations"] += rotation
        index -= 1
    if jac[2] != 0 and gauge:
        jac = beta**((3 - gauge) % 3) * jac[0], jac[1], jac[2]
        counts["final_rotations"] += 1
    return dense.affine(curve, jac), counts


def generic_cost(counts):
    assert counts["mixed_adds"] > 0
    additions = counts["mixed_adds"] - 1
    muls = (4 * counts["tau_steps"] - counts["tau_pairs"] -
            counts["cheap_z_pairs"] + 8 * additions +
            counts["digit_rotations"] + counts["final_rotations"])
    squares = 2 * counts["tau_steps"] + 3 * additions
    return {"m": muls, "s": squares, "m_plus_s": muls + squares}


def eigenvalue_and_basis(generator, curve, beta):
    omega_generator = curve(beta * generator[0], generator[1])
    lambda_omega = None
    for seed in range(2, 100):
        root = pow(seed, (dense.N - 1) // 3, dense.N)
        if root != 1:
            for candidate in (root, root * root % dense.N):
                if candidate * generator == omega_generator:
                    lambda_omega = candidate
                    break
        if lambda_omega is not None:
            break
    assert lambda_omega is not None
    lambda_tau = (1 - lambda_omega) % dense.N
    return lambda_tau, dense.gauss_reduce((dense.N, 0), (-lambda_tau, 1))


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = eigenvalue_and_basis(generator, curve, beta)
    digest = hashlib.sha256()
    cases, preparations = [], []
    totals = {arm: {"m": 0, "s": 0, "m_plus_s": 0,
                    "mixed_adds": 0, "tau_steps": 0,
                    "tau_pairs": 0, "cheap_z_pairs": 0,
                    "rotations": 0}
              for arm in ("dense", "width4_horner", "width4_paired")}
    for base_index in range(BASES):
        base_scalar = 1 if base_index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{base_index}") or 1
        base = base_scalar * generator
        seeds, seed_digest = prepared_seeds(curve, base, beta)
        preparations.append({"base_index": base_index,
                             "base_scalar_hex": f"{base_scalar:064x}",
                             "prepared_affine_points": len(seeds),
                             "seed_point_sha256": seed_digest,
                             "preparation_cost": None})
        for scalar_index in range(SCALARS_PER_BASE):
            scalar = dense.deterministic_scalar(
                f"{LABEL}:scalar:{base_index}:{scalar_index}") or 1
            digest.update(base_scalar.to_bytes(32, "big"))
            digest.update(scalar.to_bytes(32, "big"))
            a, b = dense.short_representative(scalar, lambda_tau, basis)
            dense_digits = dense.recode(a, b)
            sparse_digits = width4.recode(a, b)
            assert width4.expand(sparse_digits) == (a, b)
            dense_point, dense_counts = dense.evaluate(
                curve, base, dense_digits, beta)
            horner_point, horner_counts = evaluate_horner(
                curve, sparse_digits, seeds, beta)
            paired_point, paired_counts = evaluate_paired(
                curve, sparse_digits, seeds, beta)
            expected = scalar * base
            assert dense_point == horner_point == paired_point == expected
            assert horner_counts["tau_steps"] == paired_counts["tau_steps"]
            assert horner_counts["mixed_adds"] == paired_counts["mixed_adds"]
            metrics = {}
            for arm, counts in (("dense", dense_counts),
                                ("width4_horner", horner_counts),
                                ("width4_paired", paired_counts)):
                cost = generic_cost(counts)
                for key in ("m", "s", "m_plus_s"):
                    totals[arm][key] += cost[key]
                for key in ("mixed_adds", "tau_steps", "tau_pairs",
                            "cheap_z_pairs"):
                    totals[arm][key] += counts[key]
                totals[arm]["rotations"] += (counts["digit_rotations"] +
                                             counts["final_rotations"])
                metrics[arm] = {"counts": counts, "generic_cost": cost}
            cases.append({
                "base_index": base_index, "scalar_index": scalar_index,
                "base_scalar_hex": f"{base_scalar:064x}",
                "scalar_hex": f"{scalar:064x}",
                "short_a_hex": hex(a), "short_b_hex": hex(b),
                "dense_length": len(dense_digits),
                "dense_weight": sum(bool(digit[2]) for digit in dense_digits),
                "width4_length": len(sparse_digits),
                "width4_weight": sum(digit is not None for digit in sparse_digits),
                "arms": metrics,
                "result_x_hex": f"{int(expected[0]):064x}",
                "result_y_hex": f"{int(expected[1]):064x}",
                "verified": True,
            })
    result = {
        "schema": 1, "kind": "256-bit-width4-published-control-stage",
        "label": LABEL, "curve": "secp256k1", "base_count": BASES,
        "scalars_per_base": SCALARS_PER_BASE,
        "input_sha256": digest.hexdigest(),
        "lambda_tau_hex": f"{lambda_tau:064x}",
        "preparations": preparations,
        "preparation_cost": None,
        "arms": ["dense", "width4_horner", "width4_paired"],
        "formula_boundary": "generic_tau_4M_2S_pair_6or7M_4S_mixed_8M_3S_first_add_free_rotations_1M",
        "cases": cases, "totals": totals,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dense_source_sha256": hashlib.sha256((HERE / "validate_scalar.py").read_bytes()).hexdigest(),
        "width4_source_sha256": hashlib.sha256(WIDTH4_SOURCE.read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
    }
    path = HERE / "width4-result.json"
    if path.exists():
        raise SystemExit("width-four result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(cases),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
