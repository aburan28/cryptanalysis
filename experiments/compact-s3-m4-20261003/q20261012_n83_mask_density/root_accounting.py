#!/usr/bin/env python3
"""Charge exact S3 root-replay API work for every Q1491 first pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sweep

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    protocol = load(HERE / "protocol.json")
    drive = load(HERE / "drive_receipt.json")
    assert drive["proposal_id"] == protocol["proposal_id"] == "Q1491"
    rows = []
    for item in drive["rows"]:
        path = HERE / "runs" / f"{item['input']}_phase{item['phase']}" / "receipt.json"
        assert sha(path) == item["receipt_sha256"]
        row = load(path)
        assert row["status"] == "FIRST_PAIR_TERMINATED"
        replay = sweep.replay(row)
        rows.append({"input": item["input"], "phase": item["phase"],
                     "flip_count": row["flip_count"],
                     "workload_id": row["workload_id"],
                     "first_pair_cnf_xor_calls": row["first_pair_combined_calls"],
                     "root_count": replay["root_count"],
                     "root_field_api_calls": replay["field_api_calls"],
                     "root_field_api_entries": replay["field_api_entries"],
                     "receipt_sha256": sha(path)})
    summary = {}
    for input_name in ("selected", "holdout"):
        for count in protocol["flip_counts"]:
            sub = [r for r in rows if r["input"] == input_name and
                   r["flip_count"] == count]
            if not sub:
                continue
            key = f"{input_name}_{count}"
            api = sum(r["root_field_api_entries"] for r in sub)
            rootful = sum(r["root_count"] == 2 for r in sub)
            summary[key] = {
                "attempts": len(sub), "two_root_pairs": rootful,
                "cnf_xor_calls": sum(r["first_pair_cnf_xor_calls"] for r in sub),
                "root_field_api_entries": api,
                "root_field_api_entries_per_two_root_pair":
                    api / rootful if rootful else None,
            }
    result = {
        "proposal_id": "Q1491", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol[
            "factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "unit_boundary": "Combined WDSat CNF/XOR calls through first pair and separate CountedOnb public field API entries for conversion and exact S3 replay; units are not added or calibrated to one another.",
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "source_sha256": sha(Path(__file__)),
        "rows": rows, "summary": summary,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    sweep.save(HERE / "root_work.json", result)
    print("Q1491 root work", summary)


if __name__ == "__main__":
    main()
