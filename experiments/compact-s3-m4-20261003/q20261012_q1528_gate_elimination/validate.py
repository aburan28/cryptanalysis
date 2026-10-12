#!/usr/bin/env python3
"""Independent row semantics, archived receipts, and original-curve replay."""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import eliminate
import run

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "q20261012_q1527_native_gate_anf"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal(lit: int, assignment: dict[int, bool]) -> bool:
    return assignment[abs(lit)] == (lit > 0)


def anf_terms(line: str):
    tokens = line.split()
    assert tokens[0] == "x" and tokens[-1] == "0"
    terms = []
    i = 1
    while i < len(tokens) - 1:
        token = tokens[i]
        if token == "T":
            terms.append(None)
            i += 1
        elif token.startswith("."):
            size = int(token[1:])
            assert size >= 2
            terms.append([int(x) for x in tokens[i + 1:i + 1 + size]])
            i += size + 1
        else:
            terms.append([int(token)])
            i += 1
    return terms


def anf_satisfied(terms, assignment: dict[int, bool]) -> bool:
    return sum(term is None or all(literal(v, assignment) for v in term)
               for term in terms) % 2 == 1


def check() -> dict:
    p = run.read(HERE / "protocol.json")
    prior = run.read(BASE / "protocol.json")
    assert p["candidate_id"] is p["run_id"] is None and p["isogeny"] == "none"
    assert p["complete_n131_solve_work_log2"] is None
    assert p["q1527_protocol_sha256"] == sha(BASE / "protocol.json")
    assert p["q1527_analysis_sha256"] == sha(BASE / "analysis.json")
    assert p["converter_sha256"] == sha(HERE / "eliminate.py")
    assert p["runner_sha256"] == sha(HERE / "run.py")
    assert p["solver_binary_sha256"] == sha(run.SOLVER)
    assert subprocess.check_output(["git", "-C", str(run.SOLVER.parents[1]),
                                    "rev-parse", "HEAD"], text=True).strip() == p["solver_source_commit"]
    assert p["panel_order"] == prior["panel_order"]
    assert p["solver_options"] == prior["solver_options"]
    assert p["wall_seconds"] == prior["wall_seconds"]
    rows = []
    for label in p["panel_order"]:
        source, meta, original = eliminate.q1527.source_formula(label)
        data, counts, mapping, gates = eliminate.transform(source)
        frozen = p["inputs"][label]
        packed = HERE / "formulas" / f"{label}.anf.gz"
        assert data == gzip.decompress(packed.read_bytes())
        assert sha(packed) == frozen["gzip_sha256"]
        assert hashlib.sha256(data).hexdigest() == frozen["anf_sha256"]
        assert sha(original) == frozen["source_xcnf_sha256"] == prior["inputs"][label]["source_xcnf_sha256"]
        assert run.read(HERE / "formulas" / f"{label}.json") == {"label": label, "n": meta["n"],
            **counts, "source_xcnf_sha256": frozen["source_xcnf_sha256"],
            "anf_sha256": frozen["anf_sha256"], "gzip_sha256": frozen["gzip_sha256"]}
        assert frozen["variables"] == counts["variables"]
        assert counts["original_variables"] - counts["variables"] == len(gates)
        assert not any(abs(v) in gates for pair in source.and_cache for v in pair)
        retained, _ = eliminate.split_gate_clauses(source)
        lines = data.decode().splitlines()
        assert lines[0] == f"p cnf {counts['variables']} {counts['equations']}"
        assert len(lines) - 1 == counts["equations"] == len(retained) + len(source.xors)
        parsed = [anf_terms(line) for line in lines[1:]]
        assignments = []
        for constant in (False, True):
            assignments.append({old: constant for old in mapping})
        for seed in (1519, 1528):
            rng = random.Random(seed + source.variables)
            assignments.append({old: bool(rng.getrandbits(1)) for old in mapping})
        for live in assignments:
            full = dict(live)
            for z, (a, b) in gates.items():
                full[z] = literal(a, full) and literal(b, full)
            compact = {new: live[old] for old, new in mapping.items()}
            for old_row, terms in zip(retained, parsed[:len(retained)]):
                assert any(literal(v, full) for v in old_row) == anf_satisfied(terms, compact)
            for (old_row, rhs), terms in zip(source.xors, parsed[len(retained):]):
                assert (sum(full[v] for v in old_row) % 2 == int(rhs)) == anf_satisfied(terms, compact)
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
                     "original_variables": counts["original_variables"],
                     "variables": counts["variables"],
                     "equations": counts["equations"],
                     "eliminated_gate_variables": counts["eliminated_gate_variables"],
                     "quadratic_monomial_occurrences": counts["quadratic_monomial_occurrences"],
                     "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                     "child_user_cpu_seconds": receipt["child_user_cpu_seconds"],
                     "child_system_cpu_seconds": receipt["child_system_cpu_seconds"],
                     "peak_rss_bytes_darwin": receipt["child_peak_rss_bytes_darwin"],
                     "final_conflicts": receipt["reported_conflicts_last"],
                     "periodic_conflicts_lower_bound": max(progress) if progress else None,
                     "verified_group_relation": bool(receipt["verification"])})
    proof = run.read(HERE / "lean/proof_receipt.json")
    assert proof["exit_code"] == 0
    assert proof["source_sha256"] == sha(HERE / "lean/Eliminate.lean")
    assert proof["stdout_sha256"] == sha(HERE / "lean/build.stdout.txt")
    assert proof["stderr_sha256"] == sha(HERE / "lean/build.stderr.txt")
    assert (HERE / "lean/build.stdout.txt").read_text().count("does not depend on any axioms") == 3
    ordinary = [row for row in rows if row["label"] in ("n53_ordinary", "n83_selected", "n83_holdout")]
    hits = sum(x["verified_group_relation"] for x in ordinary)
    return {"proposal_id": "Q1528", "candidate_id": None, "run_id": None,
            "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
            "protocol_sha256": sha(HERE / "protocol.json"),
            "converter_sha256": sha(HERE / "eliminate.py"),
            "solver_binary_sha256": sha(run.SOLVER), "rows": rows,
            "verified_ordinary_relations": hits,
            "ordinary_rank_increments": 0 if not hits else None,
            "cost_per_useful_relation": None,
            "complete_n131_solve_work_log2": None,
            "challenge_dispatch_allowed": False}


if __name__ == "__main__":
    result = check()
    if sys.argv[1:] == ["--write-analysis"]:
        run.save(HERE / "analysis.json", result)
    else:
        assert not sys.argv[1:] and result == run.read(HERE / "analysis.json")
    print("PASS Q1528 exact row substitutions, receipts, and original-curve replay")
