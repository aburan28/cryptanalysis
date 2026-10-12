#!/usr/bin/env python3
"""Read-only Q1519 source, formula, solver-status and SAT-replay audit."""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q1519_run", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def check():
    p = run.read(HERE / "protocol.json")
    result = run.read(HERE / "result.json")
    assert result["protocol_sha256"] == run.sha(HERE / "protocol.json")
    assert result["source_sha256"] == run.sha(HERE / "run.py")
    assert run.sha(run.FORMULA) == p["formula_sha256"]
    assert run.sha(run.SOURCE) == p["q1513_run_source_sha256"]
    assert run.sha(run.Q1513 / "freeze.json") == p["q1513_freeze_sha256"]
    assert run.sha(Path(p["solver_binary"])) == p["solver_binary_sha256"]
    parent_control = run.read(run.Q1513 / "n53_known_pair_pinned.json")
    unpinned = run.read(run.Q1513 / "n53_known_complement_unpinned.json")
    assert parent_control["status"] == "SAT_VERIFIED"
    assert parent_control["check"]["s3_and_group_relation_checked"]
    assert parent_control["complement_x_coords"] == unpinned["complement_x_coords"]
    assert unpinned["formula_sha256"] == p["formula_sha256"]
    assert unpinned["pin_projected"] == unpinned["pin_raw"] == []
    formula, raw, leaves, onb = run.parent.build(53, unpinned["complement_x_coords"])
    assert len(result["rows"]) == len(p["settings"])
    statuses = {}
    cells = []
    for setting, row in zip(p["settings"], result["rows"]):
        assert row["setting"] == setting
        assert row["formula_sha256"] == p["formula_sha256"]
        assert row["solver_binary_sha256"] == p["solver_binary_sha256"]
        assert row["command"] == [p["solver_binary"], "--maxtime",
                                  str(p["cpu_soft_seconds_per_cell"]),
                                  "--maxconfl", str(p["max_conflicts"]),
                                  "--verb", "1", "--printsol", "1",
                                  *setting["args"], str(run.FORMULA)]
        folder = HERE / "runs" / setting["label"]
        assert run.read(folder / "receipt.json") == row
        assert run.sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        assert run.sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        stdout = (folder / "solver.stdout.txt").read_text(errors="replace")
        exact_conflicts = re.findall(r"^c\s*conflicts\s*:\s*([0-9]+)",
                                     stdout, re.M)
        assert row["exact_conflicts_if_reported"] == (
            int(exact_conflicts[-1]) if exact_conflicts else None)
        if row["status"] == "SAT_VERIFIED":
            assignment = run.parent.parse_assignment(stdout, formula.variables)
            assert assignment is not None
            assert row["check"] == run.parent.verify(
                formula, raw, leaves, onb, unpinned["complement_x_coords"],
                assignment)
        else:
            assert row["check"] is None
            assert row["status"] in ("WALL_CAP", "CPU_CAP", "INDETERMINATE",
                                     "PROCESS_FAILURE")
            if row["status"] == "WALL_CAP":
                assert row["termination_reason"] == "WALL_CAP"
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        cells.append({"setting": setting["label"], "status": row["status"],
                      "exact_conflicts_if_reported": row["exact_conflicts_if_reported"],
                      "child_user_cpu_seconds": row["child_user_cpu_seconds"],
                      "peak_rss_bytes_darwin": row["child_peak_rss_bytes_darwin"]})
    return {"proposal_id": "Q1519", "candidate_id": None,
            "curve_id": p["curve_id"], "isogeny": "none",
            "point_decomposition_stage_code": "PDP4sat",
            "known_positive_unpinned_complement_x": unpinned["complement_x_coords"],
            "settings": cells, "status_counts": statuses,
            "verified_solve_settings": [x["setting"] for x in cells
                                        if x["status"] == "SAT_VERIFIED"],
            "ordinary_relation_yield_status": "NOT_MEASURED_BY_THIS_CONTROL",
            "complete_n53_decomposition_work_log2": None,
            "complete_n131_solve_work_log2": None}


if __name__ == "__main__":
    output = check()
    if sys.argv[1:] == ["--write-analysis"]:
        (HERE / "analysis.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")
    else:
        assert sys.argv[1:] == []
        assert output == run.read(HERE / "analysis.json")
    print("PASS Q1519 fixed-formula SAT control and raw status audit")
