#!/usr/bin/env python3
"""Exhaustively compare quotient pair descriptors with all n23 base pairs."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from batch_quotient import x_orbit_key
from bench_n83_full_base import CompactOrbitBase
from orbit_key import OrbitKey
from pair_schedule import cross_orbit_pair, within_orbit_pair
from run_n23 import build_base, frozen, point_digest, sha


def main():
    receipt = json.loads((HERE / "runs" / "n23_one_target.json").read_text())
    identity = receipt["curve_identity_record"]
    curve_id = "EC1N23Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == receipt["curve_id"]
    onb = field.Onb(23)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    points, _ = build_base(curve, onb, identity["curve"]["subgroup_order"])
    assert len(points) == 322
    assert point_digest(points) == receipt["factor_base"]["enumerated_set_sha256"]
    keys = sorted({orbit.canonical(point)[0] for point in points})
    assert len(keys) == 7
    base = CompactOrbitBase(orbit, keys)
    assert set(base[index] for index in range(len(base))) == set(points)
    K, L = len(keys), 46
    cross_domain = K * (K - 1) // 2 * L
    within_domain = K * 23
    scheduled = set()
    for rank in range(cross_domain):
        i, j, shift = cross_orbit_pair(rank, K, L)
        scheduled.add(x_orbit_key(
            orbit, curve.add(base[i * L], base[j * L + shift])))
    for rank in range(within_domain):
        i, shift = within_orbit_pair(rank, K, 23)
        scheduled.add(x_orbit_key(
            orbit, curve.add(base[i * L], base[i * L + shift])))
    exhaustive = set()
    for j in range(len(base)):
        for i in range(j + 1):
            pair = curve.add(base[i], base[j])
            if pair is not None:
                exhaustive.add(x_orbit_key(orbit, pair))
    assert -1 not in scheduled
    assert scheduled == exhaustive
    report = {
        "kind": "n23_exhaustive_quotient_pair_schedule_coverage_verification",
        "curve_id": curve_id, "actual_B": len(base),
        "isogeny": "none", "candidate_id": None, "run_id": None,
        "signed_frobenius_columns": K,
        "cross_orbit_descriptors": cross_domain,
        "within_orbit_nonidentity_descriptors": within_domain,
        "unordered_base_pairs_checked": len(base) * (len(base) + 1) // 2,
        "distinct_nonidentity_x_quotient_keys": len(exhaustive),
        "descriptor_coverage_verified": True,
        "base_enumerated_set_sha256":
            receipt["factor_base"]["enumerated_set_sha256"],
        "base_receipt_sha256": sha(HERE / "runs" / "n23_one_target.json"),
        "source_sha256": sha(Path(__file__)),
        "schedule_source_sha256": sha(HERE / "pair_schedule.py"),
        "xkey_source_sha256": sha(HERE / "batch_quotient.py"),
        "local_dependency_sha256": {
            name: sha(HERE / name) for name in (
                "bench_n83_full_base.py", "orbit_key.py", "run_n23.py")
        },
    }
    (HERE / "runs" / "n23_pair_schedule_verified.json").write_text(
        json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
