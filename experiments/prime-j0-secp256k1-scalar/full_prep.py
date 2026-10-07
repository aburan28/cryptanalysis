#!/usr/bin/env python3
"""Explicit single-use variable-base preparation and scalar correctness."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_orbit_prepared as orbit
import compare_width4 as sparse
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-full-prep-20261007-v1"
CASES = 32
PREP_COST = {"m": 102, "s": 43, "inversions": 1}


def jac_neg(point):
    x, y, z = point
    return x, -y, z


def jac_add(first, second):
    """Generic Jacobian + Jacobian, 12M+4S outside exceptions."""
    x1, y1, z1 = first
    x2, y2, z2 = second
    if z1 == 0 or z2 == 0:
        raise ValueError("preparation encountered an identity input")
    zz1, zz2 = z1**2, z2**2
    u1, u2 = x1 * zz2, x2 * zz1
    s1, s2 = y1 * z2 * zz2, y2 * z1 * zz1
    h, r = u2 - u1, s2 - s1
    if h == 0:
        raise ValueError("preparation encountered an exceptional addition")
    hh = h**2
    hhh, v = h * hh, u1 * hh
    rx = r**2 - hhh - 2 * v
    ry = r * (v - rx) - s1 * hhh
    rz = z1 * z2 * h
    return rx, ry, rz


def batch_normalize(points):
    """Montgomery batch inverse: 21M+1I, then 3M+1S per point."""
    assert len(points) == 8
    zs = [point[2] for point in points]
    if any(z == 0 for z in zs):
        raise ValueError("preparation point at infinity")
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
    affine = []
    for (x, y, _), inverse in zip(points, inverse_z):
        square = inverse**2
        cube = square * inverse
        affine.append((x * square, y * cube))
    return affine


def prepare(curve, base, beta):
    """Nine published coefficient points; validate before online use."""
    x, y = base[0], base[1]
    one = x.parent()(1)
    point = x, y, one
    tau = dense.jac_tau_scaled(point, 1 - beta)
    q2 = dense.jac_double(point)
    q4 = dense.jac_double(q2)
    q1tau = dense.jac_add_mixed(tau, (x, y))
    q2two = dense.jac_double(q1tau)
    q2tau = dense.jac_add_mixed(q1tau, (x, y))
    q1two = dense.jac_add_mixed(q2two, (x, -y))
    q2four = dense.jac_double(q1two)
    q1minus = jac_add(q2, jac_neg(q1two))
    jacobians = [q2, q4, q1tau, q2two, q1two, q2four, q2tau, q1minus]
    affine = [(x, y)] + batch_normalize(jacobians)
    assert len(affine) == len(sparse.width4.SEEDS) == 9
    omega_base = curve(beta * x, y)
    tau_base = base - omega_base
    digest = hashlib.sha256()
    for (sx, sy), (a, b), jac in zip(affine, sparse.width4.SEEDS,
                                    [point] + jacobians):
        expected = a * base + b * tau_base
        assert expected == curve(sx, sy)
        assert dense.affine(curve, jac) == expected
        digest.update(int(sx).to_bytes(32, "big"))
        digest.update(int(sy).to_bytes(32, "big"))
    return affine, digest.hexdigest()


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    input_digest = hashlib.sha256()
    rows = []
    totals = {"preparation_m": 0, "preparation_s": 0,
              "preparation_inversions": 0, "online_m": 0,
              "online_s": 0, "generic_m_plus_s_excluding_inversions": 0,
              "tau_steps": 0, "paired_strides": 0,
              "mixed_adds": 0}
    for index in range(CASES):
        base_scalar = 1 if index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{index}") or 1
        scalar = dense.deterministic_scalar(f"{LABEL}:scalar:{index}") or 1
        input_digest.update(base_scalar.to_bytes(32, "big"))
        input_digest.update(scalar.to_bytes(32, "big"))
        base = base_scalar * generator
        seeds, seed_digest = prepare(curve, base, beta)
        point_orbit, orbit_digest = orbit.prepare_orbits(seeds, beta)
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        digits = sparse.width4.recode(a, b)
        assert sparse.width4.expand(digits) == (a, b)
        output, counts = orbit.evaluate(curve, digits, point_orbit, beta)
        expected = scalar * base
        assert output == expected
        online = sparse.generic_cost(counts)
        cold = {"m": PREP_COST["m"] + online["m"],
                "s": PREP_COST["s"] + online["s"],
                "inversions": PREP_COST["inversions"],
                "m_plus_s_excluding_inversion": 145 + online["m_plus_s"]}
        for key, amount in (
            ("preparation_m", PREP_COST["m"]),
            ("preparation_s", PREP_COST["s"]),
            ("preparation_inversions", PREP_COST["inversions"]),
            ("online_m", online["m"]), ("online_s", online["s"]),
            ("generic_m_plus_s_excluding_inversions",
             cold["m_plus_s_excluding_inversion"]),
            ("tau_steps", counts["tau_steps"]),
            ("paired_strides", counts["tau_pairs"]),
            ("mixed_adds", counts["mixed_adds"]),
        ):
            totals[key] += amount
        rows.append({
            "index": index, "base_scalar_hex": f"{base_scalar:064x}",
            "scalar_hex": f"{scalar:064x}",
            "short_a_hex": hex(a), "short_b_hex": hex(b),
            "digit_length": len(digits),
            "digit_weight": sum(digit is not None for digit in digits),
            "seed_point_sha256": seed_digest,
            "orbit_point_sha256": orbit_digest,
            "preparation": PREP_COST, "online_counts": counts,
            "online_cost": online, "cold_generic_cost": cold,
            "result_x_hex": f"{int(expected[0]):064x}",
            "result_y_hex": f"{int(expected[1]):064x}",
            "verified": True,
        })
    result = {
        "schema": 1, "kind": "256-bit-single-use-variable-base-width4-preparation",
        "label": LABEL, "curve": "secp256k1", "case_count": CASES,
        "input_sha256": input_digest.hexdigest(),
        "preparation_formula": "48M+35S Jacobian chain; 45M+8S+1I batch normalization; 9M orbit",
        "preparation_per_case": PREP_COST,
        "rows": rows, "totals": totals,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scalar_source_sha256": hashlib.sha256((HERE / "validate_scalar.py").read_bytes()).hexdigest(),
        "width4_source_sha256": hashlib.sha256((HERE / "compare_width4.py").read_bytes()).hexdigest(),
        "orbit_source_sha256": hashlib.sha256((HERE / "compare_orbit_prepared.py").read_bytes()).hexdigest(),
        "recode_source_sha256": hashlib.sha256(sparse.WIDTH4_SOURCE.read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
    }
    path = HERE / "full-prep-result.json"
    if path.exists():
        raise SystemExit("full-prep result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
