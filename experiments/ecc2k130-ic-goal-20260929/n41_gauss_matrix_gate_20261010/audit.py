#!/usr/bin/env python3
"""Read-only audit of the frozen N41 Gaussian-size control panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_upper_xor_projection_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case(name, protocol):
    folder = HERE / name
    result_path = folder / "result.json"
    result = json.loads(result_path.read_text())
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    formula = SOURCE / "all_fixed/projected.xcnf"
    assert result["case"] == name and result["mode"] == "all_fixed"
    assert result["status"] == "CENSORED_TIME"
    assert result["stop_reason"] == "WALL_CAP"
    assert result["model_lines"] == 0 and result["solver_status_lines"] == []
    assert result["solver_exit_code"] == -15
    assert result["parent_wall_ns"] >= 20 * 10**9
    assert result["sampled_solver_peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert result["command"][1:-2] == protocol["flags"][name]
    for key, path in {
        "runner": HERE / "run.py",
        "protocol": HERE / "protocol.json",
        "formula": formula,
        "solver": Path("/opt/homebrew/bin/cryptominisat5"),
        "stdout": stdout,
        "stderr": stderr,
    }.items():
        assert result["source_sha256"][key] == sha(path), (name, key)
    output = stdout.read_text()
    assert result["matrix_counts"][0] == (1 if name == "baseline_all_fixed" else 5)
    assert result["too_large_matrix_messages"] == 0
    assert "s SATISFIABLE" not in output and "s UNSATISFIABLE" not in output
    return {
        "status": result["status"],
        "first_accepted_gaussian_matrices": result["matrix_counts"][0],
        "accepted_gaussian_matrices_at_reinitializations":
            result["matrix_counts"],
        "raw_too_many_columns_messages":
            output.count("Too many columns in matrix"),
        "raw_too_many_rows_messages": output.count("Too many rows in matrix"),
        "logged_restarts": sum(line.startswith("c rst")
                               for line in output.splitlines()),
        "parent_wall_ns": result["parent_wall_ns"],
        "sampled_solver_peak_rss_bytes":
            result["sampled_solver_peak_rss_bytes"],
        "source_sha256": {
            "receipt": sha(result_path),
            "stdout": sha(stdout),
            "stderr": sha(stderr),
        },
    }


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_N41_GAUSSIAN_MATRIX_GATE"
    for name, path in {
        "runner": HERE / "run.py",
        "all_fixed_formula": SOURCE / "all_fixed/projected.xcnf",
        "public_formula": SOURCE / "public/projected.xcnf",
        "solver": Path("/opt/homebrew/bin/cryptominisat5"),
    }.items():
        assert protocol["source_sha256"][name] == sha(path), name
    controls = {name: case(name, protocol)
                for name in ("baseline_all_fixed", "gauss_all_fixed")}
    assert controls["baseline_all_fixed"][
        "raw_too_many_columns_messages"] > 0
    assert controls["gauss_all_fixed"][
        "raw_too_many_columns_messages"] == 0
    report = {
        "status": "PASS_FROZEN_N41_MATRIX_PANEL_AUDIT",
        "candidate_id": None,
        "target_count": 1,
        "controls": controls,
        "unpinned_public_query": "SKIPPED_POSITIVE_CONTROL_CENSORED",
        "instrumentation_note": (
            "The frozen runner's too_large_matrix_messages field searched "
            "for 'rows|cols', while CryptoMiniSat printed 'columns'. The "
            "raw log counts above are authoritative."
        ),
        "source_sha256": {
            "script": sha(Path(__file__)),
            "protocol": sha(HERE / "protocol.json"),
        },
    }
    with (HERE / "audit.json").open("x") as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": report["status"],
                      "baseline_matrices": controls["baseline_all_fixed"][
                          "first_accepted_gaussian_matrices"],
                      "gauss_matrices": controls["gauss_all_fixed"][
                          "first_accepted_gaussian_matrices"],
                      "public_query": report["unpinned_public_query"]}))


if __name__ == "__main__":
    main()
