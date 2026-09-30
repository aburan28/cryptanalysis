#!/usr/bin/env python3
"""Replay an n=83 quotient relation in Sage from archived keys and logs.

The search runner uses the repository's Python point code and a native C++
kernel. This verifier converts the archived type-II ONB coordinates to the
polynomial basis and uses Sage's independent elliptic-curve arithmetic.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_full_spill_screen.json"
HEADER = HERE.parents[1] / "ecc2k130" / "runner" / "generated" / "eccF83.h"
N = 83
L = 2 * N
MASK = (1 << N) - 1
RING_BITS = 2 * N + 1
RING_MASK = (1 << RING_BITS) - 1
KEY_BYTES = 21
LOG_BYTES = 11
RECORD_BYTES = KEY_BYTES + LOG_BYTES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gamma_to_polynomial_bits():
    source = HEADER.read_text()
    block = source.split("GAMMA_TO_PB[83][3] = {", 1)[1].split("};", 1)[0]
    rows = re.findall(
        r"\{\s*(0x[0-9a-f]+)ull,\s*(0x[0-9a-f]+)ull,\s*(0x[0-9a-f]+)ull\s*\}",
        block,
    )
    assert len(rows) == N
    values = []
    for low, high, upper in rows:
        assert int(upper, 16) == 0
        value = int(low, 16) | (int(high, 16) << 64)
        assert value < (1 << N)
        values.append(value)
    return values


def coordinate_cycle():
    cycle = []
    index = 1
    for _ in range(N):
        cycle.append(index - 1)
        doubled = 2 * index % RING_BITS
        index = min(doubled, RING_BITS - doubled)
    assert index == 1 and len(set(cycle)) == N
    return cycle


def raw_to_coords(raw):
    assert 0 <= raw <= RING_MASK
    if raw & 1:
        raw ^= RING_MASK
    assert (raw & 1) == 0
    for i in range(1, N + 1):
        assert ((raw >> i) & 1) == ((raw >> (RING_BITS - i)) & 1)
    return (raw >> 1) & MASK


def rotate_left(value, shift):
    shift %= N
    return ((value << shift) | (value >> (N - shift))) & MASK


def key_point_and_log(index, data, cycle, eigenvalue, subgroup_order):
    assert 0 <= index < len(data) // RECORD_BYTES * L
    orbit_index, within = divmod(index, L)
    start = orbit_index * RECORD_BYTES
    key = int.from_bytes(data[start:start + KEY_BYTES], "little")
    canonical_log = int.from_bytes(
        data[start + KEY_BYTES:start + RECORD_BYTES], "little")
    assert canonical_log < subgroup_order
    x_cycle = key >> N
    y_cycle = key & MASK
    assert x_cycle <= MASK
    shift = within % N
    x_cycle = rotate_left(x_cycle, shift)
    y_cycle = rotate_left(y_cycle, shift)
    if within >= N:
        y_cycle ^= x_cycle
    x_coords = y_coords = 0
    for position, coordinate in enumerate(cycle):
        x_coords |= ((x_cycle >> position) & 1) << coordinate
        y_coords |= ((y_cycle >> position) & 1) << coordinate
    point_log = canonical_log * pow(eigenvalue, shift, subgroup_order)
    if within >= N:
        point_log = -point_log
    return (x_coords, y_coords), point_log % subgroup_order


def verify(receipt_path, runtime_path):
    screen = json.loads(SCREEN.read_text())
    receipt = json.loads(receipt_path.read_text())
    runtime = json.loads(runtime_path.read_text())
    assert runtime["status"] == "verified"
    identity = screen["curve_identity_record"]
    assert identity["field"]["n"] == N and identity["field"]["p"] == 2
    assert receipt["curve_id"] == screen["curve_id"]
    assert receipt["curve_identity_record"] == identity
    assert receipt["isogeny"] == screen["isogeny"] == "none"
    public_target = "public_target" in receipt
    if public_target:
        assert receipt["public_target"] == screen["public_target"]
    else:
        assert "fixture_target" in receipt
    base = screen["factor_base"]
    if "factor_base" in receipt:
        assert receipt["factor_base"] == base
    else:
        assert receipt["factor_base_enumerated_set_sha256"] == base[
            "enumerated_set_sha256"]
    data_path = HERE / base["key_and_log_file"]
    data = data_path.read_bytes()
    assert len(data) == base["key_and_log_file_bytes"]
    assert sha(data_path) == base["key_and_log_file_sha256"]
    assert len(data) // RECORD_BYTES == base["signed_frobenius_columns"]
    assert base["actual_usable_points_B_before_folding"] == (
        L * base["signed_frobenius_columns"])

    binary = GF(2)
    polynomial_ring = PolynomialRing(binary, "t")
    t = polynomial_ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**N, name="z", modulus=modulus)
    gamma = gamma_to_polynomial_bits()
    identity_bits = 0
    for value in gamma:
        identity_bits ^= value
    assert identity_bits == 1, "sum of type-II normal basis elements is one"

    def element(coords):
        assert 0 <= coords <= MASK
        bits = 0
        while coords:
            least = coords & -coords
            bits ^= gamma[least.bit_length() - 1]
            coords ^= least
        return field(polynomial_ring([(bits >> i) & 1 for i in range(N)]))

    # Validate the archived ONB-to-polynomial table against field arithmetic,
    # independently of the point and quotient-key implementations.
    for i in range(1, N + 1):
        doubled = 2 * i % RING_BITS
        image = min(doubled, RING_BITS - doubled)
        assert element(1 << (i - 1))**2 == element(1 << (image - 1))

    def point_from_coords(coords):
        return curve(element(coords[0]), element(coords[1]))

    def point_from_raw(encoded):
        return point_from_coords(tuple(raw_to_coords(int(v)) for v in encoded))

    model = identity["curve"]
    curve = EllipticCurve(field, [model[f"a{i}"] for i in (1, 2, 3, 4, 6)])
    generator = point_from_raw(model["generator"])
    subgroup_order = model["subgroup_order"]
    assert subgroup_order * generator == curve(0)
    assert generator != curve(0)
    target_encoded = (receipt["public_target"] if public_target
                      else receipt["fixture_target"])
    target = point_from_raw(target_encoded)
    assert subgroup_order * target == curve(0)
    cycle = coordinate_cycle()
    eigenvalue = base["frobenius_eigenvalue_mod_r"]
    assert eigenvalue * generator == curve(generator[0]**2, generator[1]**2)

    certificates = (receipt.get("verified_public_target_relations") or
                    ([receipt["verified_relation"]] if "verified_relation" in receipt
                     else []))
    if "verified_public_target_quotient_table_dlp" in receipt:
        assert receipt["verified_public_target_quotient_table_dlp"] == bool(
            certificates)
        if receipt["native_result"]["exact_hit_queries"]:
            assert certificates, "native exact hit lacks a verified witness"
    verified = []
    for certificate in certificates:
        indices = (certificate["zero_pair_indices"] +
                   certificate["query_pair_indices"])
        assert len(indices) == 4
        pairs = [key_point_and_log(int(index), data, cycle, eigenvalue,
                                   subgroup_order) for index in indices]
        base_points = [point_from_coords(coords) for coords, _ in pairs]
        raw_points = [point_from_raw(encoded) for encoded in certificate[
            "verified_relation_points"]]
        assert sorted(str(point) for point in base_points) == sorted(
            str(point) for point in raw_points)
        for point, (_, logarithm) in zip(base_points, pairs):
            assert logarithm * generator == point
        scalar = int(certificate["recovered_scalar"])
        assert sum(base_points, curve(0)) == target
        assert scalar == sum(log for _, log in pairs) % subgroup_order
        assert scalar * generator == target
        verified.append({"recovered_scalar": str(scalar),
                         "factor_base_indices": indices,
                         "scalar_replay": True,
                         "four_point_sum": True})
    return {
        "kind": "n83_quotient_receipt_independent_sage_replay",
        "curve_id": screen["curve_id"],
        "proposal_id": receipt.get("proposal_id"),
        "candidate_id": receipt.get("candidate_id"),
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": base[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": base[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": base["signed_frobenius_columns"],
        "receipt_kind": receipt["kind"],
        "public_target_input": public_target,
        "verified_relation_count": len(verified),
        "natural_public_target_relation_verified": bool(
            public_target and verified),
        "verified_relations": verified,
        "receipt_sha256": sha(receipt_path),
        "Q1062_screen_sha256": sha(SCREEN),
        "key_and_log_file_sha256": sha(data_path),
        "generated_field_header_sha256": sha(HEADER),
        "sage_runtime_info_sha256": sha(runtime_path),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = verify(args.receipt, args.runtime_info)
    if args.out:
        assert not args.out.exists(), "refusing to overwrite verification receipt"
        args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
