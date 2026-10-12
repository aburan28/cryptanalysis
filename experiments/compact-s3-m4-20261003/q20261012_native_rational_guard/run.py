#!/usr/bin/env python3
"""Run the frozen Q1496 N83 pair guard against both ordinary points."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1491 = HERE.parent / "q20261012_n83_mask_density"


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(result)
    return result


def read(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def run() -> None:
    sweep = module(Q1491 / "sweep.py", "q1491_sweep")
    sweep.HERE = HERE
    protocol, frozen, built = map(read, ("protocol.json", "freeze.json",
                                         "build_receipt.json"))
    assert sweep.sha(HERE / "freeze.json") == built["freeze_sha256"]
    assert all(sweep.sha(HERE / name) == digest
               for name, digest in frozen["files_sha256"].items())
    rows = []
    for input_name in ("selected", "holdout"):
        for phase in protocol["phases"]:
            row = sweep.run_cell(input_name, phase, protocol, frozen, built)
            folder = HERE / "runs" / f"{input_name}_phase{phase}"
            log = (folder / "solver.stderr.txt").read_text(errors="replace")
            accepts = re.findall(r"^Q1496_PAIR_ACCEPTED (\d+) (\d+) (\d+)$",
                                 log, re.M)
            caps = re.findall(r"^Q1496_GUARD_FINAL (\d+) (\d+) (\d+) (\d+)$",
                              log, re.M)
            assert len(caps) <= 1
            if row["status"] == "FIRST_PAIR_TERMINATED":
                assert accepts and row["first_pair_bits"] is not None
                checks, rejects, accepted = map(int, accepts[-1])
            elif caps:
                assert row["return_code"] == 43 and row["search_started"]
                assert int(caps[0][0]) == protocol["branch_cap"]
                checks, rejects, accepted = map(int, caps[0][1:])
                row["status"] = "BRANCH_CAP_NO_USABLE_PAIR"
            else:
                checks = rejects = accepted = None
            if checks is not None:
                assert checks == rejects + accepted
                assert accepted >= len(accepts)
            row.update(proposal_id="Q1496", point_decomposition_stage_code="PDP4sat",
                       guard_complete_checks=checks, guard_rejections=rejects,
                       guard_accepted_checks=accepted,
                       guard_accepted_markers=len(accepts),
                       branch_cap=protocol["branch_cap"])
            sweep.save(folder / "receipt.json", row)
            rows.append({"input": input_name, "phase": phase,
                         "receipt_sha256": sweep.sha(folder / "receipt.json")})
            print("Q1496", input_name, phase, row["status"],
                  row["first_pair_combined_calls"], checks, rejects,
                  flush=True)
    sweep.save(HERE / "drive_receipt.json", {
        "proposal_id": "Q1496", "candidate_id": None, "run_id": None,
        "freeze_sha256": sweep.sha(HERE / "freeze.json"),
        "build_receipt_sha256": sweep.sha(HERE / "build_receipt.json"),
        "rows": rows, "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })


if __name__ == "__main__":
    run()
