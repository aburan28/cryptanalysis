#!/usr/bin/env python3
"""Validate frozen Q1450 roots, source/input binding, and paired search path."""

import json
from pathlib import Path

from run import (BASE, BASE_BINARY, HERE, LINEAR_BINARY, ROOT, STAGE,
                 input_row, sha)


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    receipt = json.loads((HERE / "measurements.json").read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
    assert freeze["proposal_id"] == receipt["proposal_id"] == "Q1450"
    assert receipt["candidate_id"] is receipt["run_id"] is None
    paths = {
        "linear_oracle": HERE / "s3_root_oracle_linear.py",
        "linear_solver": HERE / "insearch.cpp",
        "linear_build": HERE / "build.sh",
        "base_oracle": STAGE / "s3_root_oracle.py",
        "base_solver": BASE / "insearch.cpp",
        "base_build": BASE / "build.sh",
        "counted_field": STAGE / "q20261011_operation_account/counted_onb.py",
        "field": ROOT / "ecc2k130/codegen/field.py",
        "runner": HERE / "run.py",
        "validator": HERE / "validate_linear.py",
    }
    for name, path in paths.items():
        assert freeze["sources_sha256"][name] == sha(path), name
    assert freeze["binaries_sha256"]["base"] == sha(BASE_BINARY)
    assert freeze["binaries_sha256"]["linear"] == sha(LINEAR_BINARY)
    for spec in protocol["fields"]:
        for mode in ("control", "ordinary"):
            assert freeze["inputs"][str(spec["degree"])][mode] == input_row(
                spec, mode)
    for row in receipt["controls"] + receipt["ordinary_attempts"]:
        result = json.loads((HERE / row["log"]).read_text().splitlines()[0])
        assert result == row["result"]
        assert row["log_sha256"] == sha(HERE / row["log"])
        assert row["field_api_method_entries"] == sum(
            result["field_api_calls"].values())
        assert row["linear_halftrace_basis_xors"] == result.get(
            "linear_halftrace", {}).get("basis_xors", 0)
        assert row["isogeny"] == "none"
        if row["mode"] == "control":
            assert row["status_label"] == "ALGEBRAIC_MODEL"
            assert row["s3_verification"]["status"] == "verified_s3"
        else:
            assert row["status_label"] == "BOUNDED_UNKNOWN"
            assert result["final_link_matches"] == 0
            assert result["api_budget_hit"] is False
    assert len(receipt["controls"]) == 2
    assert len(receipt["ordinary_attempts"]) == 4
    excluded = {"seconds", "cpu_seconds", "peak_rss_raw", "field_api_calls",
                "linear_halftrace"}
    for degree in (53, 83):
        base = next(row for row in receipt["ordinary_attempts"]
                    if row["degree"] == degree and row["variant"] == "base")
        linear = next(row for row in receipt["ordinary_attempts"]
                      if row["degree"] == degree and row["variant"] == "linear")
        assert base["curve_id"] == linear["curve_id"]
        assert base["workload_id"] == linear["workload_id"]
        assert base["factor_base_enumerated_set_sha256"] == linear[
            "factor_base_enumerated_set_sha256"]
        assert {k: v for k, v in base["result"].items() if k not in excluded} == {
            k: v for k, v in linear["result"].items() if k not in excluded}
    assert receipt["complete_solve_work_log2"] is None
    assert receipt["degree131_challenge_gap_bits"] is None
    print("Q1450 VALIDATED: exact search path, frozen receipts, control S3")


if __name__ == "__main__":
    main()
