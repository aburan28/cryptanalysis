#!/usr/bin/env python3
"""Check the primary workload has exactly one predeclared public target."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    primary = json.loads((HERE / "primary_workload.json").read_text())
    corpus = json.loads((HERE / "workload.json").read_text())
    certificate = json.loads((HERE / "verification.json").read_text())
    derivation = json.loads((HERE / "primary_derivation.json").read_text())
    assert certificate["verified"] is True
    assert certificate["public_workload_sha256"] == sha(HERE / "workload.json")
    assert derivation["corpus_verification_sha256"] == sha(HERE / "verification.json")
    assert derivation["control_corpus_sha256"] == sha(HERE / "workload.json")
    assert derivation["producer_sha256"] == sha(HERE / "freeze_primary.py")
    assert derivation["control_corpus_id"] == corpus["workload_id"]
    assert primary["target_count"] == len(primary["targets"]) == 1
    assert primary["targets"] == [corpus["targets"][0]]
    assert primary["targets"][0]["index"] == corpus["primary_target_index"] == 0
    assert primary["source_curve_id"] == corpus["source_curve_id"]
    assert primary["descendant_curve_id"] == corpus["descendant_curve_id"]
    assert primary["route_id"] == corpus["route_id"]
    assert primary["point_encoding"] == corpus["point_encoding"]
    assert primary["input_law"] == corpus["input_law"]
    assert primary["target_scalar_domain"] == corpus["target_scalar_domain"]
    assert primary["subgroup_order"] > 0
    record = dict(primary)
    identity = record.pop("workload_id")
    digest = hashlib.sha256(json.dumps(record, sort_keys=True,
                                      separators=(",", ":"),
                                      ensure_ascii=False).encode("utf-8")).hexdigest()
    assert identity == digest[:12] == derivation["primary_workload_id"]
    assert digest == derivation["primary_identity_sha256"]
    print(json.dumps({"status": "PASS_ONE_TARGET_WORKLOAD_ID",
                      "workload_id": identity,
                      "corpus_workload_id": corpus["workload_id"]}))


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
