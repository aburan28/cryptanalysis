#!/usr/bin/env python3
"""Independently replay S3 root constraints and returned SAT relations."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
Q1419 = PARENT / "q1419_partial_pin"
sys.path[:0] = [str(PARENT), str(Q1419), str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
from chain_s3 import evaluate_s3  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from run_cell import read_profile, verify_relation  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify_formula(n, cell):
    original = gzip.decompress((Q1419 / "runs" /
        f"n{n}_free_mids/system.xcnf.gz").read_bytes()).decode().splitlines()
    raw = gzip.decompress((HERE / "inputs" / f"n{n}.xcnf.gz").read_bytes())
    new = raw.decode().splitlines()
    old_vars, old_rows = map(int, original[0].split()[2:])
    new_vars, new_rows = map(int, new[0].split()[2:])
    old_cnf = cell["original_cnf_clauses"]
    old_xor = old_rows - old_cnf
    assert old_vars == cell["original_variables"]
    assert new_vars - old_vars == cell["added_variables"] == 2
    assert new_rows - old_rows == cell["added_cnf_clauses"] == 4*n
    assert original[1:1+old_cnf] == new[1:1+old_cnf]
    assert original[-old_xor:] == new[-old_xor:]
    additions = new[1+old_cnf:1+old_cnf+4*n]
    expected = []
    f = field.Onb(n)
    for j, pair in enumerate(cell["root_sets"]):
        x, y = [f.fromCoords(v) for v in pair["leaf_x_coords"]]
        assert len(pair["root_x_coords"]) == 2
        for z in pair["root_x_coords"]:
            assert evaluate_s3(f, x, y, f.fromCoords(z)) == 0
        select = pair["selector_variable"]
        assert select == old_vars + j + 1
        for i in range(n):
            bit = 2 + 4*n + j*n + i
            first = bit if pair["root_x_coords"][0] >> i & 1 else -bit
            second = bit if pair["root_x_coords"][1] >> i & 1 else -bit
            expected += [f"{-select} {first} 0", f"{select} {second} 0"]
    assert additions == expected
    return raw


def main():
    frozen = read(HERE / "freeze.json")
    assert frozen["source_sha256"]["audit.py"] == sha(Path(__file__))
    assert frozen["q1419_protocol_sha256"] == sha(Q1419 / "protocol.json")
    rows = []
    for n in (53, 83):
        cell = frozen["cells"][str(n)]
        assert cell["oracle_api_counts"]["s3"] == 2
        raw = verify_formula(n, cell)
        assert hashlib.sha256(raw).hexdigest() == cell[
            "augmented_formula_sha256"]
        receipt = read(HERE / "runs" / f"n{n}.json")
        assert receipt["freeze_sha256"] == sha(HERE / "freeze.json")
        assert receipt["curve_id"] == cell["curve_id"]
        assert receipt["public_target"] == cell["public_target"]
        assert receipt["factor_base_enumerated_set_sha256"] == cell[
            "factor_base_enumerated_set_sha256"]
        out = HERE / "runs" / f"n{n}.stdout.gz"
        err = HERE / "runs" / f"n{n}.stderr.gz"
        assert receipt["stdout_gzip_sha256"] == sha(out)
        assert receipt["stderr_gzip_sha256"] == sha(err)
        stdout = gzip.decompress(out.read_bytes()).decode()
        assert not gzip.decompress(err.read_bytes()).strip()
        assert receipt["status"] == "SAT" and receipt["return_code"] == 10
        model = parsed_model(stdout)
        assert model is not None
        check_serialized_xcnf(raw, model)
        profile, parent, fixture = read_profile(read(Q1419 / "protocol.json"), n)
        _, leaves, _, _, _ = build_balanced(
            n, profile["normal_basis_weight_bound"],
            parent["raw_preimage_x_coordinates"])
        relation = verify_relation(profile, model, leaves)
        assert relation == receipt["relation"]
        assert relation["status"] == "verified_four_point_relation"
        assert relation["raw_leaf_x"] == fixture["fixture"]["raw_leaf_x"]
        rows.append({"field_degree_n": n, "status": "PASS",
                     "conflicts_reported": receipt["conflicts_reported"],
                     "relation_status": relation["status"],
                     "oracle_api_counts": cell["oracle_api_counts"],
                     "added_cnf_clauses": cell["added_cnf_clauses"]})
    path = HERE / "audit.json"
    assert not path.exists()
    path.write_text(json.dumps({
        "schema": "q20261010131600-audit-v1",
        "proposal_id": frozen["proposal_id"], "status": "PASS",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)), "rows": rows,
    }, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "cells": len(rows)}))


if __name__ == "__main__":
    main()
