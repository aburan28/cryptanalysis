#!/usr/bin/env python3
"""Audit exact roots and compare propagation work with Q1485."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1485 = PARENT / "q20261011_n83_common_bit_probe"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent.parent / "ecc2k130/codegen"))
sys.path.insert(0, str(PARENT / "q20261011_operation_account"))
from counted_onb import CountedOnb  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marker(log: str, label: str, count: int) -> tuple[int, ...] | None:
    found = [tuple(map(int, m.split())) for m in re.findall(
        rf"^{label} ({count} [0-9 ]+)$", log, re.M)]
    assert len(found) <= 1, (label, found)
    return found[0] if found else None


def exact_roots(onb: CountedOnb, bits: str) -> dict:
    assert len(bits) == 166 and set(bits) <= {"0", "1"}
    onb.reset_counts()
    a_coord, b_coord = int(bits[:83][::-1], 2), int(bits[83:][::-1], 2)
    a, b = onb.fromCoords(a_coord), onb.fromCoords(b_coord)
    if not a and not b:
        roots = ()
    elif not a:
        roots = (onb.inv(b),)
    elif not b:
        roots = (onb.inv(a),)
    else:
        roots = s3_roots(onb, a, b)
    root_coords = [onb.toCoords(value) for value in roots]
    counts = onb.snapshot_counts()
    return {"leaf_bits": bits, "leaf0_coords": a_coord,
            "leaf1_coords": b_coord, "leaf0_weight": bits[:83].count("1"),
            "leaf1_weight": bits[83:].count("1"),
            "root_count": len(root_coords), "root_coords": root_coords,
            "field_api_calls": counts, "field_api_entries": sum(counts.values())}


def main() -> None:
    assert not (HERE / "analysis.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    cap = protocol["branch_checkpoint"]
    onb = CountedOnb(83)
    points, samples = {}, {}
    for name in ("selected", "holdout"):
        path = HERE / "runs" / f"{name}_phase4"
        receipt = json.loads((path / "receipt.json").read_text())
        prior = json.loads((Q1485 / "runs" / f"{name}_phase4" /
                            "receipt.json").read_text())
        log = (path / "solver.stderr.txt").read_text()
        p_log = (Q1485 / "runs" / f"{name}_phase4" /
                 "solver.stderr.txt").read_text()
        assert receipt["workload_id"] == prior["workload_id"]
        p_work = marker(p_log, "Q1473_WORK", cap)
        work = marker(log, "Q1473_WORK", cap)
        propagation = marker(log, "Q1486_PROPAGATE", cap)
        distinct = marker(log, "Q1479_SUMMARY", cap)
        ready = marker(log, "Q1478_READY", cap)
        found = [(int(i), bits) for i, bits in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        assert [i for i, _ in found] == list(range(1, len(found) + 1))
        assert len({bits for _, bits in found}) == len(found)
        assert len(found) <= protocol["distinct_pair1_sample_cap_per_cell"]
        exact = [{"sample_index": i, **exact_roots(onb, bits)}
                 for i, bits in found]
        samples[name] = exact
        if work is not None:
            assert receipt["status"] == "CHECKPOINT_TERMINATED"
            assert propagation is not None and distinct is not None and ready is not None
            assert distinct[1] == len(found)
            assert distinct[1] + distinct[2] + distinct[3] == ready[4]
            assert len(propagation) == 6
            assert 0 <= propagation[4] <= propagation[3]
            assert propagation[5] <= frozen["common_root_bit_count"]
        points[name] = {
            "workload_id": receipt["workload_id"], "status": receipt["status"],
            "baseline_status": prior["status"],
            "branch_lower_bound": receipt["branch_lower_bound"],
            "combined_cnf_xor_calls_at_cap": work[1] + work[2] if work else None,
            "baseline_combined_cnf_xor_calls_at_cap": p_work[1] + p_work[2],
            "distinct_pair1_count_at_cap": distinct[1] if distinct else None,
            "baseline_distinct_pair1_count_at_cap": prior["sampled_pair1_count"],
            "propagation_checks_at_cap": propagation[1] if propagation else None,
            "propagation_bit_tests_at_cap": propagation[2] if propagation else None,
            "forced_literals_at_cap": propagation[3] if propagation else None,
            "failed_recursive_implications_at_cap": propagation[4] if propagation else None,
            "max_recursive_depth_at_cap": propagation[5] if propagation else None,
            "sampled_root_count_distribution": {
                str(k): sum(x["root_count"] == k for x in exact) for k in (0, 1, 2)},
            "sampled_root_field_api_entries": sum(x["field_api_entries"] for x in exact),
            "sample_cap_reached": len(exact) == protocol[
                "distinct_pair1_sample_cap_per_cell"],
            "receipt_sha256": sha(path / "receipt.json"),
            "baseline_receipt_sha256": sha(Q1485 / "runs" /
                                           f"{name}_phase4" / "receipt.json"),
        }
    sample_path = HERE / "root_samples.json"
    sample_path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n")
    result = {
        "proposal_id": "Q1486", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "controlled_change": protocol["controlled_change"],
        "common_root_bit_count": frozen["common_root_bit_count"],
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_sha256": sha(HERE / "drive_receipt.json"),
        "root_samples_sha256": sha(sample_path),
        "analysis_source_sha256": sha(Path(__file__)),
        "points": points, "natural_relation_yield": None,
        "novel_rank_per_query": None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    print("Q1486", {n: (p["status"], p["combined_cnf_xor_calls_at_cap"],
                       p["distinct_pair1_count_at_cap"],
                       p["forced_literals_at_cap"]) for n, p in points.items()})


if __name__ == "__main__":
    main()
