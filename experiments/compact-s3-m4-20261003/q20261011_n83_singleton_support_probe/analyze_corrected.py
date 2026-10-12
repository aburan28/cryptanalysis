#!/usr/bin/env python3
"""Post-run correction: include the zero-singleton sentinel in analysis."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1483 = HERE.parent / "q20261011_n83_two_root_support"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marker(log: str, label: str, count: int) -> tuple[int, ...]:
    found = [tuple(map(int, m.split())) for m in re.findall(
        rf"^{label} ({count} [0-9 ]+)$", log, re.M)]
    assert len(found) == 1, (label, found)
    return found[0]


def main() -> None:
    assert not (HERE / "analysis.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    cap = protocol["branch_checkpoint"]
    points = {}
    for name in ("selected", "holdout"):
        path = HERE / "runs" / f"{name}_phase4"
        receipt = json.loads((path / "receipt.json").read_text())
        prior = json.loads((Q1483 / "runs" / f"{name}_phase4" /
                            "receipt.json").read_text())
        log = (path / "solver.stderr.txt").read_text()
        p_log = (Q1483 / "runs" / f"{name}_phase4" /
                 "solver.stderr.txt").read_text()
        assert receipt["status"] == prior["status"] == "CHECKPOINT_TERMINATED"
        assert receipt["workload_id"] == prior["workload_id"]
        p_work, work = marker(p_log, "Q1473_WORK", cap), marker(log, "Q1473_WORK", cap)
        support = marker(log, "Q1483_SUPPORT", cap)
        prior_support = marker(p_log, "Q1483_SUPPORT", cap)
        singleton = marker(log, "Q1484_SINGLETON", cap)
        assert work == p_work and support == prior_support
        assert len(singleton) == 7 and len(support) == 5
        _, both, one, one_undefined, undefined_sum, minimum, maximum = singleton
        assert both + one == support[3]
        assert 0 <= one_undefined <= one
        if one == 0:
            assert (one_undefined, undefined_sum, minimum, maximum) == (0, 0, 83, 0)
        else:
            assert 0 <= minimum <= maximum <= 83
        assert 0 <= undefined_sum <= one * 83
        points[name] = {
            "workload_id": receipt["workload_id"],
            "status": receipt["status"],
            "baseline_status": prior["status"],
            "combined_cnf_xor_calls_at_cap": work[1] + work[2],
            "baseline_combined_cnf_xor_calls_at_cap": p_work[1] + p_work[2],
            "support_pair_matches_at_cap": support[3],
            "both_roots_compatible_at_cap": both,
            "exactly_one_root_compatible_at_cap": one,
            "singleton_with_undefined_middle_bits_at_cap": one_undefined,
            "singleton_undefined_middle_bits_sum_at_cap": undefined_sum,
            "singleton_undefined_middle_bits_min_at_cap": minimum,
            "singleton_undefined_middle_bits_max_at_cap": maximum,
            "support_rejections_at_cap": support[4],
            "receipt_sha256": sha(path / "receipt.json"),
            "baseline_receipt_sha256": sha(Q1483 / "runs" /
                                           f"{name}_phase4" / "receipt.json"),
        }
    result = {
        "proposal_id": "Q1484", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "controlled_change": protocol["controlled_change"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "analysis_source_sha256": sha(Path(__file__)),
        "analysis_correction": {
            "frozen_analyzer_sha256": frozen["files_sha256"]["analyze.py"],
            "frozen_analyzer_status": "POSTPROCESS_ASSERTION_FAILED_ZERO_SINGLETON",
            "change": "Accept (minimum=83, maximum=0) as the unused sentinel when no singleton observation occurred.",
        },
        "points": points,
        "natural_relation_yield": None, "novel_rank_per_query": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    print("Q1484", {n: (p["both_roots_compatible_at_cap"],
                       p["exactly_one_root_compatible_at_cap"],
                       p["singleton_with_undefined_middle_bits_at_cap"])
                    for n, p in points.items()})


if __name__ == "__main__":
    main()
