#!/usr/bin/env python3
"""Summarize the matched four-leaf Q1424 solver grid without fitting yield."""

import gzip
import hashlib
import json
from pathlib import Path
import re

from run import CASE, HERE, OLD, N83_VARIANTS, VARIANTS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    verification = json.loads((HERE / "verification.json").read_text())
    assert verification["status"] == "PASS" and len(verification["rows"]) == 12
    cases = {}
    for n, case in CASE.items():
        rows = []
        for variant in VARIANTS if n == 53 else N83_VARIANTS:
            path = HERE / f"n{n}_{variant}.json"
            receipt = json.loads(path.read_text())
            result = receipt["ordinary"]
            output_path = HERE / result["logs"]["stdout"]["path"]
            log = gzip.decompress(output_path.read_bytes()).decode(errors="replace")
            used = re.findall(r"Using (\d+) matrices", log)
            too_wide = re.findall(r"Too many columns in matrix: (\d+)", log)
            rows.append({
                "variant": variant, "flags": VARIANTS[variant],
                "control_status": receipt["control"]["status"],
                "ordinary_status": result["status"],
                "conflicts": result["conflicts"],
                "decisions": result["decisions"],
                "solver_wall_seconds_exploratory": result["wall_seconds"],
                "sampled_peak_rss_bytes": result["sampled_peak_rss_bytes"],
                "final_reported_active_gauss_matrices": (int(used[-1]) if used else None),
                "largest_rejected_gauss_matrix_columns": (
                    max(map(int, too_wide)) if too_wide else None),
                "verified_natural_relations": receipt["verified_natural_relation_count"],
                "receipt_sha256": sha(path),
            })
        assert all(row["control_status"] == "SAT" for row in rows)
        assert all(row["ordinary_status"] == "BOUNDED_UNKNOWN" for row in rows)
        assert all(row["verified_natural_relations"] == 0 for row in rows)
        cases[str(n)] = {"curve_id": case["curve_id"],
                         "workload_id": case["workload_id"],
                         "B": case["B"], "K": case["K"],
                         "base_digest": case["base_digest"],
                         "same_formula_and_public_target": True,
                         "rows": rows}
    pair_path = OLD / "runs/n53_ordinary_matched_pair_table.json"
    pair = json.loads(pair_path.read_text())
    assert pair["verified_relation_count"] == 1
    assert pair["curve_id"] == CASE[53]["curve_id"]
    assert pair["workload_id"] == CASE[53]["workload_id"]
    assert pair["factor_base_enumerated_set_sha256"] == CASE[53]["base_digest"]
    result = {
        "schema": "q1424-four-leaf-solver-grid-analysis-v1",
        "proposal_id": "Q1424", "candidate_id": None, "isogeny": "none",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "verification_sha256": sha(HERE / "verification.json"),
        "cases": cases,
        "n53_matched_pair_table_reference": {
            "receipt_sha256": sha(pair_path),
            "verified_relation_count": pair["verified_relation_count"],
            "comparison_scope": "same curve, base, and public target; different solver and resource envelope",
        },
        "natural_relation_yield_estimate": None,
        "n131_complete_cold_work_log2": None,
        "n131_complete_online_one_target_work_log2": None,
        "decision": "No variant produced a relation within its 200000-conflict bound; do not fit a solve-cost exponent from capped searches.",
    }
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "n53": len(cases["53"]["rows"]),
                      "n83": len(cases["83"]["rows"]),
                      "ordinary_verified_relations": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
