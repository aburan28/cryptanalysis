#!/usr/bin/env python3
"""Independently replay both field bridges with a polynomial-bit kernel.

All basis-pair products are checked, which proves multiplicativity for all
field elements by F2 bilinearity. The exact factor-base representatives are
then checked on the transported polynomial curve.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

from derive_onb_poly_bridge import xor_images
from run_probe import HERE, ROOT, curves, field, sha

PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from orbit_key import OrbitKey  # noqa: E402


def polynomial_mul(left, right, n, modulus):
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left >> n:
            left ^= modulus
    return result


def replay(n):
    bridge_path = HERE / "field_bridges" / f"n{n}_onb_poly.json"
    bridge = json.loads(bridge_path.read_text())
    assert bridge["field_degree"] == n
    assert bridge["status"] == "PASS"
    assert bridge["changes_curve_identity"] is False
    assert bridge["isogeny"] == "none"
    assert bridge["source_sha256"] == sha(
        HERE / "derive_onb_poly_bridge.py")
    assert bridge["field_source_sha256"] == sha(Path(field.__file__))
    runtime_path = HERE / "bridge_sage_runtime_info.json"
    assert bridge["runtime_info_sha256"] == sha(runtime_path)
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    forward = bridge["onb_to_poly_basis_images"]
    inverse = bridge["poly_to_onb_basis_images"]
    assert len(forward) == len(inverse) == n
    assert all(xor_images(forward[i], inverse) == 1 << i
               for i in range(n))
    assert all(xor_images(inverse[i], forward) == 1 << i
               for i in range(n))
    modulus = (1 << n) | sum(1 << exponent for exponent in bridge[
        "target_implementation_basis"]["low_terms"])
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    assert xor_images(onb.toCoords(onb.one()), forward) == 1
    products_checked = 0
    for i in range(n):
        left = onb.fromCoords(1 << i)
        for j in range(n):
            source = onb.toCoords(onb.mul(left, onb.fromCoords(1 << j)))
            transported = xor_images(source, forward)
            assert transported == polynomial_mul(
                forward[i], forward[j], n, modulus)
            products_checked += 1
    assert products_checked == n * n

    def polynomial_curve(point):
        x = xor_images(onb.toCoords(point[0]), forward)
        y = xor_images(onb.toCoords(point[1]), forward)
        mul = lambda a, b: polynomial_mul(a, b, n, modulus)
        assert (mul(y, y) ^ mul(x, y)) == (mul(mul(x, x), x) ^ 1)
        return x, y

    baseline_path = HERE / "runs" / f"n{n}_ordinary_frozen.json"
    baseline = json.loads(baseline_path.read_text())
    target = tuple(map(int, baseline["public_subgroup_target"]))
    assert bridge["curve_id"] == baseline["curve_id"]
    assert bridge["baseline_receipt_sha256"] == sha(baseline_path)
    assert list(polynomial_curve(target)) == bridge[
        "mapped_public_target_poly"]

    if n == 53:
        archive_path = HERE / "bases/n53_weight3_orbits.json.gz"
        bridge_source_archive_path = archive_path
        with gzip.open(archive_path, "rt") as source:
            archive = json.load(source)
        packed = base64.b64decode(archive["factor_base"][
            "packed_canonical_x_keys_base64"], validate=True)
        assert hashlib.sha256(packed).hexdigest() == archive[
            "factor_base"]["enumerated_set_sha256"]
        keys = [int.from_bytes(packed[i:i + 7], "little")
                for i in range(0, len(packed), 7)]
        assert len(keys) == 227
        for key in keys:
            point = curve.pointFromX(onb.fromCoords(key))
            assert point is not None
            polynomial_curve(point)
        representatives = len(keys)
    else:
        archive_path = HERE / "bases/n83_weight5_full_orbits.json"
        bridge_source_archive_path = HERE / "bases/n83_weight4_orbits.json.gz"
        archive = json.loads(archive_path.read_text())
        key_path = HERE / "bases/n83_weight5_full_point_orbits.bin"
        packed = key_path.read_bytes()
        assert hashlib.sha256(packed).hexdigest() == archive[
            "factor_base"]["enumerated_set_sha256"]
        assert len(packed) == 21 * 186612
        orbit = OrbitKey(onb)
        for offset in range(0, len(packed), 21):
            key = int.from_bytes(packed[offset:offset + 21], "little")
            point = orbit.point_from_key(key)
            assert point is not None
            polynomial_curve(point)
        representatives = len(packed) // 21
    assert archive["curve"]["curve_id"] == bridge["curve_id"]
    assert bridge["base_archive_sha256"] == sha(bridge_source_archive_path)
    return {
        "kind": "independent_polynomial_kernel_bridge_replay",
        "status": "PASS",
        "field_degree": n,
        "curve_id": bridge["curve_id"],
        "isogeny": "none",
        "all_basis_products_checked": products_checked,
        "factor_base_representatives_checked_on_polynomial_curve": representatives,
        "ordinary_target_checked_on_polynomial_curve": True,
        "bridge_sha256": sha(bridge_path),
        "base_archive_sha256": sha(archive_path),
        "bridge_source_base_archive_sha256": sha(bridge_source_archive_path),
        "baseline_receipt_sha256": sha(baseline_path),
        "runtime_info_sha256": sha(runtime_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "orbit_source_sha256": sha(PAIR / "orbit_key.py"),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = HERE / "runs" / f"n{args.n}_onb_poly_bridge_replay.json"
    report = replay(args.n)
    content = json.dumps(report, indent=2) + "\n"
    if args.check:
        assert path.read_text() == content
    else:
        assert not path.exists()
        path.write_text(content)
    print(json.dumps({"n": args.n, "status": report["status"],
                      "basis_products": report["all_basis_products_checked"],
                      "base_representatives": report[
                          "factor_base_representatives_checked_on_polynomial_curve"]}))


if __name__ == "__main__":
    main()
