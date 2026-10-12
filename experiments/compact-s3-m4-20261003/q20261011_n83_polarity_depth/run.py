#!/usr/bin/env python3
"""Replay Q1474's exact probe at a deeper frozen N83 branch checkpoint."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1473 = PARENT / "q20261011_selector_polarity"
Q1474 = PARENT / "q20261011_n83_propagation_probe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_probe():
    spec = importlib.util.spec_from_file_location("q1474_run_for_q1475", Q1474 / "run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = HERE
    return module


def main() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert sha(Q1474 / "run.py") == frozen["q1474_runner_sha256"]
    assert sha(Q1474 / "analysis.json") == frozen["q1474_analysis_sha256"]
    assert sha(Path(frozen["binary_path"])) == frozen["binary_sha256"]
    assert sha(Q1473 / "smoke_receipt.json") == frozen["q1473_smoke_sha256"]
    assert sha(Q1473 / "target.json") == frozen["q1473_target_sha256"]
    cell = frozen["ordinary_cell"]
    data = {}
    for kind in ("derived", "source"):
        archive = Path(cell[f"{kind}_archive_path"])
        assert sha(archive) == cell[f"{kind}_archive_sha256"]
        data[kind] = gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(data[kind]).hexdigest() == cell[f"{kind}_raw_sha256"]
    target = json.loads((Q1473 / "target.json").read_text())
    probe = load_probe()
    rows = []
    for phase in protocol["phase_order"]:
        child = probe.run_one(phase, protocol, frozen, data["derived"],
                              data["source"], target)
        folder = HERE / "runs" / f"phase{phase}"
        (folder / "receipt.json").rename(folder / "implementation_receipt.json")
        out = {"proposal_id": "Q1475", "implementation_proposal_id": "Q1474",
               "candidate_id": None, "run_id": None,
               "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
               "isogeny": "none", "factor_base_actual_B": protocol["factor_base_actual_B"],
               "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
               "phase": phase, "flip_ids": child["flip_ids"],
               "status": child["status"], "branch_lower_bound": child["branch_lower_bound"],
               "cnf_set_true_calls_at_checkpoint": child[
                   "cnf_set_true_calls_at_checkpoint"],
               "xor_set_true_calls_at_checkpoint": child[
                   "xor_set_true_calls_at_checkpoint"],
               "solver_wall_seconds_exploratory": child[
                   "solver_wall_seconds_exploratory"],
               "user_cpu_seconds": child["user_cpu_seconds"],
               "verified_natural_relations": child["verified_natural_relations"],
               "implementation_receipt_sha256": sha(folder / "implementation_receipt.json"),
               "freeze_sha256": sha(HERE / "freeze.json"),
               "wrapper_source_sha256": sha(Path(__file__)),
               "complete_n83_decomposition_work_log2": None,
               "complete_n131_solve_work_log2": None}
        (folder / "receipt.json").write_text(json.dumps(out, indent=2,
                                                       sort_keys=True) + "\n")
        rows.append(out)
        print("Q1475", phase, out["status"], out["branch_lower_bound"], flush=True)
        if out["status"] != "CHECKPOINT_TERMINATED":
            break
    result = {"proposal_id": "Q1475", "candidate_id": None, "run_id": None,
              "status": "COMPLETE_SCHEDULE" if len(rows) == len(protocol["phase_order"])
              else "STOPPED_AT_GATE", "phase_statuses": [row["status"] for row in rows],
              "new_ordinary_attempts": len(rows),
              "new_ordinary_wall_seconds_exploratory": sum(
                  row["solver_wall_seconds_exploratory"] for row in rows),
              "new_ordinary_user_cpu_seconds": sum(row["user_cpu_seconds"] for row in rows),
              "new_verified_relations": sum(row["verified_natural_relations"] for row in rows),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None,
              "degree131_challenge_gap_bits": None}
    (HERE / "drive_receipt.json").write_text(json.dumps(result, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
