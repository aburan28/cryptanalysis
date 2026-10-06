#!/usr/bin/env python3
"""Audit the map-cost receipt against frozen inputs and prior independent replay."""

import argparse
import hashlib
import json
import statistics
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUT = ROOT / "experiments/ecc2k130-263-equal-w24-workload-20261005"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    route = json.loads(ROUTE.read_text())
    workload = json.loads((INPUT / "workload.json").read_text())
    primary = json.loads((INPUT / "primary_workload.json").read_text())
    controls = json.loads((INPUT / "point_controls.json").read_text())
    parent = json.loads((INPUT / "verification.json").read_text())
    runtime = json.loads((HERE / "runtime-info.json").read_text())
    assert runtime["status"] == "verified"
    assert parent["status"] == "PASS_EXACT_BASE_ROUTE_AND_PUBLIC_FIXTURES"
    assert parent["verified"] is True and parent["fixture_count"] == 512
    assert parent["source_control_count"] == parent["native_control_count"] == 64
    assert parent["workload_id"] == workload["workload_id"]
    assert parent["public_workload_sha256"] == digest(INPUT / "workload.json")
    assert parent["control_sha256"] == digest(INPUT / "point_controls.json")
    assert primary["target_count"] == 1
    assert primary["targets"][0] == workload["targets"][0]
    assert workload["route_manifest_sha256"] == digest(ROUTE)
    assert controls["route_manifest_sha256"] == digest(ROUTE)
    assert result["schema"] == "ecc2k130-263-transport-cost-v1"
    assert result["status"] == "PASS_256_FROZEN_MAP_EVALUATIONS"
    assert result["candidate_id"] is None
    assert result["primary_workload_id"] == primary["workload_id"]
    assert result["control_corpus_id"] == workload["workload_id"]
    assert result["primary_target_index"] == 0
    assert result["source_curve_id"] == route["curve_nodes"]["source"]["curve_id"]
    assert result["descendant_curve_id"] == route["curve_nodes"]["target"]["curve_id"]
    assert result["route_id"] == route["route_id"]
    assert result["checks"] == {
        "source_target_to_descendant": 64,
        "descendant_target_to_source": 64,
        "source_base_to_transport": 64,
        "native_base_to_pullback": 64,
        "generator_and_dual_composition": True,
    }
    expected_hashes = {
        "route": digest(ROUTE),
        "workload": digest(INPUT / "workload.json"),
        "primary_workload": digest(INPUT / "primary_workload.json"),
        "base_controls": digest(INPUT / "point_controls.json"),
        "runtime_info": digest(HERE / "runtime-info.json"),
        "protocol": digest(HERE / "PROTOCOL.md"),
        "source": digest(HERE / "measure.py"),
    }
    assert result["sha256"] == expected_hashes
    assert isinstance(result["field_setup_ns_excluded"], int)
    assert isinstance(result["map_setup_ns_excluded"], int)
    assert result["field_setup_ns_excluded"] > 0
    assert result["map_setup_ns_excluded"] > 0
    for name in ("target_forward", "target_inverse", "base_forward", "base_inverse"):
        samples = result[name + "_ns"]
        assert len(samples) == 64
        assert all(isinstance(value, int) and value > 0 for value in samples)
        assert result["diagnostic_summaries"][name] == {
            "count": 64, "min_ns": min(samples),
            "median_ns": statistics.median(samples), "max_ns": max(samples),
        }
    assert result["primary_forward_ns"] == result["target_forward_ns"][0]
    assert result["primary_inverse_ns"] == result["target_inverse_ns"][0]
    assert len(workload["targets"]) >= 64
    assert len(controls["source"]) == len(controls["descendant_native"]) == 64
    for name in ("natural_pdp_yield", "verified_relation_rank",
                 "verified_logarithm", "ic_online_ms", "rho_online_ms", "speedup"):
        assert result[name] is None
    receipt = {
        "schema": "ecc2k130-263-transport-cost-audit-v1",
        "status": "PASS_FROZEN_INPUTS_AND_COST_LEDGER",
        "independent_parent_map_replay": True,
        "independent_timing_replay": False,
        "replayed_target_count": 64,
        "replayed_base_control_count": 128,
        "map_evaluation_count": 256,
        "primary_workload_id": primary["workload_id"],
        "control_corpus_id": workload["workload_id"],
        "parent_verification_sha256": digest(INPUT / "verification.json"),
        "result_sha256": digest(result_path),
        "verifier_sha256": digest(Path(__file__)),
    }
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
