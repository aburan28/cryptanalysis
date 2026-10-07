#!/usr/bin/env python3
"""Fresh comparison of Jacobian seed orbit readdition with Z powers cached."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_orbit_prepared as orbit_control
import compare_width4 as sparse
import projective_endo as projective
import selective_normalization as choices
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-cached-projective-20261007-v1"
CASES = 64


def jac_add_cached(first, second, second_z2, second_z3):
    """Jacobian addition reusing Z2² and Z2³: 11M+3S on generic inputs."""
    x1, y1, z1 = first
    x2, y2, z2 = second
    if z1 == 0 or z2 == 0:
        raise ValueError("cached addition encountered identity")
    z1_squared = z1**2
    u1, u2 = x1 * second_z2, x2 * z1_squared
    s1, s2 = y1 * second_z3, y2 * z1 * z1_squared
    h, r = u2 - u1, s2 - s1
    if h == 0:
        raise ValueError("cached addition encountered exceptional inputs")
    hh = h**2
    hhh, v = h * hh, u1 * hh
    rx = r**2 - hhh - 2 * v
    ry = r * (v - rx) - s1 * hhh
    rz = z1 * z2 * h
    return rx, ry, rz


def cached_evaluate(curve, digits, table, beta):
    cache_seeds = {digit[2] for digit in digits[:-1]
                   if digit is not None and digit[2] != 0}
    cache = {}
    for seed in sorted(cache_seeds):
        z = table[seed][0][2]
        square = z**2
        cache[seed] = square, square * z
        assert all(point[2] == z for point in table[seed])
    field = beta.parent()
    jac = field(0), field(1), field(0)
    counts = {"tau_steps": 0, "tau_pairs": 0,
              "cheap_z_pairs": 0, "mixed_adds": 0,
              "general_adds": 0, "first_insertions": 0,
              "cache_entries": len(cache)}
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
            elif seed == 0:
                assert qz == 1
                jac = dense.jac_add_mixed(jac, (qx, qy))
                counts["mixed_adds"] += 1
            else:
                zz, zzz = cache[seed]
                jac = jac_add_cached(jac, (qx, qy, qz), zz, zzz)
                counts["general_adds"] += 1
        index -= 1
    assert counts["tau_pairs"] == pairs
    assert counts["cheap_z_pairs"] == pairs
    assert gauge == 0 and counts["first_insertions"] == 1
    assert (counts["first_insertions"] + counts["mixed_adds"] +
            counts["general_adds"] == sum(d is not None for d in digits))
    return dense.affine(curve, jac), counts


def candidate_cost(counts):
    pairs, steps = counts["tau_pairs"], counts["tau_steps"]
    mixed, general = counts["mixed_adds"], counts["general_adds"]
    cached = counts["cache_entries"]
    m = 51 + cached
    s = 32 + cached
    online_m = 4 * steps - 2 * pairs + 8 * mixed + 11 * general
    online_s = 2 * steps + 3 * mixed + 3 * general
    return {"preparation_m": m, "preparation_s": s,
            "preparation_inversions": 0,
            "online_m": online_m, "online_s": online_s,
            "m_plus_s_excluding_inversion": m + s + online_m + online_s}


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
                     "mixed_adds": 0, "general_adds": 0,
                     "cache_entries": 0}
              for name in ("uncached", "cached")}
    for index in range(CASES):
        base_scalar = 1 if index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{index}") or 1
        scalar = dense.deterministic_scalar(f"{LABEL}:scalar:{index}") or 1
        input_digest.update(base_scalar.to_bytes(32, "big"))
        input_digest.update(scalar.to_bytes(32, "big"))
        base = base_scalar * generator
        expected = scalar * base
        seeds, seed_digest = projective.projective_seeds(curve, base, beta)
        table, orbit_digest = choices.make_orbits(seeds, beta)
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        digits = sparse.width4.recode(a, b)
        assert sparse.width4.expand(digits) == (a, b)
        mask = tuple(index == 0 for index in range(9))
        control_out, control_counts = choices.evaluate(
            curve, digits, table, mask, beta)
        candidate_out, candidate_counts = cached_evaluate(
            curve, digits, table, beta)
        assert control_out == candidate_out == expected
        assert (candidate_counts["general_adds"] ==
                control_counts["general_adds"])
        assert (candidate_counts["mixed_adds"] ==
                control_counts["mixed_adds"])
        assert (candidate_counts["tau_steps"] ==
                control_counts["tau_steps"])
        assert (candidate_counts["tau_pairs"] ==
                control_counts["tau_pairs"])
        control_cost = projective.source_cost(control_counts, 0)
        new_cost = candidate_cost(candidate_counts)
        expected_saving = (control_counts["general_adds"] -
                           candidate_counts["cache_entries"])
        assert control_cost["preparation_m"] + control_cost["online_m"] - (
            new_cost["preparation_m"] + new_cost["online_m"]) == expected_saving
        assert control_cost["preparation_s"] + control_cost["online_s"] - (
            new_cost["preparation_s"] + new_cost["online_s"]) == expected_saving
        arms = {}
        for name, counts, cost in (("uncached", control_counts, control_cost),
                                   ("cached", candidate_counts, new_cost)):
            for key in ("preparation_m", "preparation_s",
                        "preparation_inversions", "online_m", "online_s",
                        "m_plus_s_excluding_inversion"):
                totals[name][key] += cost[key]
            for key in ("mixed_adds", "general_adds"):
                totals[name][key] += counts[key]
            if name == "cached":
                totals[name]["cache_entries"] += counts["cache_entries"]
            arms[name] = {"counts": counts, "source_cost": cost,
                          "verified": True}
        rows.append({"index": index,
                     "base_scalar_hex": f"{base_scalar:064x}",
                     "scalar_hex": f"{scalar:064x}",
                     "short_a_hex": hex(a), "short_b_hex": hex(b),
                     "digit_length": len(digits),
                     "digit_weight": sum(d is not None for d in digits),
                     "seed_point_sha256": seed_digest,
                     "orbit_sha256": orbit_digest,
                     "arms": arms,
                     "saving_m": expected_saving,
                     "saving_s": expected_saving,
                     "result_x_hex": f"{int(expected[0]):064x}",
                     "result_y_hex": f"{int(expected[1]):064x}",
                     "verified": True})
    result = {"schema": 1,
              "kind": "256-bit-cached-projective-seed-orbit",
              "label": LABEL, "curve": "secp256k1", "case_count": CASES,
              "input_sha256": input_digest.hexdigest(),
              "rows": rows, "totals": totals,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "projective_source_sha256": hashlib.sha256((HERE / "projective_endo.py").read_bytes()).hexdigest(),
              "selective_source_sha256": hashlib.sha256((HERE / "selective_normalization.py").read_bytes()).hexdigest(),
              "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
              "verified": True, "cpu_speedup_claim": None,
              "academic_novelty_claim": None}
    path = HERE / "cached-projective-result.json"
    if path.exists():
        raise SystemExit("cached-projective result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
