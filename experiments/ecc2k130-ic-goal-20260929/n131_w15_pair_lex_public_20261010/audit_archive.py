#!/usr/bin/env python3
"""Replay the frozen terminal checks using only committed archive files."""

import json
from pathlib import Path

from audit import BASELINE, exact_added_clauses, formula, load, sha

HERE = Path(__file__).resolve().parent


def main():
    terminal = load(HERE / "terminal_audit.json")
    protocol = load(HERE / "protocol.json")
    control = load(HERE / "control.json")
    result = load(HERE / "result.json")
    semantics = load(HERE / "lex_semantics.json")
    assert terminal["status"] == "PASS_W15_PAIR_LEX_TERMINAL_AUDIT"
    assert terminal["query_status"] == result["status"] == "CENSORED_TIME"
    assert semantics["status"] == "PASS_W15_PAIR_LEX_SEMANTICS"
    assert semantics["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert semantics["source_sha256"]["circuit"] == sha(HERE / "circuit.py")
    assert terminal["sha256"]["auditor"] == sha(HERE / "audit.py")
    for key, name in (("protocol", "protocol.json"),
                      ("control", "control.json"), ("result", "result.json"),
                      ("control_formula", "control.xcnf.gz"),
                      ("public_formula", "system.xcnf.gz"),
                      ("stdout", "solver.stdout.txt"),
                      ("stderr", "solver.stderr.txt")):
        assert terminal["sha256"][key] == sha(HERE / name)
    assert formula(HERE / "control.xcnf.gz", control["formula"],
                   control["added_trace_clauses"]) == terminal["control_formula"]
    assert formula(HERE / "system.xcnf.gz", result["formula"],
                   result["added_trace_clauses"]) == terminal["public_formula"]
    delta_control = exact_added_clauses(BASELINE / "control.xcnf.gz",
                                        HERE / "control.xcnf.gz", 22)
    delta_public = exact_added_clauses(BASELINE / "system.xcnf.gz",
                                       HERE / "system.xcnf.gz", 22)
    assert delta_public == terminal["exact_formula_delta"]
    assert delta_control["added_clause_sha256"] == delta_public["added_clause_sha256"]
    assert terminal["lex_clause_count"] == delta_public["added_cnf_clauses"] == 90
    assert protocol["pair_order_symmetry_factor"] == 64
    assert int(protocol["lex_source_count"])*64 == int(protocol["source_count"])
    assert control["group_lift_status"] == "GROUP_LIFT_FOUND"
    assert control["sha256"]["group_lift"] == sha(HERE / "control_group_lift.json")
    assert result["model_lines"] == 0 and result["solver_status_lines"] == []
    assert result["phase_seconds"]["construction_plus_search"] <= \
        protocol["construction_plus_search_cap_seconds"]
    assert result["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    output = (HERE / "solver.stdout.txt").read_text(errors="replace")
    assert any(line.startswith("c rst ") for line in output.splitlines())
    print(json.dumps({"status": "PASS_ARCHIVED_W15_PAIR_LEX_REPLAY",
                      "query_status": result["status"],
                      "formula_sha256": result["formula"]["sha256"],
                      "added_clause_sha256": delta_public["added_clause_sha256"]}))


if __name__ == "__main__":
    main()
