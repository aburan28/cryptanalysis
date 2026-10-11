#!/usr/bin/env python3
"""Audit N83 sorted-leaf XCNF archive, solver stream, and any returned model."""

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path[:0] = [str(PARENT / "q1419_partial_pin"), str(PARENT)]
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    frozen, built, result = [load(HERE / name) for name in
                             ("freeze.json", "build.json", "run.json")]
    parent = load(PARENT / "runs/n83_q1408_ordinary.json")
    assert frozen["schema"] == "q20261010180700-freeze-v1"
    assert (frozen["proposal_id"] == built["proposal_id"] ==
            result["proposal_id"] == "Q20261010180700")
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert result["candidate_id"] is result["run_id"] is None
    assert frozen["isogeny"] == result["isogeny"] == "none"
    assert frozen["parent_run_sha256"] == digest(
        PARENT / "runs/n83_q1408_ordinary.json")
    assert frozen["parent_protocol_sha256"] == digest(
        PARENT / "q1408_balanced_s3_w5_protocol.json")
    assert frozen["coset_sha256"] == digest(
        PARENT / "runs/n83_ordinary_raw_preimages.json")
    assert frozen["base_receipt_sha256"] == digest(
        PARENT / "bases/n83_weight5_full_orbits.json")
    base = load(PARENT / "bases/n83_weight5_full_orbits.json")
    key_path = PARENT / "bases" / base["factor_base"]["point_key_file"]
    assert frozen["base_key_file_sha256"] == digest(key_path)
    assert frozen["factor_base_enumerated_set_sha256"] == digest(key_path)
    assert frozen["ordinary_baseline_sha256"] == digest(
        PARENT / "runs/n83_ordinary_frozen.json")
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    assert frozen["external_wall_cap_seconds"] == 300
    assert frozen["solver_flags"][-2:] == ["--maxconfl", "100000"]
    parent_archive = PARENT / "runs/n83_q1408_ordinary.xcnf.gz"
    assert frozen["parent_formula_archive_sha256"] == digest(parent_archive)
    parent_raw = gzip.decompress(parent_archive.read_bytes())
    assert hashlib.sha256(parent_raw).hexdigest() == frozen[
        "parent_formula_sha256"] == parent["attempts"][0]["xcnf_sha256"]
    assert built["freeze_sha256"] == result["freeze_sha256"] == digest(
        HERE / "freeze.json")
    archive = HERE / "formula.xcnf.gz"
    assert built["formula_archive_sha256"] == digest(archive)
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == built["formula_sha256"]
    old_lines, lines = parent_raw.decode("ascii").splitlines(), raw.decode(
        "ascii").splitlines()
    assert lines[1:len(old_lines)] == old_lines[1:]
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    assert list(map(int, header[2:])) == [built["variables"],
        built["cnf_clauses"] + built["xor_rows"]]
    assert len(lines) == 1 + built["cnf_clauses"] + built["xor_rows"]
    assert built["added_variables"] > 0
    assert built["added_cnf_clauses"] > 0
    assert built["added_xor_rows"] > 0
    assert built["added_and_gates"] > 0
    leaves = [[2 + 83*i + j for j in range(83)] for i in range(4)]
    assert built["leaves"] == leaves
    for key in ("curve_id", "workload_id", "public_target",
                "actual_usable_points_B", "folded_columns_K",
                "solver_sha256", "solver_flags"):
        assert result[key] == frozen[key]
    assert result["actual_usable_points_B"] == 30977592
    assert result["folded_columns_K"] == 186612
    assert result["workload_id"] == "bab50a1e5f66"
    assert result["build_sha256"] == digest(HERE / "build.json")
    assert result["formula_sha256"] == built["formula_sha256"]
    stdout_path, stderr_path = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    assert result["stdout_gzip_sha256"] == digest(stdout_path)
    assert result["stderr_gzip_sha256"] == digest(stderr_path)
    stdout = gzip.decompress(stdout_path.read_bytes()).decode(errors="replace")
    stderr = gzip.decompress(stderr_path.read_bytes()).decode(errors="replace")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", stdout)
    assert result["conflicts_reported"] == (
        int(conflicts[-1]) if conflicts else None)
    assert result["solver_wall_seconds_exploratory"] >= 0
    assert result["child_user_seconds"] >= 0
    assert result["child_system_seconds"] >= 0
    assert result["peak_child_rss_raw"] > 0
    assert result["relation_check_seconds_exploratory"] >= 0
    status = result["solver_status"]
    if status == "SAT":
        assert result["return_code"] == 10 and not result["external_timeout"]
        model = parsed_model(stdout)
        assert model is not None
        check_serialized_xcnf(raw, model)
        values = [sum(1 << i for i, lit in enumerate(vector) if model[lit])
                  for vector in leaves]
        assert values == sorted(values)
        assert result["model_replay"]["leaf_x_coords"] == values
    elif status == "UNSAT":
        assert result["return_code"] == 20
        assert "s UNSATISFIABLE" in stdout and result["model_replay"] is None
    else:
        assert status == "BOUNDED_UNKNOWN" and result["model_replay"] is None
        assert result["external_timeout"] or result[
            "conflicts_reported"] is not None
        assert "c rst" in stdout or "c confl" in stdout
        assert "ERROR" not in stderr.upper()
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010180700-audit-v1",
        "status": "PASS", "solver_status": status,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "build_sha256": digest(HERE / "build.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "solver_status": status}))


if __name__ == "__main__":
    main()
