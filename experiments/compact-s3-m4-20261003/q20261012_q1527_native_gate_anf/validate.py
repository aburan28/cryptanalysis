#!/usr/bin/env python3
"""Source binding, gate equivalence, solver receipts, and group replay."""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import gate_convert
import run

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "q20261012_q1525_anf_solver"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lit(literal: int, assignment: dict[int, bool]) -> bool:
    return assignment[abs(literal)] == (literal > 0)


def local_gate_check(a: int, b: int, z: int) -> None:
    assert len({abs(a), abs(b), z}) == 3
    for raw in range(8):
        assignment = {abs(a): bool(raw & 1), abs(b): bool(raw & 2),
                      z: bool(raw & 4)}
        clauses = (not assignment[z] or lit(a, assignment)) and (
            not assignment[z] or lit(b, assignment)) and (
            assignment[z] or not lit(a, assignment) or not lit(b, assignment))
        quadratic = assignment[z] == (lit(a, assignment) and lit(b, assignment))
        assert clauses == quadratic


def check() -> dict:
    p = run.read(HERE / "protocol.json")
    prior = run.read(BASE / "protocol.json")
    assert p["candidate_id"] is p["run_id"] is None and p["isogeny"] == "none"
    assert p["complete_n131_solve_work_log2"] is None
    assert p["q1525_protocol_sha256"] == sha(BASE / "protocol.json")
    assert p["q1525_analysis_sha256"] == sha(BASE / "analysis.json")
    assert p["q1519_handoff_source_sha256"] == sha(gate_convert.PARENT / "run.py")
    assert p["converter_sha256"] == sha(HERE / "gate_convert.py")
    assert p["runner_sha256"] == sha(HERE / "run.py")
    assert p["solver_binary_sha256"] == sha(run.SOLVER)
    assert subprocess.check_output(["git", "-C", str(run.SOLVER.parents[1]),
                                    "rev-parse", "HEAD"], text=True).strip() == p["solver_source_commit"]
    assert p["panel_order"] == prior["panel_order"]
    assert p["solver_options"] == prior["solver_options"]
    assert p["wall_seconds"] == prior["wall_seconds"]
    for n in (53, 83):
        for key in ("curve_id", "actual_B", "folded_K"):
            assert p[f"n{n}_{key}"] == prior[f"n{n}_{key}"]
    rows = []
    for label in p["panel_order"]:
        formula, meta, source = gate_convert.source_formula(label)
        data, counts = gate_convert.transform(formula)
        frozen = p["inputs"][label]
        packed = HERE / "formulas" / f"{label}.anf.gz"
        archived = gzip.decompress(packed.read_bytes())
        assert archived == data
        assert sha(packed) == frozen["gzip_sha256"]
        assert hashlib.sha256(data).hexdigest() == frozen["anf_sha256"]
        assert sha(source) == frozen["source_xcnf_sha256"] == prior["inputs"][label]["xcnf_sha256"]
        assert run.read(HERE / "formulas" / f"{label}.json") == {
            "label": label, "n": meta["n"], **counts,
            "source_xcnf_sha256": frozen["source_xcnf_sha256"],
            "anf_sha256": frozen["anf_sha256"], "gzip_sha256": frozen["gzip_sha256"]}
        assert frozen["equations"] == counts["equations"]
        assert counts["source_xcnf_rows"] - counts["equations"] == 2 * len(formula.and_cache)
        assert data.splitlines()[0] == f"p cnf {formula.variables} {counts['equations']}".encode()
        for (a, b), z in formula.and_cache.items():
            local_gate_check(a, b, z)
        receipt = run.read(HERE / "runs" / label / "receipt.json")
        stdout_file = HERE / "runs" / label / "stdout.txt"
        stderr_file = HERE / "runs" / label / "stderr.txt"
        assert receipt["label"] == label and receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        assert sha(stdout_file) == receipt["stdout_sha256"]
        assert sha(stderr_file) == receipt["stderr_sha256"]
        assert receipt["command"][1:-1] == p["solver_options"]
        stdout = stdout_file.read_text(errors="replace")
        if receipt["status"] == "SAT_VERIFIED":
            assert run.verify_sat(label, stdout) == receipt["verification"]
        else:
            assert receipt["verification"] is None
            assert "s SATISFIABLE" not in stdout
        if receipt["status"] == "WALL_CAP":
            assert receipt["termination_reason"] == "WALL_CAP"
            assert receipt["return_code"] == -15
        progress = [int(x) for x in re.findall(r"^c \|\s*\d+\s+\d+\s+(\d+)\s+\|", stdout, re.M)]
        rows.append({"label": label, "n": meta["n"], "status": receipt["status"],
                     "variables": counts["variables"], "equations": counts["equations"],
                     "and_gates": counts["and_gates"], "source_xcnf_rows": counts["source_xcnf_rows"],
                     "rows_saved": counts["rows_saved"],
                     "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                     "child_user_cpu_seconds": receipt["child_user_cpu_seconds"],
                     "child_system_cpu_seconds": receipt["child_system_cpu_seconds"],
                     "peak_rss_bytes_darwin": receipt["child_peak_rss_bytes_darwin"],
                     "final_conflicts": receipt["reported_conflicts_last"],
                     "periodic_conflicts_lower_bound": max(progress) if progress else None,
                     "verified_group_relation": bool(receipt["verification"])})
    proof = run.read(HERE / "lean/proof_receipt.json")
    assert proof["exit_code"] == 0
    assert proof["source_sha256"] == sha(HERE / "lean/Gate.lean")
    assert proof["stdout_sha256"] == sha(HERE / "lean/build.stdout.txt")
    assert proof["stderr_sha256"] == sha(HERE / "lean/build.stderr.txt")
    assert (HERE / "lean/build.stdout.txt").read_text().count("does not depend on any axioms") == 2
    ordinary = [row for row in rows if row["label"] in ("n53_ordinary", "n83_selected", "n83_holdout")]
    return {"proposal_id": "Q1527", "candidate_id": None, "run_id": None,
            "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
            "protocol_sha256": sha(HERE / "protocol.json"),
            "converter_sha256": sha(HERE / "gate_convert.py"),
            "solver_binary_sha256": sha(run.SOLVER), "rows": rows,
            "verified_ordinary_relations": sum(x["verified_group_relation"] for x in ordinary),
            "ordinary_rank_increments": 0 if not any(
                x["verified_group_relation"] for x in ordinary) else None,
            "cost_per_useful_relation": None,
            "complete_n131_solve_work_log2": None,
            "challenge_dispatch_allowed": False}


if __name__ == "__main__":
    output = check()
    if sys.argv[1:] == ["--write-analysis"]:
        run.save(HERE / "analysis.json", output)
    else:
        assert not sys.argv[1:] and output == run.read(HERE / "analysis.json")
    print("PASS Q1527 gate equivalence, six exact receipts, positive group replay")
