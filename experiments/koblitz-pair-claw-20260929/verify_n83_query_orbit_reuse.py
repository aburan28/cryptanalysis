#!/usr/bin/env python3
"""Sample the n=83 pair-orbit target-key identity on the exact known-log base."""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
BASE = HERE / "runs" / "n83_knownlog_orbit_base.json"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs" / "n83_perf_prefix.json"
OUTPUT = HERE / "runs" / "n83_query_orbit_reuse_sample.json"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from bench_n83_knownlog import load_keys_logs
from orbit_key import OrbitKey
from pair_schedule import cross_orbit_pair
from verify_query_orbit_reuse import lift_within


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base_receipt = json.loads(BASE.read_text())
    reference = json.loads(REFERENCE.read_text())
    assert base_receipt["curve_id"] == reference[
        "curve_id"] == "EC1N83Ckb1h876c2921cb64"
    record = base_receipt["factor_base"]
    key_path = HERE / record["key_and_log_file"]
    assert sha(key_path) == record["key_and_log_file_sha256"]
    keys, _ = load_keys_logs(key_path)
    n = 83
    L = 2 * n
    K = len(keys)
    orbit = OrbitKey(field.Onb(n))
    curve = curves.Curve(orbit.onb)
    base = CompactOrbitBase(orbit, keys)
    target = tuple(reference["workload"]["target"])
    assert K == 24097 and len(base) == 4000102
    assert curve.onCurve(target)
    cross_domain = K * (K - 1) // 2 * L
    rng = random.Random(830929)
    checks = 0
    for _ in range(512):
        rank = rng.randrange(cross_domain)
        i, j, relative = cross_orbit_pair(rank, K, L)
        first = i * L
        second = j * L + relative
        z = curve.add(base[first], base[second])
        assert z is not None
        k = rng.randrange(n)
        negative = bool(rng.randrange(2))
        a = i * L + lift_within(0, k, negative, n)
        b = j * L + lift_within(relative, k, negative, n)
        transformed = curve.frob(z, k)
        if negative:
            transformed = curve.neg(transformed)
        assert curve.add(base[a], base[b]) == transformed
        direct = curve.add(target, curve.neg(transformed))
        q_conjugate = curve.frob(target, (-k) % n)
        reused = curve.add(q_conjugate,
                           z if negative else curve.neg(z))
        assert (orbit.canonical(direct)[0] >> n ==
                orbit.canonical(reused)[0] >> n)
        checks += 1
    report = {
        "kind": "n83_signed_frobenius_query_pair_orbit_reuse_sample",
        "scope": "sampled exact-base group and canonical-x identities; no natural target relation",
        "proposal_id": "Q1050", "candidate_id": None,
        "curve_id": base_receipt["curve_id"],
        "curve_identity_record": base_receipt["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": len(base),
        "signed_frobenius_columns": K,
        "factor_base_enumerated_set_sha256": record[
            "enumerated_set_sha256"],
        "public_target": list(target),
        "cross_orbit_pair_representative_domain": cross_domain,
        "sample_seed": 830929,
        "sampled_group_and_canonical_x_identities_checked": checks,
        "all_checks_passed": True,
        "natural_relation_yield": None,
        "complete_solve_work_log2": None,
        "base_receipt_sha256": sha(BASE),
        "reference_sha256": sha(REFERENCE),
        "key_file_sha256": sha(key_path),
        "source_sha256": sha(Path(__file__)),
        "n23_control_source_sha256": sha(HERE /
                                         "verify_query_orbit_reuse.py"),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "cross_orbit_pair_representative_domain": cross_domain,
        "sampled_group_and_canonical_x_identities_checked": checks,
        "all_checks_passed": True,
    }))


if __name__ == "__main__":
    main()
