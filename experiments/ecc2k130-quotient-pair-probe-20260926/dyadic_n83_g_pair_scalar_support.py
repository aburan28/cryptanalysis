#!/usr/bin/env python3
"""Count the exact n83 L1000 G-pair support through scalar orbit invariants.

Every G-base point has a known coefficient in the order-r subgroup.  Since
the signed-Frobenius scalar action has order 166, s -> s^166 (mod r) is a
complete quotient invariant for nonzero pair sums.  This counts support;
it does not construct an elliptic-curve witness index for unknown queries.
"""

import hashlib
import json
import platform
import resource
import time
from pathlib import Path

from curves import isPrimeBig
from perf_probe import sha

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1026"
WINDOW = 1000
ORBIT_SIZE = 166


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


def coefficients_by_window(order, eigenvalue, window):
    powers = [pow(eigenvalue, j, order) for j in range(83)]
    twos = [pow(2, k, order) for k in range(window)]
    buckets = [[(sign * two * power) % order
                for power in powers for sign in (1, -1)]
               for two in twos]
    return twos, buckets


def quotient_keys(order, twos, buckets, progress=False):
    """Enumerate unordered pair orbits with the smaller k as first term."""
    keys = set()
    generators = 0
    checkpoints = []
    started = time.perf_counter()
    for k, first in enumerate(twos):
        for other_bucket in buckets[k:]:
            for second in other_bucket:
                keys.add(pow((first + second) % order, ORBIT_SIZE, order))
                generators += 1
        if progress and ((k + 1) % 100 == 0 or k + 1 == len(twos)):
            checkpoint = {"completed_first_windows": k + 1,
                          "pair_generators": generators,
                          "quotient_keys": len(keys),
                          "elapsed_seconds": time.perf_counter() - started,
                          "peak_rss_bytes": peak_rss_bytes()}
            checkpoints.append(checkpoint)
            print(json.dumps(checkpoint), flush=True)
    return keys, generators, time.perf_counter() - started, checkpoints


def main():
    geometry_path = HERE / "runs" / "n83_dyadic_target_seed_geometry.json"
    geometry = json.loads(geometry_path.read_text())
    stage_path = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    stage = json.loads(stage_path.read_text())
    assert geometry["curve_id"] == stage["curve_id"]
    order = int(geometry["subgroup_order"])
    eigenvalue = int(geometry["frobenius_eigenvalue_mod_r"])
    assert isPrimeBig(order)
    assert pow(eigenvalue, 83, order) == 1
    assert all(pow(eigenvalue, j, order) != 1 for j in range(1, 83))
    assert (order - 1) % ORBIT_SIZE == 0
    assert all(pow(eigenvalue, j, order) != order - 1 for j in range(83))

    small_twos, small_buckets = coefficients_by_window(order, eigenvalue, 32)
    small_keys, small_generators, small_seconds, _ = quotient_keys(
        order, small_twos, small_buckets)
    assert len(small_keys) == stage["index_build"]["quotient_keys"] == 80868
    assert 1 + (len(small_keys) - 1) * ORBIT_SIZE == stage[
        "exact_two_G_pair_sum_support"]
    assert small_generators == 83 * 32 * 33
    del small_keys, small_buckets, small_twos

    twos, buckets = coefficients_by_window(order, eigenvalue, WINDOW)
    assert len({value for bucket in buckets for value in bucket}) == 83 * 2 * WINDOW
    keys, generators, seconds, checkpoints = quotient_keys(
        order, twos, buckets, progress=True)
    assert generators == 83 * WINDOW * (WINDOW + 1)
    assert 0 in keys
    exact_support = 1 + (len(keys) - 1) * ORBIT_SIZE
    point_count = 2 * 83 * WINDOW
    pair_count_cap = point_count * (point_count + 1) // 2
    assert exact_support <= pair_count_cap
    workload = {
        "curve_id": geometry["curve_id"],
        "target": geometry["target"],
        "seed_policy": "public G and public Q as exact dyadic factor-base seeds",
        "doubling_window": WINDOW,
        "stage": "complete G-pair scalar-orbit support count",
        "quotient": "signed Frobenius of order 166",
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n83_target_seed_L1000_exact_G_pair_scalar_support",
        "scope": "exact support count in the known-scalar G side; no point-witness index, natural relation, or DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": geometry["curve_id"],
        "curve_identity_record": geometry["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "subgroup_order": str(order),
        "frobenius_eigenvalue_mod_r": str(eigenvalue),
        "factor_base": geometry["factor_base"],
        "G_side_actual_points": point_count,
        "L32_independent_curve_point_key_control": {
            "quotient_keys": stage["index_build"]["quotient_keys"],
            "scalar_pair_generators": small_generators,
            "scalar_count_seconds": small_seconds,
        },
        "L1000_unordered_pair_orbit_generators": generators,
        "L1000_prefix_checkpoints": checkpoints,
        "L1000_exact_quotient_keys": len(keys),
        "L1000_exact_distinct_G_pair_sums": exact_support,
        "L1000_unordered_point_pair_count_cap": pair_count_cap,
        "L1000_support_to_pair_count_ratio": exact_support / pair_count_cap,
        "L1000_scalar_count_seconds": seconds,
        "peak_process_rss_bytes": peak_rss_bytes(),
        "algorithm": "enumerate 2^k + sign*2^ell*lambda^j for k<=ell; hash its 166th power modulo r",
        "proof_boundary": "In the prime-order subgroup, the kernel of s->s^166 is precisely the order-166 signed-Frobenius scalar group. Every unordered point pair orbit can be shifted and signed to a first term 2^k with k<=ell.",
        "not_solver_index": True,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "geometry_receipt_sha256": sha(geometry_path),
        "stage_control_receipt_sha256": sha(stage_path),
    }
    out = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"exact_keys": len(keys),
                      "exact_support": exact_support,
                      "ratio": exact_support / pair_count_cap,
                      "seconds": seconds,
                      "peak_rss_bytes": report["peak_process_rss_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
