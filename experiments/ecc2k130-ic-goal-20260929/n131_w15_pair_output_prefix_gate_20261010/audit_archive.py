#!/usr/bin/env python3
"""Replay terminal XCNF and hash checks from the committed archive alone."""

import json
from pathlib import Path

from audit import formula, load, sha

HERE = Path(__file__).resolve().parent


def main():
    terminal = load(HERE / "terminal_audit.json")
    control = load(HERE / "control.json")
    result = load(HERE / "result.json")
    protocol = load(HERE / "protocol.json")
    assert terminal["status"] == "PASS_W15_PAIR_OUTPUT_PREFIX_TERMINAL_AUDIT"
    assert terminal["query_status"] == result["status"] == "CENSORED_TIME"
    assert terminal["target_q"] == result["target_q"] == protocol["target_q"]
    assert terminal["sha256"]["auditor"] == sha(HERE / "audit.py")
    for key, name in (("protocol", "protocol.json"),
                      ("control", "control.json"),
                      ("result", "result.json"),
                      ("control_formula", "control.xcnf.gz"),
                      ("public_formula", "system.xcnf.gz"),
                      ("stdout", "solver.stdout.txt"),
                      ("stderr", "solver.stderr.txt")):
        assert terminal["sha256"][key] == sha(HERE / name), name
    assert formula(HERE / "control.xcnf.gz", control["formula"],
                   control["added_trace_clauses"]) == terminal["control_formula"]
    assert formula(HERE / "system.xcnf.gz", result["formula"],
                   result["added_trace_clauses"]) == terminal["public_formula"]
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["sha256"]["group_lift"] == sha(HERE / "control_group_lift.json")
    assert result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert result["sha256"]["control"] == sha(HERE / "control.json")
    assert result["phase_seconds"]["construction_plus_search"] <= \
        protocol["construction_plus_search_cap_seconds"]
    assert terminal["sampled_peak_combined_rss_bytes"] == \
        result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    output = (HERE / "solver.stdout.txt").read_text(errors="replace")
    assert [line for line in output.splitlines() if line.startswith("s ")] == \
        result["solver_status_lines"]
    assert any(line.startswith("c rst ") for line in output.splitlines())
    print(json.dumps({"status": "PASS_ARCHIVED_W15_PREFIX_GATE_REPLAY",
                      "query_status": result["status"],
                      "formula_sha256": result["formula"]["sha256"],
                      "target_q": result["target_q"]}))


if __name__ == "__main__":
    main()
