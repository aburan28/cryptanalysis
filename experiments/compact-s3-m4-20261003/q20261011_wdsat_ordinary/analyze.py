#!/usr/bin/env python3
"""Summarize ordinary capped searches beside the conditional N131 work model."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    verification_path = HERE / "verification.json"
    verification = json.loads(verification_path.read_text())
    assert verification["status"] == "PASS" and len(verification["runs"]) == 4
    assert {(row["degree"], row["variant"]) for row in verification["runs"]} == {
        (n, variant) for n in (53, 83) for variant in ("plain", "xor_gauss")}
    frozen = json.loads((HERE / "freeze.json").read_text())
    q1462_path = PARENT / "q20261011_n131_pair_budget/analysis.json"
    q1462 = json.loads(q1462_path.read_text())
    assert q1462["proposal_id"] == "Q1462"
    assert q1462["complete_solve_work_log2"] is None
    rows = []
    for row in sorted(verification["runs"], key=lambda r: (r["degree"], r["variant"])):
        degree, variant = row["degree"], row["variant"]
        receipt = json.loads((HERE / "runs" / f"n{degree}" / variant / "receipt.json").read_text())
        assert row["receipt_sha256"] == sha(HERE / "runs" / f"n{degree}" / variant / "receipt.json")
        assert receipt["status"] == row["status"]
        assert receipt["complete_solve_work_log2"] is None
        record = frozen["cells"][f"n{degree}"]
        rows.append({"degree": degree, "variant": variant,
                     "curve_id": record["curve_id"], "workload_id": record["workload_id"],
                     "factor_base_actual_B": record["factor_base_actual_B"],
                     "factor_base_folded_columns_K": record["factor_base_folded_columns_K"],
                     "status": receipt["status"], "search_started": receipt["search_started"],
                     "wall_seconds_exploratory": receipt["wall_seconds_exploratory"],
                     "user_cpu_seconds": receipt["user_cpu_seconds"],
                     "system_cpu_seconds": receipt["system_cpu_seconds"],
                     "maxrss_child_bytes_darwin": receipt["maxrss_child_bytes_darwin"],
                     "verified_natural_relations": receipt["verified_natural_relations"],
                     "complete_solve_work_log2": None,
                     "receipt_sha256": row["receipt_sha256"]})
    output = {"proposal_id": "Q1463", "candidate_id": None,
              "status": "COMPLETE_CAPPED_MEASUREMENT", "runs": rows,
              "verification_sha256": sha(verification_path),
              "freeze_sha256": sha(HERE / "freeze.json"),
              "conditional_n131_reference": {
                  "proposal_id": "Q1462", "analysis_sha256": sha(q1462_path),
                  "curve_id": q1462["curve_id"], "conditional_B": q1462["conditional_B"],
                  "conditional_K": q1462["conditional_K"],
                  "full_table_counted_pair_add_attempts_log2": q1462[
                      "conditional_full_table_counted_pair_add_attempts_log2"],
                  "gap_above_2pow61_pair_add_bits": q1462[
                      "conditional_gap_above_2pow61_pair_add_bits"]},
              "degree131_complete_solve_work_log2": None,
              "degree131_complete_solve_challenge_gap_bits": None,
              "source_sha256": sha(Path(__file__))}
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1463", output["status"], len(rows), "runs")


if __name__ == "__main__":
    main()
