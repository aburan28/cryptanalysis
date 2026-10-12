#!/usr/bin/env python3
"""Full N53 control of Q1484's compressed status-archive construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from enumerate_n131 import (HERE, Q1481, OrbitKey, canonical_rotation,
                            curves, field, onb_x_from_cycle_mask,
                            representatives, sha,
                            status_code)
from verify_archive import code_at


def replay() -> dict:
    n, d = 53, 14
    parent_path = Q1481 / "n53_d14_base.json"
    packed_path = Q1481 / "n53_d14_projected_keys.bin"
    parent = json.loads(parent_path.read_text())
    assert parent["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert parent["nominal_window_dimension_d"] == d
    cofactor = parent["cofactor"]
    assert cofactor == 428
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    flags = bytearray((1 << (d - 1)) // 4)
    direct_keys: set[int] = set()
    direct_rational = direct_identity = direct_duplicates = 0
    for index, (mask, _) in enumerate(representatives(d)):
        x = onb_x_from_cycle_mask(mask, onb, orbit)
        point = curve.pointFromX(x)
        if point is None:
            code = 0
        else:
            direct_rational += 1
            image = curve.mul(point, cofactor)
            if image is None:
                code = 1
                direct_identity += 1
            else:
                code = 2
                key = canonical_rotation(orbit.cycle_bits(image[0]), n)
                if key in direct_keys:
                    direct_duplicates += 1
                direct_keys.add(key)
        status_code(flags, index, code)
    assert direct_identity == direct_duplicates == 0
    assert len(direct_keys) == parent["signed_frobenius_columns_K"] == 4060
    assert 2 * n * len(direct_keys) == parent[
        "actual_usable_points_B_before_folding"] == 430360
    packed = b"".join(key.to_bytes(7, "little")
                      for key in sorted(direct_keys))
    assert packed == packed_path.read_bytes()
    assert hashlib.sha256(packed).hexdigest() == parent[
        "enumerated_set_sha256"]

    projected_keys: set[int] = set()
    reconstructed_rational = reconstructed_identity = 0
    for index, (mask, _) in enumerate(representatives(d)):
        x = onb_x_from_cycle_mask(mask, onb, orbit)
        point = curve.pointFromX(x)
        code = code_at(flags, index)
        assert code in (0, 1, 2)
        assert (point is not None) == (code != 0)
        if point is not None:
            reconstructed_rational += 1
        if code == 1:
            assert curve.mul(point, cofactor) is None
            reconstructed_identity += 1
        elif code == 2:
            projected = curve.mul(point, cofactor)
            assert projected is not None
            projected_keys.add(canonical_rotation(
                orbit.cycle_bits(projected[0]), n))
        else:
            assert point is None
    assert reconstructed_rational == direct_rational
    assert reconstructed_identity == direct_identity
    assert projected_keys == direct_keys
    return {
        "kind": "q1484_archive_encoding_full_n53_control",
        "proposal_id": "Q1484",
        "parent_base_proposal_id": "Q1481",
        "curve_id": parent["curve_id"],
        "cofactor": cofactor,
        "raw_x_orbits_checked": 1 << (d - 1),
        "direct_rational_orbits": direct_rational,
        "direct_identity_orbits": direct_identity,
        "direct_duplicate_projected_orbits": direct_duplicates,
        "reconstructed_folded_K": len(projected_keys),
        "reconstructed_actual_B": 2 * n * len(projected_keys),
        "status_bitmap_sha256": hashlib.sha256(flags).hexdigest(),
        "projected_set_sha256": hashlib.sha256(packed).hexdigest(),
        "parent_receipt_sha256": sha(parent_path),
        "parent_key_archive_sha256": sha(packed_path),
        "source_sha256": sha(Path(__file__)),
        "producer_source_sha256": sha(HERE / "enumerate_n131.py"),
        "status": "PASS",
        "complete_n131_log2_work": None,
    }


def main() -> None:
    result = replay()
    path = HERE / "n53_encoding_replay.json"
    if path.exists():
        assert json.loads(path.read_text()) == result
        print("Q1484 full N53 archive encoding replay PASS (archived)")
    else:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Q1484 full N53 archive encoding replay PASS")


if __name__ == "__main__":
    main()
