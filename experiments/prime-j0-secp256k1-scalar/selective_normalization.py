#!/usr/bin/env python3
"""Scalar-conditioned Jacobian/affine digit-table selection at 256 bits."""

from collections import Counter
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_orbit_prepared as orbit_control
import compare_width4 as sparse
import full_prep as previous
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-selective-normalization-20261007-v1"
CASES = 64


def projective_seeds(curve, base, beta):
    x, y = base[0], base[1]
    point = x, y, x.parent()(1)
    tau = dense.jac_tau_scaled(point, 1 - beta)
    q2 = dense.jac_double(point)
    q4 = dense.jac_double(q2)
    q1tau = dense.jac_add_mixed(tau, (x, y))
    q2two = dense.jac_double(q1tau)
    q2tau = dense.jac_add_mixed(q1tau, (x, y))
    q1two = dense.jac_add_mixed(q2two, (x, -y))
    q2four = dense.jac_double(q1two)
    q1minus = previous.jac_add(q2, previous.jac_neg(q1two))
    points = [point, q2, q4, q1tau, q2two, q1two,
              q2four, q2tau, q1minus]
    assert len(points) == len(sparse.width4.SEEDS) == 9
    omega_base = curve(beta * x, y)
    tau_base = base - omega_base
    digest = hashlib.sha256()
    for jac, (a, b) in zip(points, sparse.width4.SEEDS):
        expected = a * base + b * tau_base
        assert dense.affine(curve, jac) == expected
        digest.update(int(expected[0]).to_bytes(32, "big"))
        digest.update(int(expected[1]).to_bytes(32, "big"))
    return points, digest.hexdigest()


def normalize_selected(points, selected):
    """Batch-normalize the chosen constructed points, with one inversion."""
    output = list(points)
    if not selected:
        return output
    chosen = [points[index] for index in selected]
    zs = [point[2] for point in chosen]
    if any(z == 0 for z in zs):
        raise ValueError("selected preparation point at infinity")
    prefix = [zs[0].parent()(1)] * len(zs)
    product = zs[0]
    for index in range(1, len(zs)):
        prefix[index] = product
        product *= zs[index]
    inverse_product = 1 / product
    inverse_z = [None] * len(zs)
    for index in range(len(zs) - 1, 0, -1):
        inverse_z[index] = inverse_product * prefix[index]
        inverse_product *= zs[index]
    inverse_z[0] = inverse_product
    one = zs[0].parent()(1)
    for index, jac, inverse in zip(selected, chosen, inverse_z):
        square = inverse**2
        cube = square * inverse
        output[index] = jac[0] * square, jac[1] * cube, one
    return output


def make_orbits(points, beta):
    digest = hashlib.sha256()
    table = []
    for x, y, z in points:
        x1 = beta * x
        x2 = -x1 - x
        assert x2 == beta**2 * x
        row = ((x, y, z), (x1, y, z), (x2, y, z))
        table.append(row)
        for px, py, pz in row:
            digest.update(int(px).to_bytes(32, "big"))
            digest.update(int(py).to_bytes(32, "big"))
            digest.update(int(pz).to_bytes(32, "big"))
    return table, digest.hexdigest()


def selected_indices(digits):
    if not digits:
        return ()
    frequencies = Counter(digit[2] for digit in digits[:-1]
                          if digit is not None)
    return tuple(index for index in range(1, 9)
                 if frequencies[index] >= 2)


def evaluate(curve, digits, table, affine_mask, beta):
    field = beta.parent()
    jac = field(0), field(1), field(0)
    counts = {"tau_steps": 0, "tau_pairs": 0,
              "cheap_z_pairs": 0, "mixed_adds": 0,
              "general_adds": 0, "first_insertions": 0}
    if not digits:
        return curve(0), counts
    pairs = orbit_control.planned_pairs(digits)
    gauge = (-2 * pairs) % 3
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
            seed = digit[2]
            qx, qy, qz = table[seed][(digit[3] + gauge) % 3]
            qy = digit[4] * qy
            if jac[2] == 0:
                jac = qx, qy, qz
                counts["first_insertions"] += 1
            elif affine_mask[seed]:
                assert qz == 1
                jac = dense.jac_add_mixed(jac, (qx, qy))
                counts["mixed_adds"] += 1
            else:
                jac = previous.jac_add(jac, (qx, qy, qz))
                counts["general_adds"] += 1
        index -= 1
    assert counts["tau_pairs"] == pairs and counts["cheap_z_pairs"] == pairs
    assert gauge == 0
    assert counts["first_insertions"] == 1
    assert (counts["first_insertions"] + counts["mixed_adds"] +
            counts["general_adds"] == sum(d is not None for d in digits))
    return dense.affine(curve, jac), counts


def generic_cost(counts, normalized_count):
    m = normalized_count
    prep_m = 57 + (6 * m - 3 if m else 0)
    prep_s = 35 + m
    prep_i = int(m > 0)
    pairs, steps = counts["tau_pairs"], counts["tau_steps"]
    mixed, general = counts["mixed_adds"], counts["general_adds"]
    online_m = 4 * steps - 2 * pairs + 8 * mixed + 12 * general
    online_s = 2 * steps + 3 * mixed + 4 * general
    return {"preparation_m": prep_m, "preparation_s": prep_s,
            "preparation_inversions": prep_i,
            "online_m": online_m, "online_s": online_s,
            "m_plus_s_excluding_inversion": prep_m + prep_s + online_m + online_s}


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    input_digest = hashlib.sha256()
    rows = []
    totals = {arm: {"m_plus_s_excluding_inversion": 0,
                    "preparation_inversions": 0,
                    "mixed_adds": 0, "general_adds": 0,
                    "normalized_points": 0}
              for arm in ("projective", "selective", "all_affine")}
    for index in range(CASES):
        base_scalar = 1 if index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{index}") or 1
        scalar = dense.deterministic_scalar(f"{LABEL}:scalar:{index}") or 1
        input_digest.update(base_scalar.to_bytes(32, "big"))
        input_digest.update(scalar.to_bytes(32, "big"))
        base = base_scalar * generator
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        digits = sparse.width4.recode(a, b)
        assert sparse.width4.expand(digits) == (a, b)
        seeds, seed_digest = projective_seeds(curve, base, beta)
        chosen = selected_indices(digits)
        policies = {"projective": (), "selective": chosen,
                    "all_affine": tuple(range(1, 9))}
        expected = scalar * base
        arms = {}
        for name, selected in policies.items():
            converted = normalize_selected(seeds, selected)
            mask = tuple(index == 0 or index in selected for index in range(9))
            for seed_index, point in enumerate(converted):
                assert dense.affine(curve, point) == dense.affine(
                    curve, seeds[seed_index])
            table, orbit_digest = make_orbits(converted, beta)
            result, counts = evaluate(curve, digits, table, mask, beta)
            assert result == expected
            cost = generic_cost(counts, len(selected))
            for key in ("m_plus_s_excluding_inversion",
                        "preparation_inversions"):
                totals[name][key] += cost[key]
            totals[name]["mixed_adds"] += counts["mixed_adds"]
            totals[name]["general_adds"] += counts["general_adds"]
            totals[name]["normalized_points"] += len(selected)
            arms[name] = {"selected_indices": list(selected),
                          "orbit_sha256": orbit_digest,
                          "counts": counts, "generic_cost": cost}
        assert len({arms[name]["counts"]["tau_steps"] for name in arms}) == 1
        assert len({arms[name]["counts"]["tau_pairs"] for name in arms}) == 1
        projective_cost = arms["projective"]["generic_cost"]["m_plus_s_excluding_inversion"]
        selective_cost = arms["selective"]["generic_cost"]["m_plus_s_excluding_inversion"]
        all_cost = arms["all_affine"]["generic_cost"]["m_plus_s_excluding_inversion"]
        rows.append({
            "index": index, "base_scalar_hex": f"{base_scalar:064x}",
            "scalar_hex": f"{scalar:064x}",
            "short_a_hex": hex(a), "short_b_hex": hex(b),
            "digit_length": len(digits),
            "digit_weight": sum(d is not None for d in digits),
            "seed_point_sha256": seed_digest,
            "arms": arms,
            "selective_break_even_inversion_m_plus_s": (
                projective_cost - selective_cost if chosen else None),
            "all_affine_break_even_inversion_m_plus_s": projective_cost - all_cost,
            "result_x_hex": f"{int(expected[0]):064x}",
            "result_y_hex": f"{int(expected[1]):064x}",
            "verified": True,
        })
    result = {
        "schema": 1, "kind": "256-bit-scalar-conditioned-selective-normalization",
        "label": LABEL, "curve": "secp256k1", "case_count": CASES,
        "input_sha256": input_digest.hexdigest(),
        "selection_rule": "normalize constructed seed iff it occurs at least twice after first insertion",
        "inversion_conversion_m_plus_s": None,
        "rows": rows, "totals": totals,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "full_prep_source_sha256": hashlib.sha256((HERE / "full_prep.py").read_bytes()).hexdigest(),
        "orbit_source_sha256": hashlib.sha256((HERE / "compare_orbit_prepared.py").read_bytes()).hexdigest(),
        "width4_source_sha256": hashlib.sha256((HERE / "compare_width4.py").read_bytes()).hexdigest(),
        "recode_source_sha256": hashlib.sha256(sparse.WIDTH4_SOURCE.read_bytes()).hexdigest(),
        "scalar_source_sha256": hashlib.sha256((HERE / "validate_scalar.py").read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
    }
    path = HERE / "selective-result.json"
    if path.exists():
        raise SystemExit("selective result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
