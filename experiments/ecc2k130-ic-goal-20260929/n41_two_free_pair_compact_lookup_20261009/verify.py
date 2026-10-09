#!/usr/bin/env python3
"""Verify frozen N41 runs, Sage row replay, and N131 transfer arithmetic."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GOAL = HERE.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    first = load("protocol.json")
    second = load("protocol_v2.json")
    matched = load("matched_baseline_protocol.json")
    new = load("public_search_v2.json")
    old = load("matched_baseline.json")
    audit = load("sage_audit.json")
    transfer = load("transfer_gate.json")
    controls = load("diagnostic_v2.json")
    assert digest(HERE / "native_compact_v1.cpp") == first["source_sha256"]["source"]
    assert digest(HERE / "native_compact") == first["source_sha256"]["binary"]
    assert digest(HERE / "protocol.json") == second["first_protocol_sha256"]
    assert digest(HERE / "native_compact.cpp") == second["source_sha256"]
    assert digest(HERE / "native_compact_v2") == second["binary_sha256"]
    assert digest(HERE / "diagnostic_v2.json") == second["diagnostic_sha256"]
    assert digest(Path(first["source_paths"]["public_input"])) == second["public_input_sha256"]
    assert digest(HERE / "public_search_v2.json") == matched["compact_result_sha256"]
    prior_dir = GOAL / "n41_two_free_pair_s3_norm_20261008"
    assert digest(prior_dir / "native_batch.cpp") == matched["baseline_source_sha256"]
    assert digest(prior_dir / "native_batch") == matched["baseline_binary_sha256"]
    assert (HERE / "public_search.json").stat().st_size == 0
    assert second["first_attempt_status"] == "OUTPUT_WRITE_FAILURE_EMPTY_RECEIPT"
    assert [entry["accepted"] for entry in controls["controls"]] == [True, False]
    assert [entry["x_hits"] for entry in controls["controls"]] == [1, 0]
    assert new["status"] == old["status"] == "VERIFIED_RAW_ROW"
    assert new["target"] == old["target"] == first["target"]
    assert new["row"] == old["row"]
    assert new["residuals"] == old["residuals"] == 513088
    assert new["x_hits"] == old["x_hits"] == 6
    assert new["final_column_rejects"] == old["final_column_rejects"] == 5
    assert new["online_ns"] == (new["query_and_loop_ns"] +
                                 new["completion_probe_ns"] +
                                 new["internal_verification_ns"])
    for result in (new, old):
        assert result["online_ns"] < 120 * 10**9
        assert result["peak_rss_bytes"] < 4 * 1024**3
    assert audit["status"] == "PASS"
    assert audit["result_sha256"] == digest(HERE / "public_search_v2.json")
    assert audit["protocol_sha256"] == digest(HERE / "protocol_v2.json")
    assert audit["audit_source_sha256"] == digest(HERE / "audit.py")
    assert audit["exact_group_sum"] and audit["distinct_columns"] == 8
    assert audit["verified_subgroup_points"] == 8
    assert transfer["status"] == "FAIL_N131_EXPLICIT_PAIR_MEMORY_GATE"
    states = transfer["pair_states_per_domain_lower"]
    assert states == 34_448_654_064
    assert transfer["one_bit_per_state_bytes_lower"] == (states + 7) // 8
    assert transfer["one_domain_excess_bytes_lower"] == (states + 7) // 8 - 4 * 1024**3
    assert transfer["source_sha256"] == digest(HERE / "native_compact.cpp")
    report = {
        "kind": "n41_compact_lookup_receipt_verification",
        "status": "PASS_RECEIPTS",
        "proposal_id": first["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "verified_public_row": True,
        "compact_online_ns": new["online_ns"],
        "matched_original_online_ns": old["online_ns"],
        "matched_original_over_compact_ratio":
            f"{old['online_ns']/new['online_ns']:.6f}",
        "first_run_receipt_status": second["first_attempt_status"],
        "n131_transfer_status": transfer["status"],
        "verification_source_sha256": digest(Path(__file__)),
    }
    output = HERE / "verification.json"
    if output.exists():
        raise FileExistsError("preserve first verifier receipt")
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
