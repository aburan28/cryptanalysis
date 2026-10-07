#!/usr/bin/env python3
"""Fresh 256-bit projective-orbit versus affine-orbit one-use comparison."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_width4 as sparse
import endo_seed_prep as optimized
import selective_normalization as choices
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-projective-endo-20261007-v1"
CASES = 64


def projective_seeds(curve, base, beta):
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
    points = [point, twice, four, one_tau, two_two_tau, one_two_tau,
              two_four_tau, two_tau, one_minus_two_tau]
    omega_base = curve(omega_x, y)
    tau_base = base - omega_base
    digest = hashlib.sha256()
    for jac, (a, b) in zip(points, sparse.width4.SEEDS):
        expected = a * base + b * tau_base
        assert dense.affine(curve, jac) == expected
        digest.update(int(expected[0]).to_bytes(32, "big"))
        digest.update(int(expected[1]).to_bytes(32, "big"))
    return points, digest.hexdigest()


def source_cost(counts, normalized_points):
    # Existing generic_cost has the old 48M+35S chain; the two
    # endomorphism-assisted seed substitutions remove 6M+3S.
    original = choices.generic_cost(counts, normalized_points)
    assert normalized_points in (0, 8)
    m = original["preparation_m"] - 6
    s = original["preparation_s"] - 3
    return {"preparation_m": m, "preparation_s": s,
            "preparation_inversions": original["preparation_inversions"],
            "online_m": original["online_m"],
            "online_s": original["online_s"],
            "m_plus_s_excluding_inversion": (
                m + s + original["online_m"] + original["online_s"])}


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
                     "online_s": 0, "m_plus_s_excluding_inversion": 0,
                     "mixed_adds": 0, "general_adds": 0}
              for name in ("projective", "affine")}
    for index in range(CASES):
        base_scalar = 1 if index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{index}") or 1
        scalar = dense.deterministic_scalar(f"{LABEL}:scalar:{index}") or 1
        input_digest.update(base_scalar.to_bytes(32, "big"))
        input_digest.update(scalar.to_bytes(32, "big"))
        base = base_scalar * generator
        expected = scalar * base
        seeds, seed_digest = projective_seeds(curve, base, beta)
        affine_seeds = choices.normalize_selected(seeds, tuple(range(1, 9)))
        old_affine, old_digest = optimized.prepare_optimized(curve, base, beta)
        assert [(x, y) for x, y, _ in affine_seeds] == old_affine
        assert seed_digest == old_digest
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        digits = sparse.width4.recode(a, b)
        assert sparse.width4.expand(digits) == (a, b)
        arms = {}
        for name, table_points, normalized in (
            ("projective", seeds, 0), ("affine", affine_seeds, 8)
        ):
            affine_mask = tuple(index == 0 or normalized == 8
                                for index in range(9))
            table, orbit_digest = choices.make_orbits(table_points, beta)
            output, counts = choices.evaluate(curve, digits, table,
                                              affine_mask, beta)
            assert output == expected
            cost = source_cost(counts, normalized)
            assert cost["preparation_m"] == (51 if name == "projective" else 96)
            assert cost["preparation_s"] == (32 if name == "projective" else 40)
            for key in ("preparation_m", "preparation_s",
                        "preparation_inversions", "online_m", "online_s",
                        "m_plus_s_excluding_inversion"):
                totals[name][key] += cost[key]
            totals[name]["mixed_adds"] += counts["mixed_adds"]
            totals[name]["general_adds"] += counts["general_adds"]
            arms[name] = {"orbit_sha256": orbit_digest,
                          "counts": counts, "source_cost": cost,
                          "verified": True}
        assert (arms["projective"]["counts"]["tau_steps"] ==
                arms["affine"]["counts"]["tau_steps"])
        assert (arms["projective"]["counts"]["tau_pairs"] ==
                arms["affine"]["counts"]["tau_pairs"])
        threshold = (arms["projective"]["source_cost"][
            "m_plus_s_excluding_inversion"] - arms["affine"][
                "source_cost"]["m_plus_s_excluding_inversion"])
        rows.append({"index": index,
                     "base_scalar_hex": f"{base_scalar:064x}",
                     "scalar_hex": f"{scalar:064x}",
                     "short_a_hex": hex(a), "short_b_hex": hex(b),
                     "digit_length": len(digits),
                     "digit_weight": sum(d is not None for d in digits),
                     "seed_point_sha256": seed_digest, "arms": arms,
                     "inversion_break_even_m_plus_s": threshold,
                     "result_x_hex": f"{int(expected[0]):064x}",
                     "result_y_hex": f"{int(expected[1]):064x}",
                     "verified": True})
    result = {
        "schema": 1,
        "kind": "256-bit-projective-endo-single-use-representation",
        "label": LABEL, "curve": "secp256k1", "case_count": CASES,
        "input_sha256": input_digest.hexdigest(),
        "projective_preparation": {"m": 51, "s": 32, "inversions": 0},
        "affine_preparation": {"m": 96, "s": 40, "inversions": 1},
        "rows": rows, "totals": totals,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "endo_source_sha256": hashlib.sha256((HERE / "endo_seed_prep.py").read_bytes()).hexdigest(),
        "selective_source_sha256": hashlib.sha256((HERE / "selective_normalization.py").read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    path = HERE / "projective-endo-result.json"
    if path.exists():
        raise SystemExit("projective-endo result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
