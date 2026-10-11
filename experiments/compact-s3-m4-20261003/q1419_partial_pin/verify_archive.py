#!/usr/bin/env python3
"""Replay archived Q1419 SAT models against the serialized XCNF and curve."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from run_cell import (CELLS, HERE, PROTOCOL, build_cell, canonical_digest,
                      read_profile, sha, verify_relation)


def parsed_model(stdout: str):
    if "s SATISFIABLE" not in stdout:
        return None
    model = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for token in line[2:].split():
                lit = int(token)
                if lit:
                    assert abs(lit) not in model
                    model[abs(lit)] = lit > 0
    return model


def check_serialized_xcnf(raw: bytes, model: dict[int, bool]) -> dict:
    """Parse the actual archived bytes, independently of Formula.write()."""
    lines = raw.decode("ascii").splitlines()
    header = lines.pop(0).split()
    assert header[:2] == ["p", "cnf"] and len(header) == 4
    variables, expected_rows = int(header[2]), int(header[3])
    assert set(model) == set(range(1, variables + 1))
    clauses = xors = 0
    for line in lines:
        tokens = line.split()
        assert tokens and tokens[-1] == "0"
        if tokens[0].startswith("x"):
            first = tokens[0][1:]
            assert first and first.lstrip("-").isdigit()
            literals = [int(first), *(int(value) for value in tokens[1:-1])]
            assert all(1 <= abs(lit) <= variables for lit in literals)
            # CryptoMiniSat XCNF parity: x<first> ... 0 means true;
            # x-<first> ... 0 means false, with all following literals
            # positive in this writer's normalized rows.
            assert all(lit > 0 for lit in literals[1:])
            wanted = first[0] != "-"
            assert (sum(model[abs(lit)] for lit in literals) & 1) == int(wanted)
            xors += 1
        else:
            literals = [int(value) for value in tokens[:-1]]
            assert all(1 <= abs(lit) <= variables for lit in literals)
            assert any(model[abs(lit)] == (lit > 0) for lit in literals)
            clauses += 1
    assert clauses + xors == expected_rows
    return {"variables": variables, "cnf_clauses": clauses, "xor_rows": xors}


def verify_cell(protocol: dict, degree: int, cell: str) -> dict:
    path = HERE / "runs" / f"n{degree}_{cell}"
    receipt_path = path / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    profile, parent, fixture = read_profile(protocol, degree)
    assert receipt["proposal_id"] == "Q1419"
    assert receipt["candidate_id"] is None and receipt["run_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["curve_id"] == profile["curve_id"]
    assert receipt["factor_base_actual_B"] == profile["factor_base_actual_B"]
    assert receipt["folded_columns_K"] == profile["folded_columns_K"]
    assert receipt["workload_id"] == profile["workload_id"]
    assert receipt["pinning_policy"] == protocol["cells"][cell]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol["runner_source_sha256"]
    assert receipt["runtime_info_sha256"] == protocol["runtime_info_sha256"]
    assert receipt["solver_wall_seconds_exploratory"] >= 0
    assert receipt["formula_build_seconds_exploratory"] >= 0
    assert receipt["relation_check_seconds_exploratory"] >= 0
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["complete_solve_work_log2"] is None
    assert receipt["is_ordinary_yield_measurement"] is False
    assert receipt["is_complete_solve_projection"] is False
    assert receipt["stage_config_sha256_full"] == canonical_digest(
        receipt["stage_config_hash_input"])
    assert receipt["stage_config_id"].endswith(
        "h" + receipt["stage_config_sha256_full"][:12])
    assert receipt["stage_run_id"] == (
        f"{receipt['stage_config_id']}W{profile['workload_id']}R1")
    assert receipt["stage_config_hash_input"]["point_decomposition"][
        "pinning_policy"] == protocol["cells"][cell]
    assert receipt["stage_config_hash_input"]["factor_base"] == profile[
        "factor_base"]
    assert receipt["stage_config_hash_input"]["curve"] == profile["curve"]
    assert sha(path / "solver.stdout.txt") == receipt["solver_stdout_sha256"]
    assert sha(path / "solver.stderr.txt") == receipt["solver_stderr_sha256"]
    assert sha(path / "system.xcnf.gz") == receipt["formula_archive_sha256"]
    raw = gzip.decompress((path / "system.xcnf.gz").read_bytes())
    assert len(raw) == receipt["formula_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == receipt["formula_raw_sha256"]
    stdout = (path / "solver.stdout.txt").read_text()
    model = parsed_model(stdout)
    assert (model is not None) == receipt["model_present"]
    if receipt["solver_status"] == "sat":
        assert receipt["solver_return_code"] == 10 and model is not None
        parsed_stats = check_serialized_xcnf(raw, model)
        for key, value in parsed_stats.items():
            assert receipt["formula"][key] == value
        formula, leaves, _ = build_cell(profile, parent, fixture, cell)
        assert formula.variables == parsed_stats["variables"]
        relation = verify_relation(profile, model, leaves)
        assert receipt["model_check"] == relation
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
        status = relation["status"]
    else:
        assert model is None and receipt["verified_relation_count"] == 0
        assert receipt["model_check"] is None
        assert receipt["solver_status"] in (
            "unsat", "censored", "external_timeout")
        status = receipt["solver_status"]
    return {"degree": degree, "cell": cell, "status": status,
            "receipt_sha256": sha(receipt_path),
            "solver_conflicts_reported": receipt["solver_conflicts_reported"],
            "solver_wall_seconds_exploratory": receipt[
                "solver_wall_seconds_exploratory"],
            "verified_relation_count": receipt["verified_relation_count"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["verifier_source_sha256"] == sha(Path(__file__))
    checks = []
    missing = []
    for degree in (53, 83):
        for cell in CELLS:
            path = HERE / "runs" / f"n{degree}_{cell}" / "receipt.json"
            if path.exists():
                checks.append(verify_cell(protocol, degree, cell))
            else:
                missing.append(f"n{degree}_{cell}")
    assert not args.require_complete or not missing
    result = {"kind": "q1419_archive_verification", "proposal_id": "Q1419",
              "protocol_sha256": sha(PROTOCOL),
              "verifier_source_sha256": sha(Path(__file__)),
              "checks": checks, "missing": missing,
              "complete": not missing,
              "natural_relation_yield_estimate": None,
              "complete_solve_work_log2": None}
    if args.emit:
        (HERE / "verification.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"checked": len(checks), "missing": missing,
                      "verified_relations": sum(row["verified_relation_count"]
                                                for row in checks)}))


if __name__ == "__main__":
    main()
