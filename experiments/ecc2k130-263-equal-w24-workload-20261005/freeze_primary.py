#!/usr/bin/env python3
"""Derive the sole primary one-target workload from preselected corpus index 0."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def save_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    workload_path = HERE / "primary_workload.json"
    derivation_path = HERE / "primary_derivation.json"
    assert not workload_path.exists() and not derivation_path.exists()
    corpus = json.loads((HERE / "workload.json").read_text())
    fixture = json.loads((HERE / "target_fixtures.json").read_text())
    verified = json.loads((HERE / "verification.json").read_text())
    config = json.loads((HERE / "CONFIG.json").read_text())
    route = json.loads(ROUTE.read_text())
    assert verified["status"] == "PASS_EXACT_BASE_ROUTE_AND_PUBLIC_FIXTURES"
    assert verified["public_workload_sha256"] == sha(HERE / "workload.json")
    assert verified["fixture_sha256"] == sha(HERE / "target_fixtures.json")
    assert verified["workload_id"] == corpus["workload_id"]
    assert corpus["target_count"] == config["target_count"] == 512
    assert corpus["primary_target_index"] == 0
    first = corpus["targets"][0]
    assert first["index"] == 0
    scalar = int.from_bytes(hashlib.sha256(
        config["target_scalar_domain"].encode() + b":" +
        first["counter"].to_bytes(8, "big")).digest()[:17], "big") & ((1 << 130) - 1)
    assert scalar == fixture["accepted_scalars"][0]
    source = route["curve_nodes"]["source"]
    assert 0 < scalar < source["subgroup_order"]
    primary = {
        "schema": "ecc2k130-263-equal-w24-primary-one-target-v1",
        "source_curve_id": source["curve_id"],
        "descendant_curve_id": route["curve_nodes"]["target"]["curve_id"],
        "route_id": route["route_id"],
        "subgroup_order": source["subgroup_order"],
        "generator_G": source["generator_G"],
        "point_encoding": corpus["point_encoding"],
        "input_law": corpus["input_law"],
        "target_scalar_domain": corpus["target_scalar_domain"],
        "target_count": 1,
        "online_start_condition": "reusable_precomputation_ready; first_target_dependent_operation",
        "targets": [first],
    }
    identity = hashlib.sha256(canonical(primary)).hexdigest()
    primary["workload_id"] = identity[:12]
    derivation = {
        "schema": "ecc2k130-263-equal-w24-primary-derivation-v1",
        "status": "DERIVED_FROM_PREDECLARED_INDEX_ZERO",
        "primary_workload_id": primary["workload_id"],
        "primary_identity_sha256": identity,
        "control_corpus_id": corpus["workload_id"],
        "control_corpus_sha256": sha(HERE / "workload.json"),
        "corpus_verification_sha256": sha(HERE / "verification.json"),
        "route_manifest_sha256": sha(ROUTE),
        "producer_sha256": sha(Path(__file__)),
        "fixture_scalar_disclosed_only_in": "target_fixtures.json",
        "candidate_id": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    save_new(workload_path, primary)
    save_new(derivation_path, derivation)
    print(json.dumps({"primary_workload_id": primary["workload_id"],
                      "target_count": 1, "control_corpus_id": corpus["workload_id"]}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
