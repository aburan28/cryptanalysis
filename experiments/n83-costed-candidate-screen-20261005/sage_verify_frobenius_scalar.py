#!/usr/bin/env python3
"""Certify the scalar action of N83 Frobenius on the public prime subgroup."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_full_w4_geometry_v1/geometry.json"
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out: Path) -> None:
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime in the output directory first")
    receipt_path = out / "frobenius_scalar.json"
    if receipt_path.exists():
        raise FileExistsError("receipt is immutable")
    started = time.perf_counter_ns()
    protocol = json.loads(PROTOCOL.read_text())
    baseline = json.loads(BASELINE.read_text())
    assert sha(BASELINE) == protocol["baseline_full_w4_geometry_sha256"]
    record = baseline["curve_identity_record"]
    assert baseline["curve_id"] == protocol["curve_id"]
    n = protocol["field_degree"]
    r = ZZ(protocol["subgroup_order_decimal"])
    h = protocol["cofactor"]
    f2 = GF(2)
    poly = PolynomialRing(f2, "z")
    z = poly.gen()
    modulus = z**n + z**7 + z**4 + z**2 + 1
    field = GF(2**n, "a", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert ZZ(r).is_prime(proof=True)
    assert curve.cardinality() == h * r == record["curve"]["curve_order"]

    def element(code: int):
        return field(poly([(code >> bit) & 1 for bit in range(n)]))

    gx, gy = record["curve"]["G"]
    generator = curve(element(gx), element(gy))
    identity = curve(0)
    assert generator != identity and r * generator == identity
    frobenius_g = curve(generator[0]**2, generator[1]**2)
    q = ZZ(1) << n
    t = ZZ(record["curve"]["trace"])
    assert t == q + 1 - curve.cardinality()
    base_curve = EllipticCurve(GF(2), [1, 0, 0, 0, 1])
    t_one = ZZ(3) - base_curve.cardinality()
    assert t_one == -1
    fr = GF(r)
    ring = PolynomialRing(fr, "u")
    u = ring.gen()
    roots = (u**2 - fr(t_one)*u + fr(2)).roots()
    assert len(roots) == 2 and all(multiplicity == 1 for _, multiplicity in roots)
    matching = [ZZ(value) for value, _ in roots
                if ZZ(value) * generator == frobenius_g]
    assert len(matching) == 1
    scalar = matching[0]
    assert scalar != 1 and pow(int(scalar), n, int(r)) == 1
    assert n * generator != identity
    assert n == 83 and ZZ(n).is_prime(proof=True)
    assert curve(frobenius_g[0]**(2**(n-1)),
                 frobenius_g[1]**(2**(n-1))) == generator
    receipt = {
        "schema_version": 1, "kind": "n83_frobenius_subgroup_scalar",
        "status": "VERIFIED", "candidate_id": None,
        "curve_id": protocol["curve_id"], "subgroup_order": str(r),
        "field_cardinality": str(q), "extension_trace": str(t),
        "base_field_trace": str(t_one),
        "characteristic_polynomial_mod_r": "u^2+u+2",
        "roots_mod_r_decimal": [str(ZZ(value)) for value, _ in roots],
        "lambda_decimal": str(scalar), "lambda_order": n,
        "certificate": "F(G)=[lambda]G; lambda^83=1 mod r; r prime and G has order r. "
        "Therefore F(P)=[lambda]P for every P in <G>.",
        "protocol_sha256": sha(PROTOCOL), "baseline_sha256": sha(BASELINE),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "lambda_decimal", "lambda_order")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    main(parser.parse_args().out)
