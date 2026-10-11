#!/usr/bin/env python3
"""Audit the one-million-conflict N83 sorted-leaf solver receipt."""

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parent
sys.path[:0] = [str(ROOT / "q1419_partial_pin"), str(ROOT)]
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    frozen, result = load(HERE / "freeze.json"), load(HERE / "run.json")
    parent, built = load(PARENT / "freeze.json"), load(PARENT / "build.json")
    assert frozen["schema"] == "q20261010181200-freeze-v1"
    assert frozen["proposal_id"] == result["proposal_id"] == "Q20261010181200"
    assert frozen["candidate_id"] is frozen["run_id"] is None
    assert result["candidate_id"] is result["run_id"] is None
    assert frozen["isogeny"] == result["isogeny"] == "none"
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_build_sha256"] == digest(PARENT / "build.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    assert frozen["solver_sha256"] == parent["solver_sha256"]
    assert frozen["solver_flags"][-2:] == ["--maxconfl", "1000000"]
    assert frozen["external_wall_cap_seconds"] == 600
    archive = PARENT / "formula.xcnf.gz"
    assert frozen["formula_archive_sha256"] == digest(archive)
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen[
        "formula_sha256"] == built["formula_sha256"]
    for key in ("curve_id", "workload_id", "public_target",
                "actual_usable_points_B", "folded_columns_K",
                "formula_sha256", "solver_sha256", "solver_flags"):
        assert result[key] == frozen[key]
    assert result["freeze_sha256"] == digest(HERE / "freeze.json")
    assert result["actual_usable_points_B"] == 30977592
    assert result["folded_columns_K"] == 186612
    assert result["workload_id"] == "bab50a1e5f66"
    out_path, err_path = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    assert digest(out_path) == result["stdout_gzip_sha256"]
    assert digest(err_path) == result["stderr_gzip_sha256"]
    stdout = gzip.decompress(out_path.read_bytes()).decode(errors="replace")
    stderr = gzip.decompress(err_path.read_bytes()).decode(errors="replace")
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
        leaves = built["leaves"]
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
    output.write_text(json.dumps({"schema": "q20261010181200-audit-v1",
        "status": "PASS", "solver_status": status,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "run_sha256": digest(HERE / "run.json"),
        "auditor_sha256": digest(Path(__file__))},
        sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "solver_status": status}))


if __name__ == "__main__":
    main()
