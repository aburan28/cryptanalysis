#!/usr/bin/env python3
"""Fresh paired check of endomorphism-assisted nine-point preparation."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_orbit_prepared as orbit
import compare_width4 as sparse
import full_prep as old
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-endo-seed-prep-20261007-v1"
CASES = 64
OLD_PREP = {"m": 102, "s": 43, "inversions": 1}
NEW_PREP = {"m": 96, "s": 40, "inversions": 1}


def prepare_optimized(curve, base, beta):
    x, y = base[0], base[1]
    point = x, y, x.parent()(1)
    twice = dense.jac_double(point)
    four = dense.jac_double(twice)
    omega_x = beta * x
    one_tau = dense.jac_add_mixed(twice, (omega_x, -y))
    two_two_tau = dense.jac_double(one_tau)
    one_two_tau = dense.jac_add_mixed(two_two_tau, (x, -y))
    two_four_tau = dense.jac_double(one_two_tau)
    two_tau = dense.jac_add_mixed(one_tau, (x, y))
    omega_twice = beta * twice[0], twice[1], twice[2]
    one_minus_two_tau = dense.jac_add_mixed(omega_twice, (x, -y))
    jacobians = [twice, four, one_tau, two_two_tau, one_two_tau,
                 two_four_tau, two_tau, one_minus_two_tau]
    normalized = [(x, y)] + old.batch_normalize(jacobians)
    assert len(normalized) == len(sparse.width4.SEEDS) == 9
    omega_base = curve(omega_x, y)
    tau_base = base - omega_base
    digest = hashlib.sha256()
    for (sx, sy), (a, b), jac in zip(normalized, sparse.width4.SEEDS,
                                    [point] + jacobians):
        expected = a * base + b * tau_base
        assert curve(sx, sy) == expected
        assert dense.affine(curve, jac) == expected
        digest.update(int(sx).to_bytes(32, "big"))
        digest.update(int(sy).to_bytes(32, "big"))
    return normalized, digest.hexdigest()


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    input_digest = hashlib.sha256()
    rows = []
    totals = {name: {"preparation_m": 0, "preparation_s": 0,
                     "preparation_inversions": 0, "online_m": 0,
                     "online_s": 0, "cold_m_plus_s_excluding_inversion": 0}
              for name in ("old", "optimized")}
    for index in range(CASES):
        base_scalar = 1 if index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{index}") or 1
        scalar = dense.deterministic_scalar(f"{LABEL}:scalar:{index}") or 1
        input_digest.update(base_scalar.to_bytes(32, "big"))
        input_digest.update(scalar.to_bytes(32, "big"))
        base = base_scalar * generator
        expected = scalar * base
        old_seeds, old_digest = old.prepare(curve, base, beta)
        new_seeds, new_digest = prepare_optimized(curve, base, beta)
        assert old_digest == new_digest
        assert old_seeds == new_seeds
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        digits = sparse.width4.recode(a, b)
        assert sparse.width4.expand(digits) == (a, b)
        arms = {}
        for name, seeds, prep in (("old", old_seeds, OLD_PREP),
                                  ("optimized", new_seeds, NEW_PREP)):
            orbits, orbit_digest = orbit.prepare_orbits(seeds, beta)
            output, counts = orbit.evaluate(curve, digits, orbits, beta)
            assert output == expected
            online = sparse.generic_cost(counts)
            cold = {"m": prep["m"] + online["m"],
                    "s": prep["s"] + online["s"],
                    "inversions": prep["inversions"],
                    "m_plus_s_excluding_inversion": (
                        prep["m"] + prep["s"] + online["m_plus_s"])}
            for key, amount in (("preparation_m", prep["m"]),
                                ("preparation_s", prep["s"]),
                                ("preparation_inversions", prep["inversions"]),
                                ("online_m", online["m"]),
                                ("online_s", online["s"]),
                                ("cold_m_plus_s_excluding_inversion",
                                 cold["m_plus_s_excluding_inversion"])):
                totals[name][key] += amount
            arms[name] = {"seed_sha256": old_digest if name == "old" else new_digest,
                          "orbit_sha256": orbit_digest, "preparation": prep,
                          "online_counts": counts, "online_cost": online,
                          "cold_cost": cold, "verified": True}
        assert arms["old"]["online_counts"] == arms["optimized"]["online_counts"]
        rows.append({"index": index,
                     "base_scalar_hex": f"{base_scalar:064x}",
                     "scalar_hex": f"{scalar:064x}",
                     "short_a_hex": hex(a), "short_b_hex": hex(b),
                     "digit_length": len(digits),
                     "digit_weight": sum(d is not None for d in digits),
                     "arms": arms,
                     "result_x_hex": f"{int(expected[0]):064x}",
                     "result_y_hex": f"{int(expected[1]):064x}",
                     "verified": True})
    result = {"schema": 1,
              "kind": "256-bit-endo-seed-single-use-preparation-comparison",
              "label": LABEL, "curve": "secp256k1", "case_count": CASES,
              "input_sha256": input_digest.hexdigest(),
              "old_preparation_per_case": OLD_PREP,
              "optimized_preparation_per_case": NEW_PREP,
              "rows": rows, "totals": totals,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "old_source_sha256": hashlib.sha256((HERE / "full_prep.py").read_bytes()).hexdigest(),
              "width4_source_sha256": hashlib.sha256((sparse.WIDTH4_SOURCE).read_bytes()).hexdigest(),
              "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
              "verified": True, "cpu_speedup_claim": None,
              "academic_novelty_claim": None}
    path = HERE / "endo-seed-result.json"
    if path.exists():
        raise SystemExit("endo-seed result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
