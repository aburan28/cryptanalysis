#!/usr/bin/env python3
"""Extend the Q1450 paired search into its root-heavy conflict interval."""

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import run as parent  # noqa: E402


def main():
    assert not (HERE / "freeze.json").exists()
    assert not (HERE / "measurements.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_protocol = json.loads((PARENT / "protocol.json").read_text())
    parent_freeze = json.loads((PARENT / "freeze.json").read_text())
    assert protocol["proposal_id"] == parent_protocol["proposal_id"] == "Q1450"
    assert parent_freeze["protocol_sha256"] == parent.sha(PARENT / "protocol.json")
    for spec in parent_protocol["fields"]:
        for mode in ("control", "ordinary"):
            assert parent_freeze["inputs"][str(spec["degree"])][mode] == (
                parent.input_row(spec, mode))
    freeze = {
        "proposal_id": "Q1450", "candidate_id": None, "run_id": None,
        "protocol_sha256": parent.sha(HERE / "protocol.json"),
        "runner_sha256": parent.sha(Path(__file__)),
        "parent_protocol_sha256": parent.sha(PARENT / "protocol.json"),
        "parent_runner_sha256": parent.sha(PARENT / "run.py"),
        "parent_freeze_sha256": parent.sha(PARENT / "freeze.json"),
        "parent_measurements_sha256": parent.sha(PARENT / "measurements.json"),
        "binary_sha256": {"base": parent.sha(parent.BASE_BINARY),
                          "linear": parent.sha(parent.LINEAR_BINARY)},
        "inputs": {str(spec["degree"]): parent_freeze["inputs"][
            str(spec["degree"])]["ordinary"]
                   for spec in parent_protocol["fields"]},
    }
    (HERE / "freeze.json").write_text(json.dumps(freeze, indent=2,
                                                  sort_keys=True) + "\n")
    parent.HERE = HERE
    attempts = []
    for name in protocol["comparison_order"]:
        degree, variant = name[1:].split("_")
        spec = next(s for s in parent_protocol["fields"]
                    if s["degree"] == int(degree))
        run_protocol = copy.deepcopy(parent_protocol)
        run_protocol["solver"]["ordinary_conflict_cap"] = protocol[
            "ordinary_conflict_caps"][degree]
        run_protocol["solver"]["ordinary_api_budget"] = protocol[
            "ordinary_api_budget"]
        run_protocol["solver"]["ordinary_wall_cap_seconds"] = protocol[
            "ordinary_wall_cap_seconds"]
        run_protocol["solver"]["external_process_timeout_seconds"] = protocol[
            "external_process_timeout_seconds"]
        row = parent.run_one(spec, freeze["inputs"][degree], variant,
                             run_protocol)
        attempts.append(row)
        print(json.dumps({"degree": row["degree"], "variant": variant,
                          "status": row["status_label"],
                          "conflicts": row["result"]["conflicts"],
                          "final_checks": row["result"]["final_link_checks"],
                          "api": row["field_api_method_entries"],
                          "basis_xors": row["linear_halftrace_basis_xors"]},
                         sort_keys=True), flush=True)
    comparison = []
    for degree in (53, 83):
        base, linear = [next(row for row in attempts if row["degree"] == degree
                             and row["variant"] == variant)
                        for variant in ("base", "linear")]
        excluded = {"seconds", "cpu_seconds", "peak_rss_raw", "field_api_calls",
                    "linear_halftrace"}
        same_path = ({k: v for k, v in base["result"].items()
                      if k not in excluded} ==
                     {k: v for k, v in linear["result"].items()
                      if k not in excluded})
        comparison.append({"degree": degree, "same_search_path": same_path,
                           "base_api_entries": base["field_api_method_entries"],
                           "linear_api_entries": linear["field_api_method_entries"],
                           "linear_basis_xors": linear[
                               "linear_halftrace_basis_xors"],
                           "complete_solve_work_log2": None})
    receipt = {"proposal_id": "Q1450", "candidate_id": None,
               "run_id": None, "isogeny": "none",
               "freeze_sha256": parent.sha(HERE / "freeze.json"),
               "attempts": attempts, "comparisons": comparison,
               "complete_solve_work_log2": None,
               "degree131_challenge_gap_bits": None}
    (HERE / "measurements.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
