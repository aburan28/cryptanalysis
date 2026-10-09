#!/usr/bin/env python3
"""Cross-check frozen sources, Sage controls, native controls, and failure gates."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((HERE / name).read_text())


def main():
    output = HERE / "verification.json"
    if output.exists():
        raise FileExistsError("preserve first verification")
    protocol = load("protocol.json")
    freeze = load("native_freeze.json")
    runtime = load("sage_runtime_info.json")
    sage = load("result.json")
    controls = load("native_controls.json")
    search = load("native_search.json")
    transfer = load("transfer_gate.json")
    prior_audit = json.loads((HERE / protocol["positive_control_sage_audit"]).read_text())
    assert runtime["status"] == "verified" and prior_audit["status"] == "PASS"
    assert freeze["status"] == "FROZEN_BEFORE_PUBLIC_SEARCH"
    assert freeze["source_sha256"] == sha(HERE / "native_batch.cpp")
    assert freeze["binary_sha256"] == sha(HERE / "native_batch")
    assert freeze["input_sha256"] == sha(HERE / protocol["frozen_input_source"])
    assert freeze["diagnostic_sha256"] == sha(HERE / "native_controls.json")
    assert sage["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert sage["source_sha256"]["run_sage"] == sha(HERE / "run_sage.py")
    assert sage["source_sha256"]["sage_runtime_info"] == sha(HERE / "sage_runtime_info.json")
    assert sage["source_sha256"]["sage_audit"] == sha(HERE / protocol["positive_control_sage_audit"])
    assert sage["status"] == "TIME_CAP" and len(sage["probes"]) == 2
    positive, negative = sage["probes"]
    assert positive["name"] == "known_row" and positive["accepted"]
    assert positive["gcd_degree"] == 1 and len(positive["verified_group_witness_x_pairs"]) == 1
    assert negative["name"] == "prefix_0_0" and not negative["accepted"]
    assert negative["gcd_degree"] == 0 and not negative["verified_group_witness_x_pairs"]
    assert [control["residual"] for control in controls["controls"]] == [
        positive["residual"], negative["residual"]]
    assert [control["accepted"] for control in controls["controls"]] == [True, False]
    assert [control["scanned_b"] for control in controls["controls"]] == [538, 978]
    assert search["status"] == "ONLINE_TIME_CAP" and search["row"] is None
    assert search["target"] == protocol["public_target_q"] == freeze["target"]
    assert search["pair_list_sizes"] == [1956] * 4
    assert search["unique_x_sizes"] == [978, 978]
    assert search["residuals"] == 75264 and search["x_hits"] == 0
    assert search["scanned_b"] == search["residuals"] * 978
    assert 120_000_000_000 <= search["online_ns"] < 121_000_000_000
    assert search["peak_rss_bytes"] < freeze["limits"]["peak_rss_bytes"]
    assert transfer["status"] == "FAIL_N131_4GIB_EXPLICIT_STATE_MEMORY_GATE"
    assert transfer["minimum_one_bit_per_state_bytes"] > transfer["memory_cap_bytes"]
    assert transfer["source_sha256"]["n41_native_search"] == sha(HERE / "native_search.json")
    report = {
        "kind": "n41_two_free_pair_s3_norm_receipt_verification",
        "status": "PASS_RECEIPTS",
        "proposal_id": freeze["proposal_id"],
        "candidate_id": None,
        "run_id": None,
        "sage_controls": [True, False],
        "native_controls": [True, False],
        "public_search_status": search["status"],
        "n131_transfer_status": transfer["status"],
        "source_sha256": {name: sha(HERE / name) for name in (
            "protocol.json", "run_sage.py", "result.json", "native_batch.cpp",
            "native_batch", "native_freeze.json", "native_controls.json",
            "native_search.json", "transfer_gate.py", "transfer_gate.json")},
    }
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
