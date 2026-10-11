#!/usr/bin/env python3
"""Bind the exact control, independent replay, and capped complete scan."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    protocol = read("protocol.json")
    profile = read("profile.json")
    audit = read("audit.json")
    failure = read("audit_failure_v1.json")
    interruption = read("interruption.json")
    paths = {"source": HERE / "run.py",
             "previous": BASE / "n41_linearized_bucket_composition_20261011/run.py",
             "geometry": BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for key, path in paths.items():
        assert sha(path) == protocol["sha256"][key], key
    assert sha(HERE / "protocol.json") == audit["protocol_sha256"]
    assert sha(HERE / "protocol.json") == interruption["protocol_sha256"]
    assert sha(HERE / "profile.json") == audit["profile_sha256"]
    assert sha(HERE / "run.stdout.txt") == interruption["stdout_sha256"]
    assert sha(HERE / "run.stderr.txt") == interruption["stderr_sha256"]
    assert sha(HERE / "audit.py") == audit["source_sha256"]
    assert sha(HERE / "audit_v1.py") == failure["source_sha256"]
    rows = profile["profile"]
    assert len(rows) == 16 and all(row["updates"] == 15 for row in rows)
    assert {(row["kind"], row["option"], row["right_seed"]) for row in rows} == {
        (kind, option, seed) for kind in ("positive", "negative")
        for option in range(4) for seed in (5, 17)}
    positives = [row for row in rows if row["gcd_degree"] > 0]
    assert len(positives) == 1
    assert (positives[0]["kind"], positives[0]["option"],
            positives[0]["right_seed"]) == ("positive", 3, 5)
    assert audit["status"] == "PASS_EXACT_TWO_BUCKET_CONTROL"
    assert len(audit["direct_case_checks"]) == 8
    assert audit["projected_pair_witness_match"]
    assert failure["status"] == "AUDIT_PRODUCER_FAILURE" and failure["exit_code"] == 134
    row = interruption["completed_raw_options"]
    assert interruption["status"] == "INTERRUPTED_AFTER_CENSORED_OPTION"
    assert interruption["producer_exit_code"] == 143 and not interruption["result_json_written"]
    assert len(row) == 1 and row[0]["status"] == "CENSORED_TIME"
    assert row[0]["kind"] == "positive" and row[0]["option"] == 0
    assert row[0]["bucket_pairs"] == 693 == 11*63
    assert row[0]["wall_s"] > protocol["raw_option_wall_cap_seconds"]
    assert row[0]["hits"] == 0
    print(json.dumps({"status": "PASS_EXACT_PROFILE_AND_CENSORED_SCAN_BINDING",
                      "profile_cases": len(rows), "audit_cases": len(audit["direct_case_checks"]),
                      "censored_bucket_pairs": row[0]["bucket_pairs"]}))


if __name__ == "__main__":
    main()
