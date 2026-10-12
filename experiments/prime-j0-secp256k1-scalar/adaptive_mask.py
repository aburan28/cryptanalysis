#!/usr/bin/env python3
"""Fresh, one-use 256-bit validation of per-scalar alphabet-mask selection."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_width4 as sparse
import hybrid_holdout as previous
import hybrid_subset as hybrid
import selective_normalization as selected
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-adaptive-mask-20261007-v1"
CASES = 64


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    input_digest = hashlib.sha256()
    rows = []
    totals = {name: {"m_plus_s_excluding_inversion": 0, "inversions": 0,
                     "weight": 0, "tau_steps": 0, "paired_strides": 0,
                     "constructed_seed_points": 0}
              for name in ("selected", "width4")}
    all_recode_positions = 0
    for index in range(CASES):
        base_scalar = 1 if index == 0 else dense.deterministic_scalar(
            f"{LABEL}:base:{index}") or 1
        scalar = dense.deterministic_scalar(f"{LABEL}:scalar:{index}") or 1
        input_digest.update(base_scalar.to_bytes(32, "big"))
        input_digest.update(scalar.to_bytes(32, "big"))
        base = base_scalar * generator
        expected = scalar * base
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        scores = []
        for mask in range(64):
            digits = hybrid.recode(a, b, mask)
            model = hybrid.model(digits)
            all_recode_positions += len(digits)
            scores.append(model["m_plus_s_excluding_inversion"])
        selected_mask = min(range(64), key=lambda mask: (scores[mask], mask))
        assert selected_mask == 63 or scores[selected_mask] <= scores[63]
        arms = {}
        for name, mask in (("selected", selected_mask), ("width4", 63)):
            digits = hybrid.recode(a, b, mask)
            used, closure = hybrid.used_and_closure(digits)
            table, digest = previous.prepare_used(curve, base, beta, used,
                                                  closure)
            affine_mask = tuple(seed in used for seed in range(9))
            output, counts = selected.evaluate(curve, digits, table,
                                               affine_mask, beta)
            assert output == expected
            model = hybrid.model(digits)
            cost = previous.actual_cost(closure, used, counts)
            assert cost["m_plus_s_excluding_inversion"] == scores[mask]
            assert cost["inversions"] == model["inversions"]
            assert counts["tau_steps"] == model["tau_steps"]
            assert counts["tau_pairs"] == model["paired_strides"]
            for key, amount in (("m_plus_s_excluding_inversion",
                                 cost["m_plus_s_excluding_inversion"]),
                                ("inversions", cost["inversions"]),
                                ("weight", model["weight"]),
                                ("tau_steps", counts["tau_steps"]),
                                ("paired_strides", counts["tau_pairs"]),
                                ("constructed_seed_points",
                                 len(closure - {0}))):
                totals[name][key] += amount
            arms[name] = {"mask": mask, "model": model,
                          "actual_source_cost": cost, "counts": counts,
                          "prepared_orbit_sha256": digest, "verified": True}
        rows.append({
            "index": index, "base_scalar_hex": f"{base_scalar:064x}",
            "scalar_hex": f"{scalar:064x}", "short_a_hex": hex(a),
            "short_b_hex": hex(b), "mask_costs_m_plus_s": scores,
            "selected_mask": selected_mask, "arms": arms,
            "result_x_hex": f"{int(expected[0]):064x}",
            "result_y_hex": f"{int(expected[1]):064x}", "verified": True,
        })
    result = {
        "schema": 1, "kind": "256-bit-adaptive-mask-single-use-validation",
        "label": LABEL, "curve": "secp256k1", "case_count": CASES,
        "input_sha256": input_digest.hexdigest(), "mask_searches_per_case": 64,
        "all_recode_positions": all_recode_positions, "rows": rows,
        "totals": totals,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "hybrid_source_sha256": hashlib.sha256(
            (HERE / "hybrid_subset.py").read_bytes()).hexdigest(),
        "holdout_source_sha256": hashlib.sha256(
            (HERE / "hybrid_holdout.py").read_bytes()).hexdigest(),
        "selective_source_sha256": hashlib.sha256(
            (HERE / "selective_normalization.py").read_bytes()).hexdigest(),
        "width4_source_sha256": hashlib.sha256(
            (hybrid.OLD / "run.py").read_bytes()).hexdigest(),
        "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
        "verified": True, "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    path = HERE / "adaptive-mask-result.json"
    if path.exists():
        raise SystemExit("adaptive-mask result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "all_recode_positions": all_recode_positions,
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
