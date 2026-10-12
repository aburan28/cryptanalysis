#!/usr/bin/env python3
"""Independently replay shifted widths 15 and 16 in checked Sage."""

import hashlib
import json
import math
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, Integer, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = ROOT / "experiments/koblitz-n83-index-design-20260929/Q20261011_N83_FACTOR_BASE_SEARCH"
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
sys.path.insert(0, str(PRIOR))
from verify_sage import canonical, cycle, signed_frobenius_variants  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output_path = HERE / "independent_sage_replay.json"
    assert not output_path.exists(), "refusing to overwrite independent replay"
    started = time.perf_counter_ns()
    receipt_path = HERE / "frontier.json"
    receipt = json.loads(receipt_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    bridge = json.loads(BRIDGE.read_text())
    assert bridge["curve_id"] == receipt["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert bridge["field_degree"] == 83
    order = Integer(2417851639230796216685689)
    assert order.is_prime(proof=True)
    binary = GF(2)
    poly = PolynomialRing(binary, "t")
    t = poly.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    images = bridge["onb_to_poly_basis_images"]
    assert len(images) == 83

    def from_bits(bits):
        return field(poly([(int(bits) >> i) & 1 for i in range(83)]))

    gamma = [from_bits(value) for value in images]
    columns = []
    for value in gamma:
        coeffs = list(value.polynomial().list())
        coeffs.extend([binary(0)] * (83 - len(coeffs)))
        columns.append(vector(binary, coeffs))
    basis = matrix(binary, 83, 83, lambda i, j: columns[j][i])
    assert basis.is_invertible()
    inverse = basis.inverse()

    def from_onb(coords):
        result = field(0)
        while coords:
            least = coords & -coords
            result += gamma[least.bit_length() - 1]
            coords ^= least
        return result

    def to_onb(value):
        coeffs = list(field(value).polynomial().list())
        coeffs.extend([binary(0)] * (83 - len(coeffs)))
        answer = inverse * vector(binary, coeffs)
        return sum(int(answer[j]) << j for j in range(83))

    for j in range(83):
        assert to_onb(gamma[j]) == 1 << j
    positions = cycle()
    results = []
    for row in receipt["rows"]:
        dimension = row["dimension"]
        offset = row["offset_onb_coordinates"]
        keys = set()
        valid = invalid = projected_identity = duplicates = 0
        for seed in range(1 << dimension):
            coords = seed ^ offset
            if not coords:
                invalid += 1
                continue
            x = from_onb(coords)
            rhs = x + x**(-2)
            if rhs.trace() != 0:
                invalid += 1
                continue
            term = rhs
            half = field(0)
            for _ in range(42):
                half += term
                term = term**4
            assert half**2 + half == rhs
            point = curve(x, x * half)
            valid += 1
            projected = 4 * point
            if projected == curve(0):
                projected_identity += 1
                continue
            assert order * projected == curve(0)
            key = canonical(projected, to_onb, positions)
            if key in keys:
                duplicates += 1
            keys.add(key)
        ordered = sorted(keys)
        payload = b"".join(key.to_bytes(21, "little") for key in ordered)
        path = HERE / row["canonical_key_file"]
        assert payload == path.read_bytes()
        assert sha(path) == row["canonical_key_sha256"]
        assert (valid, invalid, projected_identity, duplicates) == (
            row["valid_lifts"], row["invalid_or_zero_lifts"],
            row["identity_projections"], row["duplicate_orbit_seeds"])
        assert len(keys) == row["folded_columns_K"]
        assert 166 * len(keys) == row["actual_usable_points_B_before_folding"]
        assert 83 * len(keys) ** 2 == row["full_pair_root_states"]
        assert 32 * row["full_pair_root_states"] == row[
            "compact16_root_payload_bytes"]
        assert 64 * row["full_pair_root_states"] == row[
            "cached_xy_payload_bytes"]
        assert math.comb(166 * len(keys), 4) > 0
        for key in ordered:
            variants = signed_frobenius_variants(key)
            assert len(variants) == 166 and min(variants) == key
        results.append({"dimension": dimension, "offset": offset,
                        "K": len(keys), "B": 166 * len(keys),
                        "key_sha256": sha(path), "full_seed_replay": True})
        print(json.dumps(results[-1]), flush=True)
    report = {"status": "PASS", "curve_id": receipt["curve_id"],
              "results": results, "source_receipt_sha256": sha(receipt_path),
              "bridge_sha256": sha(BRIDGE),
              "prior_sage_verifier_sha256": sha(PRIOR / "verify_sage.py"),
              "verifier_sha256": sha(Path(__file__)),
              "sage_runtime_info_sha256": sha(runtime_path),
              "replay_wall_ns": time.perf_counter_ns() - started}
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
