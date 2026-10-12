#!/usr/bin/env python3
"""Check Q1450 deeper paired logs against the frozen follow-up receipt."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
from run import BASE_BINARY, LINEAR_BINARY, input_row, sha  # noqa: E402


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_protocol = json.loads((PARENT / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    receipt = json.loads((HERE / "measurements.json").read_text())
    assert freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert freeze["runner_sha256"] == sha(HERE / "run.py")
    assert freeze["parent_protocol_sha256"] == sha(PARENT / "protocol.json")
    assert freeze["parent_runner_sha256"] == sha(PARENT / "run.py")
    assert freeze["parent_freeze_sha256"] == sha(PARENT / "freeze.json")
    assert freeze["parent_measurements_sha256"] == sha(PARENT / "measurements.json")
    assert freeze["binary_sha256"] == {"base": sha(BASE_BINARY),
                                      "linear": sha(LINEAR_BINARY)}
    assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
    assert receipt["candidate_id"] is receipt["run_id"] is None
    assert receipt["isogeny"] == "none"
    assert len(receipt["attempts"]) == 4
    for spec in parent_protocol["fields"]:
        degree = str(spec["degree"])
        assert freeze["inputs"][degree] == input_row(spec, "ordinary")
    excluded = {"seconds", "cpu_seconds", "peak_rss_raw", "field_api_calls",
                "linear_halftrace"}
    for row in receipt["attempts"]:
        log = HERE / row["log"]
        assert row["log_sha256"] == sha(log)
        result = json.loads(log.read_text().splitlines()[0])
        assert result == row["result"]
        assert row["field_api_method_entries"] == sum(
            result["field_api_calls"].values())
        assert row["linear_halftrace_basis_xors"] == result.get(
            "linear_halftrace", {}).get("basis_xors", 0)
        assert row["status_label"] == "BOUNDED_UNKNOWN"
        assert result["api_budget_hit"] is False
        assert result["final_link_matches"] == 0
        assert row["conflict_cap"] == protocol["ordinary_conflict_caps"][
            str(row["degree"])]
    for comp in receipt["comparisons"]:
        degree = comp["degree"]
        base, linear = [next(row for row in receipt["attempts"]
                             if row["degree"] == degree and row["variant"] == variant)
                        for variant in ("base", "linear")]
        same = ({k: v for k, v in base["result"].items() if k not in excluded} ==
                {k: v for k, v in linear["result"].items() if k not in excluded})
        assert comp["same_search_path"] is same is True
        assert comp["base_api_entries"] == base["field_api_method_entries"]
        assert comp["linear_api_entries"] == linear["field_api_method_entries"]
        assert comp["linear_basis_xors"] == linear["linear_halftrace_basis_xors"]
    assert receipt["complete_solve_work_log2"] is None
    assert receipt["degree131_challenge_gap_bits"] is None
    print("Q1450 FOLLOWUP VALIDATED: paired root-heavy paths and operation vectors")


if __name__ == "__main__":
    main()
