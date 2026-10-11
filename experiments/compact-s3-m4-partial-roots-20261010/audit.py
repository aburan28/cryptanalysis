#!/usr/bin/env python3
"""Independently audit the frozen partially free S3 root experiment."""

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
Q1419 = ROOT / "experiments/compact-s3-m4-20261003/q1419_partial_pin"
PARENT = Q1419.parent
sys.path[:0] = [str(Q1419), str(PARENT), str(ROOT / "ecc2k130/codegen")]
from chain_s3 import evaluate_s3  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from run_cell import read_profile, verify_relation  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
import field  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def audit_formula(n, name, cell, protocol):
    parent_path = Q1419 / "runs" / f"n{n}_{name}/system.xcnf.gz"
    receipt_path = Q1419 / "runs" / f"n{n}_{name}/receipt.json"
    parent_receipt = load(receipt_path)
    assert digest(receipt_path) == cell["parent_receipt_sha256"]
    assert digest(parent_path) == parent_receipt["formula_archive_sha256"]
    original = gzip.decompress(parent_path.read_bytes())
    assert hashlib.sha256(original).hexdigest() == cell["parent_formula_sha256"]
    archive = HERE / "inputs" / f"n{n}_{name}.xcnf.gz"
    assert digest(archive) == cell["augmented_archive_sha256"]
    augmented = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(augmented).hexdigest() == cell[
        "augmented_formula_sha256"]
    old, new = original.decode("ascii").splitlines(), augmented.decode(
        "ascii").splitlines()
    old_header, new_header = old[0].split(), new[0].split()
    assert old_header[:2] == new_header[:2] == ["p", "cnf"]
    variables, rows = map(int, old_header[2:])
    assert list(map(int, new_header[2:])) == [variables + 1, rows + 2*n]
    assert variables == cell["original_variables"]
    assert rows == cell["original_rows"]
    clauses = parent_receipt["formula"]["cnf_clauses"]
    assert clauses == cell["original_cnf_clauses"]
    assert new[1:1+clauses] == old[1:1+clauses]
    assert new[1+clauses+2*n:] == old[1+clauses:]
    selector = variables + 1
    assert selector == cell["selector_variable"]
    assert cell["added_variables"] == 1 and cell["added_cnf_clauses"] == 2*n

    profile, parent, fixture = read_profile(protocol, n)
    assert cell["curve_id"] == profile["curve_id"]
    assert cell["actual_usable_points_B"] == profile["factor_base_actual_B"]
    assert cell["folded_columns_K"] == profile["folded_columns_K"]
    assert cell["factor_base_enumerated_set_sha256"] == profile[
        "factor_base_enumerated_set_sha256"]
    assert cell["workload_id"] == profile["workload_id"]
    assert cell["public_target"] == profile["public_target"]
    witness = fixture["fixture"]
    assert cell["fixed_pair_leaf_x_coords"] == witness["raw_leaf_x"][:2]
    f = field.Onb(n)
    x, y = (f.fromCoords(coord) for coord in cell["fixed_pair_leaf_x_coords"])
    roots = cell["root_x_coords"]
    assert len(roots) == 2 and len(set(roots)) == 2
    assert int(witness["raw_pair_sum_points"][0][0]) in [
        f.fromCoords(value) for value in roots]
    assert all(evaluate_s3(f, x, y, f.fromCoords(value)) == 0
               for value in roots)
    expected = []
    for i in range(n):
        midpoint = 2 + 4*n + i
        literal0 = midpoint if roots[0] >> i & 1 else -midpoint
        literal1 = midpoint if roots[1] >> i & 1 else -midpoint
        expected.extend((f"{-selector} {literal0} 0",
                         f"{selector} {literal1} 0"))
    assert new[1+clauses:1+clauses+2*n] == expected
    assert cell["oracle_api_counts"]["s3"] == 1
    assert cell["oracle_seconds_exploratory"] >= 0
    assert cell["input_construction_seconds_exploratory"] >= 0
    return profile, parent, augmented


def audit_run(frozen, n, name, setting, profile, parent, formula):
    key = f"n{n}_{name}"
    label = f"{key}_{setting}"
    path = HERE / "runs" / f"{label}.json"
    receipt = load(path)
    assert receipt["proposal_id"] == frozen["proposal_id"]
    assert receipt["candidate_id"] is receipt["run_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["field_degree_n"] == n
    assert receipt["cell"] == name and receipt["setting"] == setting
    assert receipt["curve_id"] == profile["curve_id"]
    assert receipt["formula_sha256"] == frozen["cells"][key][
        "augmented_formula_sha256"]
    assert receipt["solver_sha256"] == frozen["solver_sha256"]
    assert receipt["freeze_sha256"] == digest(HERE / "freeze.json")
    assert receipt["solver_flags"][:8] == ["--verb", "1", "--threads", "1",
                                           "--random", "0", "--maxconfl",
                                           "1000000"]
    if setting == "gauss":
        assert receipt["solver_flags"][8:] == [
            "--maxmatrixcols", "10000" if n == 53 else "25000",
            "--autodisablegauss", "0"]
    else:
        assert len(receipt["solver_flags"]) == 8
    stdout_path = HERE / "runs" / f"{label}.stdout.gz"
    stderr_path = HERE / "runs" / f"{label}.stderr.gz"
    assert digest(stdout_path) == receipt["stdout_gzip_sha256"]
    assert digest(stderr_path) == receipt["stderr_gzip_sha256"]
    stdout = gzip.decompress(stdout_path.read_bytes()).decode(errors="replace")
    stderr = gzip.decompress(stderr_path.read_bytes()).decode(errors="replace")
    matches = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", stdout)
    assert receipt["conflicts_reported"] == (
        int(matches[-1]) if matches else None)
    assert receipt["solver_wall_seconds_exploratory"] >= 0
    assert receipt["peak_child_rss_raw"] >= 0
    assert receipt["child_user_seconds"] >= 0
    assert receipt["child_system_seconds"] >= 0
    assert receipt["decompression_seconds_exploratory"] >= 0
    assert receipt["relation_check_seconds_exploratory"] >= 0
    status = receipt["status"]
    model = parsed_model(stdout)
    if status == "SAT":
        assert receipt["return_code"] == 10
        assert not receipt["external_timeout"] and model is not None
        assert "s SATISFIABLE" in stdout
        stats = check_serialized_xcnf(formula, model)
        assert stats["variables"] == frozen["cells"][key][
            "original_variables"] + 1
        assert stats["cnf_clauses"] == (
            frozen["cells"][key]["original_cnf_clauses"] + 2*n)
        _, leaves, _, _, _ = build_balanced(
            n, profile["normal_basis_weight_bound"],
            parent["raw_preimage_x_coordinates"])
        relation = verify_relation(profile, model, leaves)
        assert relation == receipt["relation"]
        assert relation["status"] == "verified_four_point_relation"
    else:
        assert status == "BOUNDED_UNKNOWN" and model is None
        assert receipt["relation"] is None
        assert receipt["return_code"] != 20
        assert receipt["external_timeout"] or (
            receipt["conflicts_reported"] is not None and
            receipt["conflicts_reported"] >= 1_000_000)
        assert "s UNSATISFIABLE" not in stdout
        assert "ERROR" not in stderr.upper()
    return {
        "label": label, "status": status,
        "conflicts": receipt["conflicts_reported"],
        "solver_wall_seconds_exploratory": receipt[
            "solver_wall_seconds_exploratory"],
        "peak_child_rss_raw": receipt["peak_child_rss_raw"],
        "peak_child_rss_unit": receipt["peak_child_rss_unit"],
        "receipt_sha256": digest(path),
    }


def main():
    frozen = load(HERE / "freeze.json")
    assert frozen["schema"] == "q20261010171000-freeze-v1"
    assert frozen["proposal_id"] == "Q20261010171000"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert frozen["isogeny"] == "none"
    assert frozen["q1419_protocol_sha256"] == digest(Q1419 / "protocol.json")
    q1316 = ROOT / "experiments/compact-s3-m4-external-roots-20261010"
    assert frozen["q1316_oracle_sha256"] == digest(q1316 / "oracle.py")
    assert frozen["q1316_runner_sha256"] == digest(q1316 / "experiment.py")
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    assert frozen["order"] == [[n, cell, setting] for n in (53, 83)
                                for cell in ("three_leaves", "two_same")
                                for setting in ("default", "gauss")]
    assert frozen["max_conflicts"] == 1_000_000
    assert frozen["external_wall_cap_seconds"] == 60
    protocol = load(Q1419 / "protocol.json")
    formulas = {(n, name): audit_formula(n, name,
                frozen["cells"][f"n{n}_{name}"], protocol)
                for n in (53, 83) for name in ("three_leaves", "two_same")}
    rows = [audit_run(frozen, n, name, setting,
                      *formulas[(n, name)]) for n, name, setting
            in frozen["order"]]
    result = {"schema": "q20261010171000-audit-v1", "status": "PASS",
              "freeze_sha256": digest(HERE / "freeze.json"),
              "auditor_sha256": digest(Path(__file__)), "rows": rows,
              "sat_count": sum(row["status"] == "SAT" for row in rows)}
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "rows": len(rows),
                      "sat_count": result["sat_count"]}))


if __name__ == "__main__":
    main()
