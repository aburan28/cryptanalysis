#!/usr/bin/env python3
"""Freeze a fresh uniform one-target n=83 DLP fixture without its scalar.

Run this only with the repository's checked Sage launcher. The scalar exists
only in this process; search workers receive the public point record.
"""

import argparse
import hashlib
import json
import secrets
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

import verify_n83_quotient_receipt_sage as independent
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_full_spill_screen.json"
DEFAULT_OUT = HERE / "n83_holdout_target_20261001.json"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite frozen target"
    runtime = json.loads(args.runtime_info.read_text())
    assert runtime["status"] == "verified"
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    identity = screen["curve_identity_record"]
    model = identity["curve"]
    order = model["subgroup_order"]

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    binary = GF(2**83, name="z", modulus=modulus)
    gamma = independent.gamma_to_polynomial_bits()

    def element(raw):
        coords = independent.raw_to_coords(int(raw))
        bits = 0
        while coords:
            least = coords & -coords
            bits ^= gamma[least.bit_length() - 1]
            coords ^= least
        return binary(ring([(bits >> i) & 1 for i in range(83)]))

    curve = EllipticCurve(binary, [model[f"a{i}"] for i in (1, 2, 3, 4, 6)])
    generator = curve(*(element(raw) for raw in model["generator"]))
    assert generator != curve(0) and order * generator == curve(0)
    scalar = secrets.randbelow(order - 1) + 1
    target_sage = scalar * generator
    assert target_sage != curve(0) and order * target_sage == curve(0)

    # Encode through the normal-basis table, then decode and replay in Sage.
    # Invert the normal-basis map with a GF(2) matrix solve.
    from sage.all import matrix, vector
    columns = [[(g >> row) & 1 for row in range(83)] for g in gamma]
    basis = matrix(GF(2), 83, 83,
                   lambda row, col: columns[col][row])
    assert basis.is_invertible()

    def encode(value):
        polynomial_bits = sum(int(coefficient) << i for i, coefficient
                              in enumerate(value.polynomial().list()))
        coords = basis.solve_right(vector(GF(2), [
            (polynomial_bits >> i) & 1 for i in range(83)]))
        coordinate_bits = sum(int(coords[i]) << i for i in range(83))
        raw = sum(((coordinate_bits >> (i - 1)) & 1) *
                  ((1 << i) | (1 << (167 - i))) for i in range(1, 84))
        assert element(raw) == value
        return raw

    target = [encode(target_sage[0]), encode(target_sage[1])]
    assert curve(*(element(raw) for raw in target)) == target_sage
    assert target != screen["public_target"]
    workload = {
        "schema_version": 1,
        "curve_id": screen["curve_id"],
        "subgroup_order": order,
        "generator": model["generator"],
        "targets": [target],
        "input_law": "one uniform nonzero secret scalar times G; scalar discarded before search",
        "target_count": 1,
        "cache_state": "reusable known-log factor base, no target-dependent cache",
    }
    workload_digest = hashlib.sha256(canonical(workload)).hexdigest()
    record = {
        "kind": "n83_fresh_holdout_public_target",
        "curve_id": screen["curve_id"],
        "curve_identity_record": identity,
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": target,
        "workload": workload,
        "workload_id": workload_digest[:12],
        "workload_record_sha256": workload_digest,
        "sage_scalar_replay_at_freeze": True,
        "fixture_scalar_retained": False,
        "sage_runtime_info_sha256": hashlib.sha256(
            args.runtime_info.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.out.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"curve_id": record["curve_id"],
                      "workload_id": record["workload_id"],
                      "public_target": target,
                      "fixture_scalar_retained": False}))


if __name__ == "__main__":
    main()
