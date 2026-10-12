#!/usr/bin/env python3
"""Replay the archived N83 relation using only the reduced prefix base."""

import hashlib
import json
import sys
import tarfile
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from verify_n83_quotient_receipt_sage import (  # noqa: E402
    coordinate_cycle, gamma_to_polynomial_bits, key_point_and_log,
    raw_to_coords,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "independent_sage_replay.json"
    assert not output.exists(), "replay evidence already exists"
    protocol = json.loads((HERE / "protocol.json").read_text())
    prefix_receipt = json.loads((HERE / "prefix.json").read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    prefix_path = HERE / "witness_prefix_keys_and_logs.bin"
    assert sha(prefix_path) == prefix_receipt["prefix_file_sha256"]
    data = prefix_path.read_bytes()
    assert len(data) == prefix_receipt["K"] * 32
    archive_path = (HERE / protocol["archive"]).resolve()
    assert sha(archive_path) == protocol["archive_sha256"]
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.extractfile(protocol["archive_member"])
        assert member is not None
        witness_bytes = member.read()
    assert hashlib.sha256(witness_bytes).hexdigest() == prefix_receipt[
        "witness_receipt_sha256"]
    witness = json.loads(witness_bytes)
    relation = witness["verified_public_target_relations"][0]
    indices = relation["zero_pair_indices"] + relation["query_pair_indices"]
    assert indices == prefix_receipt["witness_indices"]
    assert all(index < len(data) // 32 * 166 for index in indices)
    assert max(indices) >= (prefix_receipt["K"] - 1) * 166

    binary = GF(2)
    ring = PolynomialRing(binary, "t")
    t = ring.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="z", modulus=modulus)
    gamma_bits = gamma_to_polynomial_bits()
    assert len(gamma_bits) == 83

    def element(coords):
        bits = 0
        while coords:
            low = coords & -coords
            bits ^= gamma_bits[low.bit_length() - 1]
            coords ^= low
        return field(ring([(bits >> i) & 1 for i in range(83)]))

    def point_from_coords(coords):
        return curve(element(coords[0]), element(coords[1]))

    def point_from_raw(encoded):
        return point_from_coords([raw_to_coords(int(v)) for v in encoded])

    model = witness["curve_identity_record"]["curve"]
    curve = EllipticCurve(field, [model[f"a{i}"] for i in (1, 2, 3, 4, 6)])
    order = model["subgroup_order"]
    generator = point_from_raw(model["generator"])
    target = point_from_raw(witness["public_target"])
    assert order * generator == curve(0)
    assert order * target == curve(0)
    eigenvalue = witness["factor_base"]["frobenius_eigenvalue_mod_r"]
    assert eigenvalue * generator == curve(generator[0]**2, generator[1]**2)
    pairs = [key_point_and_log(index, data, coordinate_cycle(), eigenvalue, order)
             for index in indices]
    points = [point_from_coords(coords) for coords, _ in pairs]
    assert all(log * generator == point for point, (_, log) in zip(points, pairs))
    shift = int(relation["frobenius_shift"])
    sign = int(relation["sign"])
    relation_points = [curve(points[i][0] ** (1 << shift),
                             points[i][1] ** (1 << shift)) for i in (0, 1)]
    relation_logs = [sign * pow(eigenvalue, shift, order) * pairs[i][1] % order
                     for i in (0, 1)]
    if sign < 0:
        relation_points = [-point for point in relation_points]
    relation_points += points[2:]
    relation_logs += [pairs[i][1] for i in (2, 3)]
    archived_points = [point_from_raw(value) for value in relation[
        "verified_relation_points"]]
    assert sorted(str(p) for p in relation_points) == sorted(
        str(p) for p in archived_points)
    assert sum(relation_points, curve(0)) == target
    assert all(log * generator == point for log, point in zip(
        relation_logs, relation_points))
    scalar = sum(relation_logs) % order
    assert scalar == int(relation["recovered_scalar"])
    assert scalar * generator == target
    result = {
        "status": "PASS",
        "curve_id": witness["curve_id"],
        "K": prefix_receipt["K"],
        "B": prefix_receipt["actual_usable_points_B_before_folding"],
        "witness_indices": indices,
        "public_target_scalar_replayed": str(scalar),
        "four_point_sum": True,
        "all_four_logs_replayed": True,
        "prefix_file_sha256": sha(prefix_path),
        "prefix_receipt_sha256": sha(HERE / "prefix.json"),
        "archive_sha256": sha(archive_path),
        "runtime_info_sha256": sha(runtime_path),
        "verifier_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "K": result["K"],
                      "scalar": str(scalar)}))


if __name__ == "__main__":
    main()
