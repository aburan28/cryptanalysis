#!/usr/bin/env python3
"""Audit exact S3 roots and compare N83 root-domain branch variants."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1485 = PARENT / "q20261011_n83_common_bit_probe"
Q1479 = PARENT / "q20261011_n83_distinct_roots"
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


def replay_pair(onb: CountedOnb, bits: str) -> dict:
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
    coords = [onb.toCoords(c) for c in roots]
    calls = onb.snapshot_counts()
    return {"leaf_bits": bits, "leaf0_coords": a_coord,
            "leaf1_coords": b_coord, "leaf0_weight": bits[:83].count("1"),
            "leaf1_weight": bits[83:].count("1"), "root_count": len(coords),
            "root_coords": coords, "field_api_calls": calls,
            "field_api_entries": sum(calls.values())}


def main() -> None:
    assert not (HERE / "analysis.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    onb = CountedOnb(83)
    points, samples = {}, {}
    cap = protocol["branch_checkpoint"]
    for item in drive["rows"]:
        name, variant = item["input"], item["variant"]
        key = f"{name}_{variant}"
        folder = HERE / "runs" / key
        row = json.loads((folder / "receipt.json").read_text())
        assert sha(folder / "receipt.json") == item["receipt_sha256"]
        log = (folder / "solver.stderr.txt").read_text()
        work = marker(log, "Q1473_WORK", cap)
        distinct = marker(log, "Q1479_SUMMARY", cap)
        domain = marker(log, "Q1489_ROOT_DOMAIN", cap)
        ready = marker(log, "Q1478_READY", cap)
        found = [(int(i), bits) for i, bits in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        assert [i for i, _ in found] == list(range(1, len(found) + 1))
        assert len({bits for _, bits in found}) == len(found)
        exact = [{"sample_index": i, **replay_pair(onb, bits)}
                 for i, bits in found]
        samples[key] = exact
        if row["status"] == "CHECKPOINT_TERMINATED":
            assert work is not None and distinct is not None
            assert domain is not None and ready is not None
            assert distinct[1] == len(found)
            assert distinct[1] + distinct[2] + distinct[3] == ready[4]
            assert 0 <= domain[4] <= domain[3]
            assert domain[5] <= 83
        prior = json.loads((Q1485 / "runs" / f"{name}_phase4" /
                            "receipt.json").read_text())
        base_work = prior["work_at_cap"]
        assert base_work is not None
        points[key] = {
            "workload_id": row["workload_id"], "status": row["status"],
            "variant": variant, "branch_lower_bound": row["branch_lower_bound"],
            "combined_cnf_xor_calls_at_cap": work[1] + work[2] if work else None,
            "baseline_q1485_combined_calls_at_cap": base_work[1] + base_work[2],
            "distinct_pair1_count_at_cap": distinct[1] if distinct else None,
            "sampled_distinct_pair1_count": len(exact),
            "domain_checks_at_cap": domain[1] if domain else None,
            "domain_bit_tests_at_cap": domain[2] if domain else None,
            "forced_root_literals_at_cap": domain[3] if domain else None,
            "failed_recursive_implications_at_cap": domain[4] if domain else None,
            "max_recursive_depth_at_cap": domain[5] if domain else None,
            "sampled_root_count_distribution": {
                str(k): sum(x["root_count"] == k for x in exact) for k in (0, 1, 2)},
            "sampled_root_field_api_entries": sum(x["field_api_entries"] for x in exact),
            "sample_cap_reached": len(exact) == protocol[
                "distinct_pair1_sample_cap_per_cell"],
            "receipt_sha256": item["receipt_sha256"],
            "baseline_receipt_sha256": frozen["q1485_phase4_receipts_sha256"][name],
        }
    sample_path = HERE / "root_samples.json"
    sample_path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n")
    result = {
        "proposal_id": "Q1489", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
        "controlled_change": protocol["controlled_change"],
        "root_discriminator_bit": frozen["root_discriminator_bit"],
        "root_discriminator_variable": frozen["root_discriminator_variable"],
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
    print("Q1489", {k: (p["status"], p["combined_cnf_xor_calls_at_cap"],
                       p["distinct_pair1_count_at_cap"],
                       p["forced_root_literals_at_cap"])
                    for k, p in points.items()})


if __name__ == "__main__":
    main()
