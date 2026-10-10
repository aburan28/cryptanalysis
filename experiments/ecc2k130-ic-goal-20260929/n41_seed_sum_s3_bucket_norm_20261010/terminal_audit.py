#!/usr/bin/env python3
"""Bind the independent Sage audit to the frozen bucket-norm receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "terminal_audit.json"
    if output.exists():
        raise FileExistsError(output)
    verification = json.loads((HERE / "verification.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    protocol = json.loads((HERE / "sage_audit_protocol.json").read_text())
    prior = json.loads((BASE / "n41_two_free_pair_s3_norm_20261008/native_controls.json").read_text())
    assert verification["status"] == "PASS_SEED_SUM_S3_BUCKET_NORM"
    assert audit["status"] == "PASS" and audit["independent_group_witness"]
    for key, path in [("source", HERE / "sage_audit.py"),
                      ("geometry", BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"),
                      ("affine_result", HERE / "affine_rank_result.json"),
                      ("exact_result", HERE / "result.json"),
                      ("batch_result", HERE / "batch_result.json"),
                      ("runtime", HERE / "sage_runtime_info.json")]:
        assert protocol["sha256"][key] == sha(path)
    assert audit["source_sha256"] == sha(HERE / "sage_audit.py")
    assert audit["protocol_sha256"] == sha(HERE / "sage_audit_protocol.json")
    assert [x["trace_zero_x_count"] for x in audit["domain_checks"]] == [978, 978]
    assert len(audit["sampled_bucket_product_ranks"]) == 4
    assert all(x["cross_product_rank"] == 41 for x in audit["sampled_bucket_product_ranks"])
    assert [x["residual"] for x in prior["controls"]] == [
        [332635421840, 2054854538524], [87763439808, 1229415118085]]
    assert [x["accepted"] for x in prior["controls"]] == [True, False]
    assert verification["affine_result_sha256"] == sha(HERE / "affine_rank_result.json")
    assert verification["exact_result_sha256"] == sha(HERE / "result.json")
    assert verification["batch_result_sha256"] == sha(HERE / "batch_result.json")
    result = {"status": "PASS_SEED_SUM_S3_TERMINAL_AUDIT",
              "source_sha256": sha(Path(__file__)),
              "verification_sha256": sha(HERE / "verification.json"),
              "sage_audit_sha256": sha(HERE / "sage_audit.json"),
              "sage_audit_protocol_sha256": sha(HERE / "sage_audit_protocol.json"),
              "prior_native_controls_sha256": sha(BASE / "n41_two_free_pair_s3_norm_20261008/native_controls.json")}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(result["status"])


if __name__ == "__main__":
    main()
