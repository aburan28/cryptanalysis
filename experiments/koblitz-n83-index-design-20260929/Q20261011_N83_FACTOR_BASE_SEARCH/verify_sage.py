#!/usr/bin/env python3
"""Independent Sage replay of the baseline and selected N83 affine base."""

from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, Integer, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = HERE / "runs/one_bit_cosets_20261011"
BRIDGE = ROOT / "experiments/compact-s3-m4-20261003/field_bridges/n83_onb_poly.json"
N = 83
D = 11
R = 2417851639230796216685689
MASK = (1 << N) - 1
KEY_BYTES = 21


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cycle() -> list[int]:
    result = []
    index = 1
    for _ in range(N):
        result.append(index - 1)
        doubled = 2 * index % (2 * N + 1)
        index = min(doubled, 2 * N + 1 - doubled)
    assert index == 1 and len(set(result)) == N
    return result


def canonical(point, to_onb, positions) -> int:
    x_coords = to_onb(point[0])
    y_coords = to_onb(point[1])
    x = sum(((x_coords >> bit) & 1) << j for j, bit in enumerate(positions))
    y = sum(((y_coords >> bit) & 1) << j for j, bit in enumerate(positions))
    best = None
    for _ in range(N):
        positive = (x << N) | y
        negative = (x << N) | (x ^ y)
        best = min(positive, negative) if best is None else min(best, positive, negative)
        x = ((x << 1) | (x >> (N - 1))) & MASK
        y = ((y << 1) | (y >> (N - 1))) & MASK
    return best


def signed_frobenius_variants(key: int) -> set[int]:
    x = key >> N
    y = key & MASK
    variants = set()
    for _ in range(N):
        variants.add((x << N) | y)
        variants.add((x << N) | (x ^ y))
        x = ((x << 1) | (x >> (N - 1))) & MASK
        y = ((y << 1) | (y >> (N - 1))) & MASK
    return variants


def main() -> None:
    started = time.perf_counter_ns()
    improved = len(sys.argv) == 2 and sys.argv[1] == "--improved"
    if len(sys.argv) > 1 and not improved:
        raise ValueError("use --improved to replay the coordinate-ascent winner")
    runtime_path = RUN / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    receipt_path = RUN / ("improve.json" if improved else "sweep.json")
    receipt = json.loads(receipt_path.read_text())
    assert receipt["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    bridge = json.loads(BRIDGE.read_text())
    assert bridge["curve_id"] == receipt["curve_id"]
    assert bridge["field_degree"] == N
    images = bridge["onb_to_poly_basis_images"]
    assert len(images) == N

    binary = GF(2)
    poly = PolynomialRing(binary, "t")
    t = poly.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**N, name="z", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert Integer(R).is_prime(proof=True)

    def from_bits(bits: int):
        return field(poly([(bits >> i) & 1 for i in range(N)]))

    gamma = [from_bits(int(bits)) for bits in images]
    columns = []
    for value in gamma:
        coeffs = list(value.polynomial().list())
        coeffs.extend([binary(0)] * (N - len(coeffs)))
        columns.append(vector(binary, coeffs))
    basis_matrix = matrix(binary, N, N, lambda i, j: columns[j][i])
    assert basis_matrix.is_invertible()
    inverse = basis_matrix.inverse()

    def from_onb(coords: int):
        result = field(0)
        while coords:
            least = coords & -coords
            result += gamma[least.bit_length() - 1]
            coords ^= least
        return result

    def to_onb(value) -> int:
        coeffs = list(field(value).polynomial().list())
        coeffs.extend([binary(0)] * (N - len(coeffs)))
        answer = inverse * vector(binary, coeffs)
        return sum(int(answer[j]) << j for j in range(N))

    for j in range(N):
        assert to_onb(gamma[j]) == 1 << j

    positions = cycle()
    results = []
    for label, row in (([("improved", receipt["winner"])] if improved else
                       [("baseline", receipt["baseline"]), ("winner", receipt["winner"])])):
        offset = row["offset_onb_coordinates"]
        observed = set()
        lifts = invalid = identities = duplicates = 0
        for u in range(1 << D):
            coords = u ^ offset
            x = from_onb(coords)
            if not coords:
                identities += 1
                continue
            c = x + x**(-2)
            if c.trace() != 0:
                invalid += 1
                continue
            term = c
            half = field(0)
            for _ in range((N + 1) // 2):
                half += term
                term = term**4
            assert half**2 + half == c
            point = curve(x, x * half)
            lifts += 1
            projected = 4 * point
            if projected == curve(0):
                identities += 1
                continue
            assert R * projected == curve(0)
            key = canonical(projected, to_onb, positions)
            if key in observed:
                duplicates += 1
            observed.add(key)
        keys = sorted(observed)
        for key in keys:
            variants = signed_frobenius_variants(key)
            assert len(variants) == 166 and min(variants) == key
        path = RUN / row["canonical_keys_file"]
        payload = b"".join(key.to_bytes(KEY_BYTES, "little") for key in keys)
        assert payload == path.read_bytes()
        assert sha(path) == row["canonical_keys_sha256"]
        assert len(keys) == row["folded_columns_K"]
        assert len(keys) * 166 == row["actual_usable_points_B"]
        assert math.comb(166 * len(keys), 5) > 0
        assert (lifts, invalid, identities, duplicates) == (
            row["valid_lifts"], row["invalid_lifts"], row["identity_projections"],
            row["duplicate_orbit_seeds"])
        results.append({"label": label, "K": len(keys), "B": 166 * len(keys),
                        "offset_bit": row["offset_bit"], "key_sha256": sha(path),
                        "full_seed_replay": True, "all_projected_points_in_subgroup": True})
    output = {"status": "PASS", "curve_id": receipt["curve_id"],
              "bridge_sha256": sha(BRIDGE), "source_receipt_sha256": sha(receipt_path),
              "verifier_sha256": sha(Path(__file__)),
              "sage_runtime_info_sha256": sha(runtime_path), "results": results,
              "replay_wall_ns": time.perf_counter_ns() - started}
    result_path = RUN / ("independent_sage_replay_improved.json" if improved else
                         "independent_sage_replay.json")
    result_path.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
