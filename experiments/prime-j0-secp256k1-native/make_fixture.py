#!/usr/bin/env python3
"""Freeze Sage points and width-four digits for native point-path replay."""

import hashlib
import json
from pathlib import Path
import sys

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent
SCALAR = HERE.parent / "prime-j0-secp256k1-scalar"
sys.path.insert(0, str(SCALAR))
import compare_width4 as sparse  # noqa: E402
import projective_endo as projective  # noqa: E402
import validate_scalar as dense  # noqa: E402


def main():
    source = SCALAR / "cached-projective-result.json"
    saved = json.loads(source.read_text())
    assert saved["verified"] and len(saved["rows"]) == 64
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    cases = []
    for row in saved["rows"]:
        base_scalar = int(row["base_scalar_hex"], 16)
        scalar = int(row["scalar_hex"], 16)
        base = base_scalar * generator
        expected = scalar * base
        assert f"{int(expected[0]):064x}" == row["result_x_hex"]
        assert f"{int(expected[1]):064x}" == row["result_y_hex"]
        a, b = dense.short_representative(scalar, lambda_tau, basis)
        assert (hex(a), hex(b)) == (row["short_a_hex"], row["short_b_hex"])
        digits = sparse.width4.recode(a, b)
        assert sparse.width4.expand(digits) == (a, b)
        seeds, _ = projective.projective_seeds(curve, base, beta)
        seed_affine = [dense.affine(curve, seed) for seed in seeds]
        cases.append({
            "index": row["index"],
            "base_x_hex": f"{int(base[0]):064x}",
            "base_y_hex": f"{int(base[1]):064x}",
            "scalar_hex": row["scalar_hex"],
            "short_a_hex": row["short_a_hex"],
            "short_b_hex": row["short_b_hex"],
            "digits": [list(digit) if digit is not None else None
                       for digit in digits],
            "seed_affine": [[f"{int(point[0]):064x}",
                             f"{int(point[1]):064x}"]
                            for point in seed_affine],
            "expected_x_hex": row["result_x_hex"],
            "expected_y_hex": row["result_y_hex"],
            "expected_counts": row["arms"]["cached"]["counts"],
        })
    fixture = {
        "schema": 1, "kind": "native-point-path-frozen-sage-fixture",
        "curve": "secp256k1", "beta_hex": f"{int(beta):064x}",
        "input_sha256": saved["input_sha256"],
        "source_result_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": cases,
    }
    target = HERE / "fixture.json"
    if target.exists():
        raise SystemExit("native fixture exists; refusing overwrite")
    target.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases),
                      "input_sha256": fixture["input_sha256"],
                      "fixture_sha256": hashlib.sha256(target.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
