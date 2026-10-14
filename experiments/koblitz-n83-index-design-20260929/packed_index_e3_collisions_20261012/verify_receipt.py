#!/usr/bin/env python3
"""Check immutable source, input, and result digests for the E-3 audit."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUTS = ROOT / "experiments/koblitz-n83-index-design-20260929/adaptive_all_orientations_20261004/inputs"


def sha(path):
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    record = json.loads((HERE / "protocol.json").read_text())
    inputs = {
        "stage_manifest": HERE / "stage_manifest.json",
        "bridge": INPUTS / "n83_onb_poly_bridge.json",
        "representatives": INPUTS / "n83_x_representatives.bin",
        "rust_source": HERE / "native_packed_index.rs",
        "cargo_manifest": HERE / "Cargo.toml",
        "cargo_lock": HERE / "Cargo.lock",
    }
    evidence = {
        "raw_collision_audit": HERE / "collision_audit_29900000.json",
        "independent_sage_replay": HERE / "independent_sage_replay.json",
        "sage_runtime_info": HERE / "sage_runtime_info.json",
        "lean_source": HERE / "CollisionCancellation.lean",
        "lean_build": HERE / "lean-build.txt",
    }
    for name, path in inputs.items():
        assert sha(path) == record["input_sha256"][name], name
    for name, path in evidence.items():
        assert sha(path) == record["evidence_sha256"][name], name
    if args.binary:
        assert sha(args.binary) == record["input_sha256"]["native_binary"]

    raw = json.loads(evidence["raw_collision_audit"].read_text())
    sage = json.loads(evidence["independent_sage_replay"].read_text())
    result = record["result"]
    assert raw["status"] == "collision_audit_complete"
    assert sage["status"] == "PASS"
    assert sage["verifier_sha256"] == sha(HERE / "verify_sage.py")
    assert sage["raw_sha256"] == sha(evidence["raw_collision_audit"])
    assert sage["native_source_sha256"] == sha(inputs["rust_source"])
    assert raw["native_source_sha256"] == sha(inputs["rust_source"])
    assert raw["cargo_manifest_sha256"] == sha(inputs["cargo_manifest"])
    assert raw["curve_id"] == sage["curve_id"] == record["curve_id"]
    assert raw["workload_id"] == sage["workload_id"] == record["workload_id"]
    assert raw["index_pair_states_examined"] == sage["indexed_states"] == record["state_cap"]
    assert raw["root_table_records"] == result["root_records"]
    assert raw["index_distinct_root_keys"] == result["distinct_root_keys"]
    assert raw["duplicate_records"] == result["duplicate_records"]
    assert sage["collision_groups"] == result["duplicate_records"]
    assert sage["categories"]["swapped_pair"] == result["swapped_pair"]
    assert sage["categories"]["same_state_two_selectors"] == result["same_state_two_selectors"]
    assert sage["categories"]["distinct_pair"] == result["distinct_pair"]
    assert sage["nontrivial_rank_increment"] == result["nontrivial_rank_increment"] == 0
    assert raw["peak_rss_bytes"] == result["peak_rss_bytes"]
    assert raw["index_build_and_sort_ns"] == result["index_build_and_sort_ns"]
    assert "error:" not in evidence["lean_build"].read_text()
    print(json.dumps({"status": "PASS", "collision_groups": sage["collision_groups"],
                      "nontrivial_rank_increment": sage["nontrivial_rank_increment"],
                      "binary_checked": bool(args.binary)}, sort_keys=True))


if __name__ == "__main__":
    main()
