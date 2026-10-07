#!/usr/bin/env python3
"""Fresh 256-bit end-to-end test for one frozen hybrid tau alphabet."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_width4 as sparse
import full_prep as previous
import hybrid_subset as hybrid
import selective_normalization as selected
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-hybrid-holdout-20261007-v1"
CASES = 64
ARMS = {"width3": 0, "fixed_hybrid": 31, "width4": 63}
CHAIN_COST = {
    0: (0, 0), 1: (2, 5), 2: (2, 5), 3: (12, 5),
    4: (2, 5), 5: (8, 3), 6: (2, 5), 7: (8, 3), 8: (12, 4),
}


def prepare_used(curve, base, beta, used, closure):
    x, y = base[0], base[1]
    cache = {0: (x, y, x.parent()(1))}

    def get(index):
        if index in cache:
            return cache[index]
        if index == 1:
            value = dense.jac_double(get(0))
        elif index == 2:
            value = dense.jac_double(get(1))
        elif index == 3:
            tau = dense.jac_tau_scaled(get(0), 1 - beta)
            value = dense.jac_add_mixed(tau, (x, y))
        elif index == 4:
            value = dense.jac_double(get(3))
        elif index == 5:
            value = dense.jac_add_mixed(get(4), (x, -y))
        elif index == 6:
            value = dense.jac_double(get(5))
        elif index == 7:
            value = dense.jac_add_mixed(get(3), (x, y))
        elif index == 8:
            value = previous.jac_add(get(1), previous.jac_neg(get(5)))
        else:
            raise AssertionError(index)
        cache[index] = value
        return value

    for index in sorted(used):
        get(index)
    assert set(cache) == closure
    omega_base = curve(beta * x, y)
    tau_base = base - omega_base
    for index in sorted(closure):
        a, b = sparse.width4.SEEDS[index]
        assert dense.affine(curve, cache[index]) == a * base + b * tau_base

    points = [cache.get(index) for index in range(9)]
    normalized = selected.normalize_selected(points, tuple(sorted(used - {0})))
    orbit = [None] * 9
    digest = hashlib.sha256()
    for index in sorted(used):
        px, py, pz = normalized[index]
        assert pz == 1
        assert dense.affine(curve, cache[index]) == curve(px, py)
        x1 = beta * px
        x2 = -x1 - px
        assert x2 == beta**2 * px
        orbit[index] = ((px, py, pz), (x1, py, pz), (x2, py, pz))
        digest.update(index.to_bytes(1, "big"))
        for ox, oy, oz in orbit[index]:
            digest.update(int(ox).to_bytes(32, "big"))
            digest.update(int(oy).to_bytes(32, "big"))
            digest.update(int(oz).to_bytes(32, "big"))
    return orbit, digest.hexdigest()


def actual_cost(closure, used, counts):
    chain_m = sum(CHAIN_COST[index][0] for index in closure)
    chain_s = sum(CHAIN_COST[index][1] for index in closure)
    constructed = len(used - {0})
    normalize_m = 6 * constructed - 3 if constructed else 0
    normalize_s = constructed
    inversions = int(constructed > 0)
    orbit_m = len(used)
    steps, pairs = counts["tau_steps"], counts["tau_pairs"]
    mixed = counts["mixed_adds"]
    assert counts["general_adds"] == 0 and counts["first_insertions"] == 1
    online_m = 4 * steps - 2 * pairs + 8 * mixed
    online_s = 2 * steps + 3 * mixed
    return {
        "point_chain_m": chain_m, "point_chain_s": chain_s,
        "normalization_m": normalize_m, "normalization_s": normalize_s,
        "orbit_m": orbit_m, "inversions": inversions,
        "online_m": online_m, "online_s": online_s,
        "m_plus_s_excluding_inversion": (
            chain_m + chain_s + normalize_m + normalize_s +
            orbit_m + online_m + online_s),
    }


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    input_digest = hashlib.sha256()
    rows = []
    totals = {name: {"m_plus_s_excluding_inversion": 0,
                     "inversions": 0, "digit_weight": 0,
                     "tau_steps": 0, "paired_strides": 0,
                     "used_seed_points": 0,
                     "constructed_seed_points": 0}
              for name in ARMS}
    for index in range(CASES):
        base_scalar = 1 if index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{index}") or 1
        scalar = dense.deterministic_scalar(f"{LABEL}:scalar:{index}") or 1
        input_digest.update(base_scalar.to_bytes(32, "big"))
        input_digest.update(scalar.to_bytes(32, "big"))
        base = base_scalar * generator
        expected = scalar * base
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        arms = {}
        for name, mask in ARMS.items():
            digits = hybrid.recode(a, b, mask)
            used, closure = hybrid.used_and_closure(digits)
            table, digest = prepare_used(curve, base, beta, used, closure)
            affine_mask = tuple(seed in used for seed in range(9))
            output, counts = selected.evaluate(
                curve, digits, table, affine_mask, beta)
            assert output == expected
            model = hybrid.model(digits)
            cost = actual_cost(closure, used, counts)
            assert cost["m_plus_s_excluding_inversion"] == model[
                "m_plus_s_excluding_inversion"]
            assert cost["inversions"] == model["inversions"]
            assert counts["tau_steps"] == model["tau_steps"]
            assert counts["tau_pairs"] == model["paired_strides"]
            for key, amount in (
                ("m_plus_s_excluding_inversion",
                 cost["m_plus_s_excluding_inversion"]),
                ("inversions", cost["inversions"]),
                ("digit_weight", model["weight"]),
                ("tau_steps", counts["tau_steps"]),
                ("paired_strides", counts["tau_pairs"]),
                ("used_seed_points", len(used)),
                ("constructed_seed_points", len(closure - {0})),
            ):
                totals[name][key] += amount
            arms[name] = {
                "mask": mask, "digit_length": len(digits),
                "digit_weight": model["weight"],
                "used_seed_indices": sorted(used),
                "constructed_seed_indices": sorted(closure - {0}),
                "prepared_orbit_sha256": digest,
                "counts": counts, "model": model,
                "actual_source_cost": cost, "verified": True,
            }
        rows.append({
            "index": index, "base_scalar_hex": f"{base_scalar:064x}",
            "scalar_hex": f"{scalar:064x}",
            "short_a_hex": hex(a), "short_b_hex": hex(b),
            "arms": arms,
            "result_x_hex": f"{int(expected[0]):064x}",
            "result_y_hex": f"{int(expected[1]):064x}",
            "verified": True,
        })
    result = {
        "schema": 1, "kind": "256-bit-fixed-hybrid-tau-single-use-holdout",
        "label": LABEL, "curve": "secp256k1", "case_count": CASES,
        "input_sha256": input_digest.hexdigest(),
        "training_selected_mask": 31,
        "training_artifact_sha256": hashlib.sha256(
            (HERE / "hybrid-training-result.json").read_bytes()).hexdigest(),
        "arms": ARMS, "rows": rows, "totals": totals,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "hybrid_source_sha256": hashlib.sha256((HERE / "hybrid_subset.py").read_bytes()).hexdigest(),
        "selective_source_sha256": hashlib.sha256((HERE / "selective_normalization.py").read_bytes()).hexdigest(),
        "full_prep_source_sha256": hashlib.sha256((HERE / "full_prep.py").read_bytes()).hexdigest(),
        "width3_source_sha256": hashlib.sha256((hybrid.OLD / "make_tau3_fused.py").read_bytes()).hexdigest(),
        "width4_source_sha256": hashlib.sha256((hybrid.OLD / "run.py").read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    path = HERE / "hybrid-holdout-result.json"
    if path.exists():
        raise SystemExit("hybrid holdout result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
