#!/usr/bin/env python3
"""Run the archived n53 quotient pair table on the frozen S3 target/base."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from chain_s3 import square_destinations
from enumerate_weight_base import orbit
from run_probe import HERE, ROOT, sha

PRIOR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PRIOR))

from orbit_key import OrbitKey  # noqa: E402
from probe_n53_relation import base_and_columns  # noqa: E402
from probe_n53_table import (QUERY_SAMPLES, QUERY_SEED, TABLE_SAMPLES,  # noqa: E402
                             TABLE_SEED, search)
from run_probe import curves, field  # noqa: E402


def main():
    stage_path = HERE / "runs/n53_ordinary_frozen.json"
    archive_path = HERE / "bases/n53_weight3_orbits.json.gz"
    output = HERE / "runs/n53_ordinary_matched_pair_table.json"
    assert not output.exists()
    stage = json.loads(stage_path.read_text())
    import gzip
    with gzip.open(archive_path, "rt") as stream:
        archive = json.load(stream)
    assert sha(Path(field.__file__)) == archive["enumeration"][
        "field_source_sha256"]
    assert sha(Path(curves.__file__)) == archive["enumeration"][
        "curve_source_sha256"]
    assert stage["curve_id"] == archive["curve"]["curve_id"]
    assert stage["factor_base_archive_sha256"] == sha(archive_path)
    assert stage["workload_kind"] == "ordinary"
    assert stage["protocol_sha256"] == sha(HERE / "protocol.json")
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    order = int(archive["curve"]["subgroup_order"])
    cofactor = int(archive["curve"]["cofactor"])
    target = tuple(int(v) for v in stage["public_subgroup_target"])
    assert curve.onCurve(target) and curve.mul(target, order) is None

    setup_started = time.perf_counter_ns()
    base, representatives, rational_x = base_and_columns(
        curve, onb, order, cofactor)
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(base) == archive["factor_base"][
        "actual_usable_points_B_before_folding"]
    assert len(representatives) == archive["factor_base"][
        "signed_frobenius_columns"]
    destinations = square_destinations(onb)
    keys = {}
    for representative in representatives:
        projected_x = onb.toCoords(representative[0])
        xs = orbit(projected_x, destinations)
        canonical = min(xs)
        assert canonical not in keys
        keys[canonical] = len(xs)
    packed = b"".join(key.to_bytes(7, "little") for key in sorted(keys))
    digest = hashlib.sha256(packed).hexdigest()
    assert digest == archive["factor_base"]["enumerated_set_sha256"]
    assert 2 * sum(keys.values()) == len(base)
    assert rational_x == archive["factor_base"]["geometric_rational_x_count"]

    result = search(curve, base, target, OrbitKey(onb))
    relation = result["relation"]
    if relation is not None:
        base_set = set(base)
        points = [tuple(row) for row in relation["points"]]
        assert len(points) == 4 and all(point in base_set for point in points)
        total = None
        for point in points:
            total = curve.add(total, point)
        assert total == target
    report = {
        "kind": "matched_n53_weight3_pair_table_stage_probe",
        "proposal_id": "Q1301",
        "candidate_id": None,
        "run_id": None,
        "workload_id": stage["workload_id"],
        "curve_id": stage["curve_id"],
        "isogeny": "none",
        "status": result["status"],
        "target": list(stage["public_subgroup_target"]),
        "matched_s3_stage_receipt_sha256": sha(stage_path),
        "protocol_sha256": stage["protocol_sha256"],
        "factor_base_archive_sha256": sha(archive_path),
        "factor_base_enumerated_set_sha256": digest,
        "factor_base_actual_B": len(base),
        "factor_base_folded_columns": len(representatives),
        "base_setup_wall_ns": setup_ns,
        "table_samples": TABLE_SAMPLES,
        "query_sample_cap": QUERY_SAMPLES,
        "table_seed": TABLE_SEED,
        "query_seed": QUERY_SEED,
        "ordinary_query": result,
        "verified_relation_count": int(relation is not None),
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "peak_parent_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_parent_rss_units": "bytes on Darwin, KiB on Linux",
        "source_sha256": sha(Path(__file__)),
        "prior_search_source_sha256": sha(PRIOR / "probe_n53_table.py"),
        "prior_base_source_sha256": sha(PRIOR / "probe_n53_relation.py"),
        "orbit_key_source_sha256": sha(PRIOR / "orbit_key.py"),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "run_probe_source_sha256": sha(HERE / "run_probe.py"),
        "chain_s3_source_sha256": sha(HERE / "chain_s3.py"),
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "factor_base_digest": digest,
                      "table_samples": TABLE_SAMPLES,
                      "query_samples": result["query_samples"],
                      "table_seconds": result["table_wall_ns"] / 1e9,
                      "query_seconds": result["query_wall_ns"] / 1e9,
                      "verified_relation_count": report["verified_relation_count"]}))


if __name__ == "__main__":
    main()
