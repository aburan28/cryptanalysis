#!/usr/bin/env python3
"""Replay Q1449 input binding, operation accounting, and S3 control."""

import json
from pathlib import Path

from run import HERE, BASELINE, BINARY, PRIOR, PARENT, STAGE, check_inputs, sha, verify_s3


def main() -> None:
    inputs = json.loads((HERE / "inputs.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    measured = json.loads((HERE / "measurements.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    check_inputs(inputs)
    for label, path in (
        ("protocol", HERE / "protocol.json"),
        ("inputs", HERE / "inputs.json"),
        ("runner", HERE / "run.py"),
        ("binary", BINARY),
        ("solver_source", PARENT / "insearch.cpp"),
        ("build_script", PARENT / "build.sh"),
        ("counted_field_source", STAGE / "q20261011_operation_account/counted_onb.py"),
        ("matched_weight5_measurements", BASELINE),
        ("prior_campaign_measurements", PRIOR),
    ):
        assert freeze[label + "_sha256"] == sha(path), label
    assert measured["freeze_sha256"] == sha(HERE / "freeze.json")
    assert measured["candidate_id"] is measured["run_id"] is None
    assert measured["factor_base_actual_B"] is None
    assert measured["curve_id"] == protocol["curve_id"]
    assert measured["ordinary_workload_id"] == protocol["ordinary_workload_id"]
    assert measured["isogeny"] == "none"
    for label, row, inp in zip(("control", "ordinary_attempt"),
                               (measured["control"], measured["ordinary_attempt"]),
                               inputs["formula_rows"]):
        assert row["mode"] == inp["mode"]
        assert row["curve_id"] == inp["curve_id"]
        assert row["workload_id"] == inp["workload_id"]
        assert row["cnf_sha256"] == inp["cnf_sha256"]
        log = HERE / row["log"]
        assert row["log_sha256"] == sha(log)
        result = json.loads(log.read_text().splitlines()[0])
        assert row["result"] == result
        assert row["field_api_method_entry_events"] == sum(
            result["field_api_calls"].values())
        if label == "control":
            assert row["status_label"] == "ALGEBRAIC_MODEL"
            assert row["s3_verification"] == verify_s3(inp, log)
        else:
            assert row["status_label"] == "BOUNDED_UNKNOWN"
            assert result["api_budget_hit"]
            assert result["final_link_matches"] == 0
    baseline = json.loads(BASELINE.read_text())
    matched = next(row for row in baseline["attempts"]
                   if row["degree"] == 83 and row["mode"] == "ordinary"
                   and row["seed"] == 8 and row["early_limit"] == 1)
    assert measured["matched_weight5_api_entries"] == matched[
        "field_api_method_entry_events"]
    assert measured["matched_weight5_final_link_checks"] == matched[
        "result"]["final_link_checks"]
    prior = json.loads(PRIOR.read_text())
    prior_n83 = next(row for row in prior["cumulative_campaigns"]
                     if row["degree"] == 83)
    assert measured["prior_same_point_sat_api_entries"] == prior_n83[
        "cumulative_api_events"]
    assert measured["cumulative_same_point_sat_api_entries"] == (
        prior_n83["cumulative_api_events"] + measured["ordinary_attempt"][
            "field_api_method_entry_events"])
    assert measured["complete_solve_work_log2"] is None
    assert measured["degree131_challenge_gap_bits"] is None
    print("Q1449 VALIDATED: frozen input, control S3, censored ordinary API budget")


if __name__ == "__main__":
    main()
