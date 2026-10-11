#!/usr/bin/env python3
"""Independent receipt and model audit for the extended ordinary cell."""

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import audit as parent_audit  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    frozen, result = load(HERE / "freeze.json"), load(HERE / "run.json")
    parent, prepared = load(PARENT / "freeze.json"), load(PARENT / "prepare.json")
    assert frozen["schema"] == "q20261010175400-freeze-v1"
    assert frozen["proposal_id"] == result["proposal_id"] == "Q20261010175400"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert result["candidate_id"] is result["run_id"] is None
    assert frozen["isogeny"] == result["isogeny"] == "none"
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_prepare_sha256"] == digest(PARENT / "prepare.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    assert frozen["formula_archive_sha256"] == digest(
        PARENT / "inputs/system.xcnf.gz")
    raw = gzip.decompress((PARENT / "inputs/system.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["formula_sha256"]
    assert frozen["formula_sha256"] == prepared["formula_sha256"]
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    assert frozen["solver_sha256"] == parent["solver_sha256"]
    assert frozen["solver_flags"] == parent["solver_flags"]
    assert frozen["external_wall_cap_seconds"] == 1200
    for key in ("curve_id", "workload_id", "public_target",
                "actual_usable_points_B", "folded_columns_K",
                "formula_sha256", "solver_sha256", "solver_flags"):
        assert result[key] == frozen[key]
    assert result["freeze_sha256"] == digest(HERE / "freeze.json")
    assert result["actual_usable_points_B"] == 151792
    assert result["folded_columns_K"] == 1432
    assert result["workload_id"] == parent["ordinary_workload_id"]
    stdout_path, stderr_path = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    assert digest(stdout_path) == result["stdout_gzip_sha256"]
    assert digest(stderr_path) == result["stderr_gzip_sha256"]
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
        replay = parent_audit.verify_relation(parent, prepared, model)
        assert replay["status"] == result["relation"]["status"]
        assert replay["leaf_t_coords"] == result["relation"]["leaf_t_coords"]
        if replay["status"] == "verified_four_point_relation":
            assert replay["folded_columns"] == result["relation"][
                "folded_columns"]
    elif status == "UNSAT":
        assert result["return_code"] == 20
        assert "s UNSATISFIABLE" in stdout and result["relation"] is None
    else:
        assert status == "BOUNDED_UNKNOWN" and result["relation"] is None
        assert result["external_timeout"] or result[
            "conflicts_reported"] is not None
        assert "c rst" in stdout or "c confl" in stdout
        assert "ERROR" not in stderr.upper()
    output = HERE / "audit.json"
    assert not output.exists()
    output.write_text(json.dumps({"schema": "q20261010175400-audit-v1",
        "status": "PASS", "solver_status": status,
        "relation_status": result["relation"]["status"] if result[
            "relation"] else None,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "solver_status": status,
                      "relation_status": result["relation"]["status"]
                      if result["relation"] else None}))


if __name__ == "__main__":
    main()
