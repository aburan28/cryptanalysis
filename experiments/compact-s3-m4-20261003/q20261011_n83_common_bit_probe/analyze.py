#!/usr/bin/env python3
"""Compare unset common-root bits with Q1484 on both ordinary points."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1484 = HERE.parent / "q20261011_n83_singleton_support_probe"


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
        prior = json.loads((Q1484 / "runs" / f"{name}_phase4" /
                            "receipt.json").read_text())
        log = (path / "solver.stderr.txt").read_text()
        p_log = (Q1484 / "runs" / f"{name}_phase4" /
                 "solver.stderr.txt").read_text()
        assert receipt["status"] == prior["status"] == "CHECKPOINT_TERMINATED"
        assert receipt["workload_id"] == prior["workload_id"]
        p_work, work = marker(p_log, "Q1473_WORK", cap), marker(log, "Q1473_WORK", cap)
        support = marker(log, "Q1483_SUPPORT", cap)
        prior_support = marker(p_log, "Q1483_SUPPORT", cap)
        singleton = marker(log, "Q1484_SINGLETON", cap)
        prior_singleton = marker(p_log, "Q1484_SINGLETON", cap)
        common = marker(log, "Q1485_COMMON", cap)
        assert work == p_work and support == prior_support
        assert singleton == prior_singleton
        assert len(common) == 6
        _, checks, available, unset_sum, minimum, maximum = common
        assert checks == support[3] == 32720
        assert 0 <= available <= checks
        assert 0 <= minimum <= maximum <= frozen["common_root_bit_count"]
        assert minimum * checks <= unset_sum <= maximum * checks
        points[name] = {
            "workload_id": receipt["workload_id"],
            "status": receipt["status"],
            "baseline_status": prior["status"],
            "combined_cnf_xor_calls_at_cap": work[1] + work[2],
            "baseline_combined_cnf_xor_calls_at_cap": p_work[1] + p_work[2],
            "recognized_pair_states_at_cap": checks,
            "states_with_unset_common_bits_at_cap": available,
            "unset_common_bits_sum_at_cap": unset_sum,
            "unset_common_bits_min_at_cap": minimum,
            "unset_common_bits_max_at_cap": maximum,
            "support_rejections_at_cap": support[4],
            "receipt_sha256": sha(path / "receipt.json"),
            "baseline_receipt_sha256": sha(Q1484 / "runs" /
                                           f"{name}_phase4" / "receipt.json"),
        }
    result = {
        "proposal_id": "Q1485", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "controlled_change": protocol["controlled_change"],
        "common_root_bit_count": frozen["common_root_bit_count"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "analysis_source_sha256": sha(Path(__file__)),
        "points": points,
        "natural_relation_yield": None, "novel_rank_per_query": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    print("Q1485", {n: (p["states_with_unset_common_bits_at_cap"],
                       p["unset_common_bits_min_at_cap"],
                       p["unset_common_bits_max_at_cap"])
                    for n, p in points.items()})


if __name__ == "__main__":
    main()
