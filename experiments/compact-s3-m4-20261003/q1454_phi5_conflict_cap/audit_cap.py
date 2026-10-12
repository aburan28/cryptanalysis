#!/usr/bin/env python3
"""Interpret CryptoMiniSat's indeterminate conflict-cap exit after Q1454."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]

import sys
sys.path.insert(0, str(PARENT))

from q1449_phi5_native_xor.common import sha  # noqa: E402

OUTPUT = HERE / "cap_interpretation.json"


def final_integer(output: str, name: str) -> int:
    assert "FINAL TOTAL SEARCH STATS" in output
    values = re.findall(rf"^c {name}\s+:\s+(\d+)\s", output, re.M)
    assert values, name
    assert len(set(values)) == 1, (name, values)
    return int(values[-1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol_path = HERE / "protocol.json"
    verification_path = HERE / "verification.json"
    parent_path = PARENT / "q1452_known_satisfiable_phi5/protocol.json"
    run = HERE / "runs/n53_known_satisfiable_ordinary"
    receipt_path = run / "receipt.json"
    stdout_path = run / "attempt_000.stdout.txt"
    stderr_path = run / "attempt_000.stderr.txt"
    protocol = json.loads(protocol_path.read_text())
    verification = json.loads(verification_path.read_text())
    parent = json.loads(parent_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    assert protocol["proposal_id"] == "Q1454"
    assert parent["proposal_id"] == "Q1452"
    assert protocol["parent_q1452_protocol_sha256"] == sha(parent_path)
    assert protocol["cells"]["53"] == parent["cells"]["53"]
    assert verification["status"] == "pass"
    assert verification["protocol_sha256"] == sha(protocol_path)
    assert verification["rows"][0]["receipt_sha256"] == sha(receipt_path)
    assert receipt["protocol_sha256"] == sha(protocol_path)
    assert receipt["status"] == "solver_error"
    assert receipt["verified_relation_count"] == 0
    assert receipt["verified_relation"] is None
    assert len(receipt["attempts"]) == 1
    attempt = receipt["attempts"][0]
    assert attempt["exit_code"] == 15
    assert attempt["solver_status"] == "error"
    assert attempt["stdout_sha256"] == sha(stdout_path)
    assert attempt["stderr_sha256"] == sha(stderr_path)
    assert attempt["model_sha256"] is None
    assert attempt["blocked_assignment"] is None
    command = attempt["command"]
    assert command[command.index("--maxconfl") + 1] == "1000000"
    assert command[command.index("--maxtime") + 1] == "480"
    assert command[command.index("--verbstat") + 1] == "3"
    stdout = stdout_path.read_text()
    assert re.search(r"^s INDETERMINATE$", stdout, re.M)
    assert not re.search(r"^s (SATISFIABLE|UNSATISFIABLE)$", stdout, re.M)
    conflicts = final_integer(stdout, "conflicts")
    decisions = final_integer(stdout, "decisions")
    assert conflicts >= protocol["solver_conflict_cap"]
    assert attempt["solver_process_wall_ns_exploratory"] < (
        protocol["solver_wall_cap_seconds"] * 1_000_000_000)
    assert (attempt["solver_child_user_cpu_ns"] +
            attempt["solver_child_system_cpu_ns"]) < (
                protocol["solver_wall_cap_seconds"] * 1_000_000_000)
    assert conflicts == attempt["exact_final_conflicts"]
    assert decisions == attempt["exact_final_decisions"]
    assert attempt["exact_final_propagations"] is None
    propagations = re.findall(
        r"^c propagations\s+:\s+([0-9]+[KMB]?)\s", stdout, re.M)
    assert propagations and len(set(propagations)) == 1
    result = {
        "kind": "q1454_crypto_minisat_conflict_cap_interpretation",
        "proposal_id": "Q1454", "candidate_id": None,
        "isogeny": "none", "status": "pass",
        "degree_n": 53,
        "curve_id": receipt["curve_id"],
        "workload_id": receipt["workload_id"],
        "target_preimage_index": receipt["target_preimage_index"],
        "selected_slice_known_satisfiable_by_archived_witness": True,
        "raw_runner_status": receipt["status"],
        "raw_solver_status": attempt["solver_status"],
        "native_exit_code": 15,
        "native_status_line": "s INDETERMINATE",
        "interpreted_outcome": "conflict_cap_indeterminate_no_model",
        "exact_final_conflicts": conflicts,
        "exact_final_decisions": decisions,
        "final_propagations_rounded_display": propagations[-1],
        "exact_final_propagations": None,
        "solver_process_wall_ns_exploratory": attempt[
            "solver_process_wall_ns_exploratory"],
        "solver_child_user_cpu_ns": attempt["solver_child_user_cpu_ns"],
        "solver_child_system_cpu_ns": attempt["solver_child_system_cpu_ns"],
        "verified_relation_count": 0,
        "successful_decomposition_cost_measured": False,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "scope": ("one deterministic search prefix on a known-satisfiable "
                  "N53 ordinary target slice; conflict counts are SAT "
                  "events, not field operations or a complete DLP cost"),
        "protocol_sha256": sha(protocol_path),
        "parent_q1452_protocol_sha256": sha(parent_path),
        "verification_sha256": sha(verification_path),
        "receipt_sha256": sha(receipt_path),
        "stdout_sha256": sha(stdout_path),
        "stderr_sha256": sha(stderr_path),
        "audit_source_sha256": sha(Path(__file__)),
    }
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1454 clean indeterminate conflict-cap audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print("Q1454 clean indeterminate conflict-cap audit: PASS")


if __name__ == "__main__":
    main()
