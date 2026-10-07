#!/usr/bin/env python3
"""Cross-check the paired-tau and carried-gauge formulas on secp256k1.

Launch with /Volumes/SSD990/cryptanalysis/sage -python validate.py.
This is a correctness check of the formulas, not a scalar timing result.
"""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF


HERE = Path(__file__).resolve().parent
LABEL = "prime-j0-secp256k1-pair-20261007-v1"
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
SAMPLES = 64


def affine(curve, jac):
    x, y, z = jac
    if z == 0:
        return curve(0)
    return curve(x / z**2, y / z**3)


def jac_tau(jac, beta):
    x, y, z = jac
    if z == 0 or x == 0:
        return 0, x.parent()(1), x.parent()(0)
    x3 = x**3
    rx = 4 * y**2 - 3 * x3
    return rx, y * (3 * x3 - 2 * rx), (1 - beta) * x * z


def jac_triple(jac):
    x, y, z = jac
    if z == 0 or x == 0:
        return 0, x.parent()(1), x.parent()(0)
    x3 = x**3
    tx = 4 * y**2 - 3 * x3
    ty = y * (3 * x3 - 2 * tx)
    rx = 4 * ty**2 - 3 * tx**3
    return rx, ty * (3 * tx**3 - 2 * rx), 3 * tx * x * z


def jac_tau_pair(jac, beta, change):
    x, y, z = jac_triple(jac)
    if z == 0:
        return x, y, z
    if change == 2:
        return x, y, -z
    return x, y, -(beta ** (change + 1)) * z


def main():
    field = GF(P)
    curve = EllipticCurve(field, [0, 7])
    generator = curve(GX, GY)
    assert N * generator == curve(0)
    beta = field(2) ** ((P - 1) // 3)
    assert beta != 1 and beta**3 == 1 and 1 + beta + beta**2 == 0

    def omega(point, power=1):
        if point == curve(0):
            return point
        return curve(beta**power * point[0], point[1])

    digest = hashlib.sha256()
    checks = {"tau": 0, "triple": 0, "pair": 0, "tau_square": 0}
    for index in range(SAMPLES):
        scalar = int.from_bytes(hashlib.sha256(
            f"{LABEL}:scalar:{index}".encode()).digest(), "big") % (N - 1) + 1
        point = scalar * generator
        tau_point = point - omega(point)
        tau_square = tau_point - omega(tau_point)
        assert tau_square == -3 * omega(point)
        checks["tau_square"] += 1
        digest.update(scalar.to_bytes(32, "big"))
        digest.update(int(point[0]).to_bytes(32, "big"))
        digest.update(int(point[1]).to_bytes(32, "big"))
        for scale_index in range(3):
            scale = field(1 if scale_index == 0 else 2 if scale_index == 1 else
                          int.from_bytes(hashlib.sha256(
                              f"{LABEL}:scale:{index}".encode()).digest(), "big") % P)
            assert scale != 0
            jac = scale**2 * point[0], scale**3 * point[1], scale
            assert affine(curve, jac_tau(jac, beta)) == tau_point
            checks["tau"] += 1
            assert affine(curve, jac_triple(jac)) == 3 * point
            checks["triple"] += 1
            for change in range(3):
                assert affine(curve, jac_tau_pair(jac, beta, change)) == omega(
                    tau_square, change)
                checks["pair"] += 1

    result = {
        "schema": 1,
        "kind": "256-bit-formula-correctness-only",
        "label": LABEL,
        "curve": "secp256k1",
        "field_modulus_hex": f"{P:064x}",
        "subgroup_order_hex": f"{N:064x}",
        "beta_hex": f"{int(beta):064x}",
        "samples": SAMPLES,
        "projective_scales_per_sample": 3,
        "checks": checks,
        "input_point_sha256": digest.hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "verified": True,
        "cpu_speedup_claim": None,
    }
    path = HERE / "result.json"
    if path.exists():
        raise SystemExit("result already exists; refusing overwrite")
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verified": True, "checks": checks,
                      "input_point_sha256": digest.hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
