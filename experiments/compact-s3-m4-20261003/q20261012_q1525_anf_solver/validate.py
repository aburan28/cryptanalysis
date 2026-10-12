#!/usr/bin/env python3
"""Independent truth-table, receipt, and positive group replay for Q1525."""
from __future__ import annotations

import hashlib
import gzip
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import convert
import run

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def literal_value(lit: int, assignment: list[bool]) -> bool:
    return assignment[abs(lit)] == (lit > 0)


def anf_terms(line: str):
    tokens = line.split()
    assert tokens[0] == "x" and tokens[-1] == "0"
    terms = []
    index = 1
    while index < len(tokens) - 1:
        token = tokens[index]
        if token == "T":
            terms.append(None)
            index += 1
        elif token.startswith("."):
            size = int(token[1:])
            assert size >= 2
            terms.append([int(x) for x in tokens[index + 1:index + 1 + size]])
            index += 1 + size
        else:
            terms.append([int(token)])
            index += 1
    return terms


def anf_satisfied(terms, assignment: list[bool]) -> bool:
    parity = 0
    for term in terms:
        parity ^= int(term is None or all(literal_value(x, assignment) for x in term))
    return parity == 1  # DPLL_ANF's documented/implemented equation convention.


def xcnf_satisfied(is_xor: bool, lits: list[int], assignment: list[bool]) -> bool:
    if is_xor:
        return sum(literal_value(x, assignment) for x in lits) % 2 == 1
    return any(literal_value(x, assignment) for x in lits)


def core_assignment(stdout: str, nvars: int) -> list[bool]:
    bitstrings = [line[2:] for line in stdout.splitlines()
                  if line.startswith("s ") and set(line[2:]) <= {"0", "1"}]
    assert len(bitstrings) == 1 and len(bitstrings[0]) == nvars
    return [False] + [bit == "1" for bit in bitstrings[0]]


def check():
    protocol = run.read(HERE / "protocol.json")
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert sha(HERE / "convert.py") == protocol["converter_sha256"]
    assert sha(run.SOLVER) == protocol["solver_binary_sha256"]
    archive = run.read(HERE / "archive_manifest.json")
    for label, entry in archive["failed_encoding_v1"].items():
        packed = HERE / "failed_encoding_v1" / "formulas" / f"{label}.anf.gz"
        assert sha(packed) == entry["gzip_sha256"]
        assert hashlib.sha256(gzip.decompress(packed.read_bytes())).hexdigest() == entry["uncompressed_sha256"]
    assert subprocess.check_output(["git", "-C", str(run.SOLVER.parents[1]),
                                    "rev-parse", "HEAD"], text=True).strip() == protocol["solver_source_commit"]
    rows = []
    for label in protocol["panel_order"]:
        source = convert.PARENT / convert.INPUTS[label]
        formula = run.ensure_formula(label)
        frozen = protocol["inputs"][label]
        receipt = run.read(HERE / "runs" / label / "receipt.json")
        assert sha(source) == frozen["xcnf_sha256"]
        assert sha(formula) == frozen["anf_sha256"]
        assert sha(HERE / "runs" / label / "stdout.txt") == receipt["stdout_sha256"]
        assert sha(HERE / "runs" / label / "stderr.txt") == receipt["stderr_sha256"]
        assert receipt["label"] == label and receipt["candidate_id"] is None
        assert receipt["isogeny"] == "none"
        nvars, xrows = convert.parse_xcnf(source)
        with formula.open() as stream:
            header = stream.readline().split()
            assert header == ["p", "cnf", str(nvars), str(len(xrows))]
            lines = stream.readlines()
        assert len(lines) == len(xrows)
        patterns = [[False] * (nvars + 1), [True] * (nvars + 1)]
        for seed in (1519, 1525):
            rng = random.Random(seed + nvars)
            patterns.append([False] + [bool(rng.getrandbits(1)) for _ in range(nvars)])
        for (is_xor, lits), line in zip(xrows, lines):
            terms = anf_terms(line)
            assert all(anf_satisfied(terms, bits) == xcnf_satisfied(is_xor, lits, bits)
                       for bits in patterns)
        stdout = (HERE / "runs" / label / "stdout.txt").read_text()
        assert receipt["status"] in {"SAT_VERIFIED", "WALL_CAP", "INDETERMINATE", "UNSAT", "CPU_CAP", "PROCESS_FAILURE"}
        if receipt["status"] == "SAT_VERIFIED":
            bits = core_assignment(stdout, nvars)
            assert all(xcnf_satisfied(kind, lits, bits) for kind, lits in xrows)
            assert run.verify_sat(label, stdout) == receipt["verification"]
        else:
            assert receipt["verification"] is None
            assert "s SATISFIABLE" not in stdout
        if receipt["status"] == "WALL_CAP":
            assert receipt["termination_reason"] == "WALL_CAP"
            assert receipt["return_code"] == -15
        progress = [int(x) for x in re.findall(r"^c \|\s*\d+\s+\d+\s+(\d+)\s+\|", stdout, re.M)]
        rows.append({"label": label, "status": receipt["status"],
                     "nvars": nvars, "equations": len(xrows),
                     "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                     "child_user_cpu_seconds": receipt["child_user_cpu_seconds"],
                     "child_system_cpu_seconds": receipt["child_system_cpu_seconds"],
                     "peak_rss_bytes_darwin": receipt["child_peak_rss_bytes_darwin"],
                     "final_reported_conflicts": receipt["reported_conflicts_last"],
                     "periodic_conflicts_lower_bound": max(progress) if progress else None,
                     "verified_group_relation": bool(receipt["verification"])})
    assert [x["status"] for x in rows] == ["SAT_VERIFIED"] + ["WALL_CAP"] * 5
    assert any(x["child_user_cpu_seconds"] > 35 for x in rows if x["status"] == "WALL_CAP")
    return {"proposal_id": "Q1525", "candidate_id": None, "run_id": None,
            "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
            "solver_source_commit": protocol["solver_source_commit"],
            "solver_binary_sha256": protocol["solver_binary_sha256"],
            "protocol_sha256": sha(HERE / "protocol.json"),
            "rows": rows, "verified_ordinary_relations": 0,
            "ordinary_rank_increments": 0,
            "cost_per_useful_relation": None,
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    analysis = check()
    if sys.argv[1:] == ["--write-analysis"]:
        run.save(HERE / "analysis.json", analysis)
    else:
        assert sys.argv[1:] == []
        assert analysis == run.read(HERE / "analysis.json")
    print("PASS Q1525 six exact conversions, receipts, and N53 group replay")
