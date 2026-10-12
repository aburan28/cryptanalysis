#!/usr/bin/env python3
"""Freeze the interrupted Q1518 scan without filling missing cells."""
from pathlib import Path
import run

HERE = Path(__file__).resolve().parent


def main():
    partial = run.read(HERE / "scan_result.partial.json")
    rows = partial["rows"]
    assert len(rows) == 16 and partial["proposal_id"] == "Q1518"
    assert sum(x["status"] == "COMPLETE" for x in rows) == 14
    assert sum(x["status"] == "TIMEOUT" for x in rows) == 2
    assert not (HERE / "scan_result.json").exists()
    run.save(HERE / "scan_result.json", {
        "proposal_id": "Q1518", "candidate_id": None, "run_id": None,
        "curve_id": run.read(HERE / "result.json")["curve_id"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "status": "INTERRUPTED_HOST_CONTENTION",
        "interruption": {"signal": "SIGINT", "active_cell": {
            "input": "selected", "pair_index": 6, "signs": [1, 1]},
            "active_cell_receipt": None,
            "completed_or_capped_receipts": 16,
            "remaining_planned_cells_including_active": 24,
            "reason": "host contention; prior native process observed at 6.5 percent CPU and two 30-second wall caps"},
        "scan_protocol_sha256": run.sha(HERE / "scan_protocol.json"),
        "scan_source_sha256": run.sha(HERE / "scan_phase3.py"),
        "partial_sha256": run.sha(HERE / "scan_result.partial.json"),
        "salvage_source_sha256": run.sha(Path(__file__)),
        "rows": rows, "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
