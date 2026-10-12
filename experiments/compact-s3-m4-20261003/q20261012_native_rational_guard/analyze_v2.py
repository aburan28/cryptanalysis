#!/usr/bin/env python3
"""Charge capped Q1496 WDSat calls and preserve the validator correction."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1491 = HERE.parent / "q20261012_n83_mask_density"
Q1494 = HERE.parent / "q20261012_n83_pair_base_audit"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def run() -> None:
    protocol, frozen, drive, result = (load(HERE / n) for n in
                                      ("protocol.json", "freeze.json",
                                       "drive_receipt.json", "result.json"))
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"]
    assert sha(HERE / "drive_receipt.json") == result["drive_receipt_sha256"]
    assert frozen["files_sha256"]["validate.py"] == sha(HERE / "validate.py")
    summary = {}
    for input_name in ("selected", "holdout"):
        rows = []
        for phase in protocol["phases"]:
            folder = HERE / "runs" / f"{input_name}_phase{phase}"
            receipt = folder / "receipt.json"
            entry = next(x for x in drive["rows"] if x["input"] == input_name
                         and x["phase"] == phase)
            assert sha(receipt) == entry["receipt_sha256"]
            row = load(receipt)
            stderr = folder / "solver.stderr.txt"
            assert sha(stderr) == row["stderr_sha256"]
            if row["status"] == "FIRST_PAIR_TERMINATED":
                charged = row["first_pair_combined_calls"]
                assert charged is not None and row["marker_seen"]
            else:
                assert row["status"] == "BRANCH_CAP_NO_USABLE_PAIR"
                matches = re.findall(r"^Q1473_WORK 32768 (\d+) (\d+)$",
                                     stderr.read_text(), re.M)
                assert len(matches) == 1 and row["return_code"] == 43
                charged = sum(map(int, matches[0]))
            checks = row["guard_complete_checks"]
            assert checks is not None
            rows.append({"phase": phase, "status": row["status"],
                         "charged_cnf_xor_calls": charged,
                         "guard_checks": checks,
                         "guard_rejections": row["guard_rejections"],
                         "receipt_sha256": sha(receipt)})
        calls = sum(x["charged_cnf_xor_calls"] for x in rows)
        accepted = sum(x["status"] == "FIRST_PAIR_TERMINATED" for x in rows)
        assert accepted == result["summary"][input_name]["usable_pairs"]
        summary[input_name] = {
            "attempts": len(rows), "usable_pairs": accepted,
            "charged_cnf_xor_calls_all_attempts": calls,
            "charged_calls_per_usable_pair": calls / accepted if accepted else None,
            "charged_calls_per_usable_pair_log2":
                math.log2(calls / accepted) if accepted else None,
            "native_guard_checks": sum(x["guard_checks"] for x in rows),
            "native_guard_field_mul_sqr_upper_bound":
                180 * sum(x["guard_checks"] for x in rows),
            "rows": rows,
        }
    baseline = [load(Q1491 / "runs" / f"selected_phase{i}" / "receipt.json")
                for i in protocol["phases"]]
    assert all(sha(Q1491 / "runs" / f"selected_phase{b['phase']}" /
                   "receipt.json") == frozen[
                       "baseline_selected_receipts_sha256"][str(b["phase"])]
               for b in baseline)
    assert sha(Q1494 / "result.json") == frozen["q1494_result_sha256"]
    baseline_usable = {r["phase"] for r in load(Q1494 / "result.json")["rows"]
                       if r["phase"] in protocol["phases"] and r["both_usable"]}
    assert sum(b["first_pair_combined_calls"] for b in baseline) == 778598
    assert baseline_usable == {41, 45, 48}
    comparison = {
        "baseline_selected_first_pair_calls_all_eight": 778598,
        "baseline_selected_usable_pairs_independently_audited": 3,
        "baseline_calls_per_usable_pair": 778598 / 3,
        "guarded_selected_calls_per_usable_pair":
            summary["selected"]["charged_calls_per_usable_pair"],
        "guarded_to_baseline_calls_per_usable_pair_ratio":
            summary["selected"]["charged_calls_per_usable_pair"] / (778598 / 3),
        "guarded_minus_baseline_log2_bits":
            math.log2(summary["selected"]["charged_calls_per_usable_pair"] /
                      (778598 / 3)),
    }
    save(HERE / "analysis_v2.json", {
        "proposal_id": "Q1496", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_receipt_sha256": sha(HERE / "drive_receipt.json"),
        "result_sha256": sha(HERE / "result.json"),
        "validate_v2_source_sha256": sha(HERE / "validate_v2.py"),
        "analyze_v2_source_sha256": sha(Path(__file__)),
        "validator_v1_status": "FAILED_MISSING_HISTORICAL_HOLDOUT_BASELINE",
        "validator_v2_status": "PASS",
        "field_kernel_bound_note": "Each nonzero leaf inverse uses exactly eight native multiplications and 82 native squarings. A complete guard check tests at most two leaves; zero or overweight leaves and short-circuit rejects reduce the actual count. WDSat CNF/XOR calls and native field operations are distinct units.",
        "summary": summary, "selected_comparison": comparison,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })
    print("PASS Q1496 charged", comparison)


if __name__ == "__main__":
    run()
