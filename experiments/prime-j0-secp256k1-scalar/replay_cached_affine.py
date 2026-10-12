#!/usr/bin/env python3
"""Replay the affine seed control on the frozen cached-projective cases."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF

import compare_width4 as sparse
import endo_seed_prep as optimized
import projective_endo as projective
import selective_normalization as choices
import validate_scalar as dense


HERE = Path(__file__).resolve().parent
INPUT = HERE / "cached-projective-result.json"


def main():
    prior = json.loads(INPUT.read_text())
    assert prior["verified"] and prior["case_count"] == len(prior["rows"]) == 64
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    rows = []
    totals = {"affine_m": 0, "affine_s": 0,
              "affine_preparation_inversions": 0,
              "cached_projective_m": 0, "cached_projective_s": 0,
              "break_even_m": 0, "break_even_s": 0}
    for saved in prior["rows"]:
        base_scalar = int(saved["base_scalar_hex"], 16)
        scalar = int(saved["scalar_hex"], 16)
        base = base_scalar * generator
        expected = scalar * base
        assert f"{int(expected[0]):064x}" == saved["result_x_hex"]
        assert f"{int(expected[1]):064x}" == saved["result_y_hex"]
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        assert (hex(a), hex(b)) == (saved["short_a_hex"],
                                     saved["short_b_hex"])
        digits = sparse.width4.recode(a, b)
        assert sparse.width4.expand(digits) == (a, b)
        seeds, seed_digest = optimized.prepare_optimized(curve, base, beta)
        assert seed_digest == saved["seed_point_sha256"]
        table, orbit_digest = choices.make_orbits(
            [(x, y, field(1)) for x, y in seeds], beta)
        affine_mask = (True,) * 9
        output, counts = choices.evaluate(curve, digits, table,
                                          affine_mask, beta)
        assert output == expected
        cached_counts = saved["arms"]["cached"]["counts"]
        assert counts["tau_steps"] == cached_counts["tau_steps"]
        assert counts["tau_pairs"] == cached_counts["tau_pairs"]
        assert (counts["mixed_adds"] + counts["general_adds"] ==
                cached_counts["mixed_adds"] + cached_counts["general_adds"])
        affine = projective.source_cost(counts, 8)
        cached = saved["arms"]["cached"]["source_cost"]
        assert affine["preparation_inversions"] == 1
        assert cached["preparation_inversions"] == 0
        affine_m = affine["preparation_m"] + affine["online_m"]
        affine_s = affine["preparation_s"] + affine["online_s"]
        cached_m = cached["preparation_m"] + cached["online_m"]
        cached_s = cached["preparation_s"] + cached["online_s"]
        for key, amount in (("affine_m", affine_m), ("affine_s", affine_s),
                            ("affine_preparation_inversions", 1),
                            ("cached_projective_m", cached_m),
                            ("cached_projective_s", cached_s),
                            ("break_even_m", cached_m - affine_m),
                            ("break_even_s", cached_s - affine_s)):
            totals[key] += amount
        rows.append({"index": saved["index"],
                     "base_scalar_hex": saved["base_scalar_hex"],
                     "scalar_hex": saved["scalar_hex"],
                     "seed_sha256": seed_digest,
                     "affine_orbit_sha256": orbit_digest,
                     "affine_counts": counts, "affine_cost": affine,
                     "cached_projective_cost": cached,
                     "break_even_m": cached_m - affine_m,
                     "break_even_s": cached_s - affine_s,
                     "break_even_m_plus_s": (
                         cached_m + cached_s - affine_m - affine_s),
                     "result_x_hex": saved["result_x_hex"],
                     "result_y_hex": saved["result_y_hex"],
                     "verified": True})
    result = {"schema": 1,
              "kind": "256-bit-cached-projective-versus-affine-replay",
              "case_count": len(rows), "input_sha256": prior["input_sha256"],
              "input_artifact_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
              "rows": rows, "totals": totals,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cached_source_sha256": hashlib.sha256((HERE / "cached_projective.py").read_bytes()).hexdigest(),
              "endo_source_sha256": hashlib.sha256((HERE / "endo_seed_prep.py").read_bytes()).hexdigest(),
              "formula_source_sha256": hashlib.sha256(dense.FORMULAS.read_bytes()).hexdigest(),
              "verified": True, "cpu_speedup_claim": None,
              "academic_novelty_claim": None}
    path = HERE / "cached-affine-replay-result.json"
    if path.exists():
        raise SystemExit("cached-affine replay result exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "cases": len(rows),
                      "input_sha256": result["input_sha256"],
                      "totals": totals}, sort_keys=True))


if __name__ == "__main__":
    main()
