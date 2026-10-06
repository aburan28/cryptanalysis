#!/usr/bin/env python3
"""Run or verify Q1461 native exact-pair comparison on frozen inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_protocol(protocol: dict) -> None:
    assert protocol["proposal_id"] == "Q1461"
    assert protocol["candidate_id"] is None and protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    for section in ("source_sha256", "input_sha256"):
        for relative, digest in protocol[section].items():
            assert sha(ROOT / relative) == digest, relative
    build = json.loads((HERE / "compile_receipt.json").read_text())
    assert sha(HERE / "probe") == build["binary_sha256"]["probe"]
    assert sha(HERE / "control_roots") == build[
        "binary_sha256"]["control_roots"]


def run_degree(n: int, protocol: dict) -> dict:
    field = PARENT / "q1420_root_theory" / f"n{n}_field.txt"
    text_input = (HERE / f"n{n}_inputs.txt").read_text()
    completed = subprocess.run(
        [str(HERE / "probe"), str(field), str(4 if n == 53 else 6),
         str(protocol["sum_candidate_cap"]), str(protocol["direct_pair_cap"])],
        input=text_input, check=True, capture_output=True, text=True)
    rows = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(rows) == 18 and rows[0]["kind"] == "setup"
    assert rows[0]["degree_n"] == n
    states = rows[1:]
    assert states[0]["cell"] == f"n{n}_planted"
    assert [row["cell"] for row in states[1:]] == [
        f"n{n}_ordinary"] * 16
    assert [row["state_index"] for row in states[1:]] == list(range(16))
    control = next(row for row in json.loads((PARENT /
        "q1448_torsion_phi5/validation.json").read_text())["rows"]
                   if row["degree_n"] == n)
    a, b = control["raw_leaf_x"][:2]
    assert [f"{a:x}", f"{b:x}"] in states[0]["witness_pairs"]
    assert all(row["sum_candidate_count"] == row["sums_visited"]
               for row in states)
    return {
        "curve_id": protocol["cells"][f"n{n}_ordinary"]["curve_id"],
        "ordinary_workload_id": protocol["cells"][f"n{n}_ordinary"][
            "workload_id"],
        "setup": rows[0],
        "positive_control": states[0],
        "ordinary_archived_states": states[1:],
        "ordinary_verified_pairs": sum(row["verified_pairs"]
                                       for row in states[1:]),
    }


def make_result() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    check_protocol(protocol)
    return {
        "kind": "q1461_sparse_sum_inverse_result",
        "proposal_id": "Q1461", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "protocol_sha256": sha(PROTOCOL),
        "cells": {f"n{n}": run_degree(n, protocol) for n in (53, 83)},
        "cpu_isolation_receipt": None,
        "controlled_wall_speedup": None,
        "successful_decomposition_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def untimed(data: dict) -> dict:
    return {key: (untimed(value) if isinstance(value, dict) else
                  [untimed(item) if isinstance(item, dict) else item
                   for item in value] if isinstance(value, list) else value)
            for key, value in data.items()
            if not key.endswith("wall_ns_exploratory")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_result()
    if args.check:
        assert untimed(result) == untimed(json.loads(OUTPUT.read_text()))
        print("Q1461 exact pair sets and operation counts: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1461", "status": "pass",
                          "ordinary_verified_pairs": {
                              key: cell["ordinary_verified_pairs"]
                              for key, cell in result["cells"].items()}}))


if __name__ == "__main__":
    main()
