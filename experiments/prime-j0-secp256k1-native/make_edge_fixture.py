#!/usr/bin/env python3
"""Generate Sage-checked zero and subgroup-boundary native replay cases."""

import hashlib
import json
from pathlib import Path
import sys

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent
SCALAR = HERE.parent / "prime-j0-secp256k1-scalar"
sys.path.insert(0, str(SCALAR))
import cached_projective as cached  # noqa: E402
import compare_width4 as sparse  # noqa: E402
import projective_endo as projective  # noqa: E402
import selective_normalization as choices  # noqa: E402
import validate_scalar as dense  # noqa: E402


def main():
    field = GF(dense.P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(dense.GX, dense.GY)
    assert dense.N * generator == curve(0)
    beta = field(2)**((dense.P - 1) // 3)
    lambda_tau, basis = sparse.eigenvalue_and_basis(generator, curve, beta)
    base_scalars = [1, 37, dense.deterministic_scalar(
        "prime-j0-native-edge-third-base-20261007") or 1]
    scalars = [0, 1, 2, 3, 4, 7, 8, dense.N - 1, dense.N, dense.N + 1]
    cases = []
    input_digest = hashlib.sha256()
    for base_index, base_scalar in enumerate(base_scalars):
        base = base_scalar * generator
        seeds, _ = projective.projective_seeds(curve, base, beta)
        seed_affine = [dense.affine(curve, seed) for seed in seeds]
        table, _ = choices.make_orbits(seeds, beta)
        for scalar_index, scalar in enumerate(scalars):
            expected = scalar * base
            a, b = dense.short_representative(scalar, lambda_tau, basis)
            digits = sparse.width4.recode(a, b)
            assert sparse.width4.expand(digits) == (a, b)
            output, counts = cached.cached_evaluate(curve, digits, table, beta)
            assert output == expected
            input_digest.update(base_scalar.to_bytes(32, "big"))
            input_digest.update(scalar.to_bytes(33, "big"))
            identity = expected == curve(0)
            cases.append({
                "index": len(cases), "base_index": base_index,
                "scalar_index": scalar_index,
                "base_x_hex": f"{int(base[0]):064x}",
                "base_y_hex": f"{int(base[1]):064x}",
                "scalar_hex": f"{scalar:x}",
                "short_a_hex": hex(a), "short_b_hex": hex(b),
                "digits": [list(digit) if digit is not None else None
                           for digit in digits],
                "seed_affine": [[f"{int(point[0]):064x}",
                                 f"{int(point[1]):064x}"]
                                for point in seed_affine],
                "expected_identity": identity,
                "expected_x_hex": None if identity else f"{int(expected[0]):064x}",
                "expected_y_hex": None if identity else f"{int(expected[1]):064x}",
                "expected_counts": counts,
            })
    assert len(cases) == 30
    fixture = {
        "schema": 1, "kind": "native-point-path-edge-controls",
        "curve": "secp256k1", "beta_hex": f"{int(beta):064x}",
        "input_sha256": input_digest.hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": cases,
    }
    target = HERE / "edge-fixture.json"
    if target.exists():
        raise SystemExit("edge fixture exists; refusing overwrite")
    target.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases),
                      "input_sha256": fixture["input_sha256"],
                      "fixture_sha256": hashlib.sha256(target.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
