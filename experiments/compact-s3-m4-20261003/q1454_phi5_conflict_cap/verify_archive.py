#!/usr/bin/env python3
"""Audit Q1454's exact N53 XCNF, final counters, and returned models."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1451_phi5_fixed_target.build_formula import build  # noqa: E402
from q1448_torsion_phi5.verify_model import model_from_file, replay  # noqa: E402
from q1449_phi5_native_xor.common import (  # noqa: E402
    blocked_assignment, sha, sha_bytes, xcnf_bytes)

OUTPUT = HERE / "verification.json"
CONTROLS = PARENT / "q1452_known_satisfiable_phi5/controls.json"


def final_counter(stdout: str, name: str) -> int | None:
    if "FINAL TOTAL SEARCH STATS" not in stdout:
        return None
    values = re.findall(rf"^c {name}\s+:\s+(\d+)\s", stdout, re.M)
    return int(values[-1]) if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1454"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["point_decomposition_stage_code"] == "PDP4phi5"
    assert sha(CONTROLS) == protocol["controls_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    for name, digest in protocol["source_sha256"].items():
        assert sha(ROOT / name) == digest, name
    rows = []
    for n in (53,):
        cell = protocol["cells"][str(n)]
        output = HERE / "runs" / f"n{n}_known_satisfiable_ordinary"
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["protocol_sha256"] == sha(protocol_path)
        assert receipt["runner_source_sha256"] == protocol[
            "source_sha256"][str((HERE / "run_stage.py").relative_to(ROOT))]
        for name in ("curve_id", "workload_id", "factor_base_actual_B",
                     "folded_columns_K",
                     "factor_base_enumerated_set_sha256", "public_target",
                     "target_preimage_index", "selected_raw_target_x",
                     "target_preimage_x_count", "xcnf_variables",
                     "full_target_preimage_x_count", "cnf_clauses",
                     "native_xor_rows", "and_gates"):
            assert receipt[name] == cell[name], name
        assert receipt[
            "selected_slice_known_satisfiable_by_archived_witness"] is True
        assert receipt["witness_leaf_values_supplied_to_solver"] is False
        formula, meta = build(n, target_index=201)
        assert meta["target_preimage_index"] == 201
        assert meta["raw_target_x_values"] == [cell["selected_raw_target_x"]]
        assert meta["full_target_preimage_x_count"] == cell[
            "full_target_preimage_x_count"]
        assert len(formula.and_cache) == cell["and_gates"]
        assert sha_bytes(xcnf_bytes(formula)) == cell[
            "initial_xcnf_sha256"] == receipt["initial_xcnf_sha256"]
        archive = output / "initial_system.xcnf.gz"
        assert sha(archive) == receipt["initial_xcnf_archive_sha256"]
        assert gzip.decompress(archive.read_bytes()) == xcnf_bytes(formula)
        blocked = []
        verified = None
        for number, attempt in enumerate(receipt["attempts"]):
            assert attempt["number"] == number
            assert attempt["input_xcnf_sha256"] == sha_bytes(
                xcnf_bytes(formula))
            assert attempt["input_cnf_clauses"] == len(formula.clauses)
            assert attempt["native_xor_rows"] == len(formula.xors)
            command = attempt["command"]
            for flag, value in (
                ("--maxmatrixcols", protocol["max_matrix_columns"]),
                ("--maxmatrixrows", protocol["max_matrix_rows"]),
                ("--maxnummatrices", protocol["max_matrices"]),
                ("--autodisablegauss", 0),
                ("--verbstat", protocol["solver_final_stats_verbosity"]),
            ):
                assert command[command.index(flag) + 1] == str(value)
            prefix = f"attempt_{number:03d}"
            stdout = output / f"{prefix}.stdout.txt"
            stderr = output / f"{prefix}.stderr.txt"
            model_path = output / f"{prefix}.model.txt"
            assert sha(stdout) == attempt["stdout_sha256"]
            assert sha(stderr) == attempt["stderr_sha256"]
            matrix_match = re.search(
                r"^c \[matrix\] Using (\d+) matrices recovered from ",
                stdout.read_text(), re.M)
            assert (int(matrix_match.group(1)) if matrix_match else None) == (
                attempt["initial_gaussian_matrices_used"])
            restarts = re.findall(r"^c rst\s+.*$", stdout.read_text(), re.M)
            assert attempt["last_progress_conflicts_rounded"] == (
                restarts[-1].split()[6] if restarts else None)
            for name, key in (("conflicts", "exact_final_conflicts"),
                              ("decisions", "exact_final_decisions"),
                              ("propagations", "exact_final_propagations")):
                assert attempt[key] == final_counter(stdout.read_text(), name)
            assert attempt["solver_child_user_cpu_ns"] >= 0
            assert attempt["solver_child_system_cpu_ns"] >= 0
            if attempt["solver_status"] == "sat":
                assert attempt["exit_code"] == 10
                assert sha(model_path) == attempt["model_sha256"]
                assert model_path.read_bytes() == stdout.read_bytes()
                check = replay(formula, meta, model_path, cell["instance"])
                assert check == attempt["model_check"]
                if check["status"] == "verified_four_point_relation":
                    assert attempt["blocked_assignment"] is None
                    verified = check
                else:
                    block = blocked_assignment(
                        formula, meta, model_from_file(model_path))
                    assert block == attempt["blocked_assignment"]
                    blocked.append(block)
            else:
                assert not model_path.exists()
                assert attempt["blocked_assignment"] is None
        assert blocked == receipt["blocked_assignments"]
        assert verified == receipt["verified_relation"]
        assert receipt["verified_relation_count"] == int(verified is not None)
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["natural_relation_yield_estimate"] is None
        assert receipt["cost_per_useful_row"] is None
        assert receipt["target_dependent_stage_wall_ns_exploratory"] >= (
            receipt["formula_build_wall_ns_exploratory"] +
            receipt["solver_process_wall_ns_exploratory"] +
            receipt["model_replay_wall_ns_exploratory"])
        rows.append({
            "degree_n": n, "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "status": receipt["status"],
            "attempt_count": len(receipt["attempts"]),
            "blocked_model_count": len(blocked),
            "verified_relation_count": receipt["verified_relation_count"],
            "receipt_sha256": sha(receipt_path),
            "archive_sha256": sha(archive),
        })
    result = {
        "kind": "q1454_phi5_conflict_cap_archive_audit",
        "proposal_id": "Q1454", "candidate_id": None,
        "isogeny": "none", "status": "pass", "rows": rows,
        "protocol_sha256": sha(protocol_path),
        "ordinary_n53_relation_measured": bool(rows[0][
            "verified_relation_count"]),
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1454 independent N53 archive audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print("Q1454 independent N53 archive audit: PASS")


if __name__ == "__main__":
    main()
