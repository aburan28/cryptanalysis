#!/usr/bin/env python3
"""Replay exact S3 roots and field API work for frozen distinct-pair samples."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1478 = PARENT / "q20261011_n83_leaf_exposure"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent.parent / "ecc2k130/codegen"))
sys.path.insert(0, str(PARENT / "q20261011_operation_account"))
from counted_onb import CountedOnb  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coord(bits: str) -> int:
    assert len(bits) == 83 and set(bits) <= {"0", "1"}
    return int(bits[::-1], 2)


def replay_pair(onb: CountedOnb, bits: str) -> dict:
    assert len(bits) == 166 and set(bits) <= {"0", "1"}
    onb.reset_counts()
    a = onb.fromCoords(coord(bits[:83]))
    b = onb.fromCoords(coord(bits[83:]))
    if not a and not b:
        roots = ()
    elif not a:
        roots = (onb.inv(b),)
    elif not b:
        roots = (onb.inv(a),)
    else:
        roots = s3_roots(onb, a, b)
    root_coordinates = [onb.toCoords(root) for root in roots]
    calls = onb.snapshot_counts()
    return {"leaf0_coords": coord(bits[:83]), "leaf1_coords": coord(bits[83:]),
            "leaf0_weight": bits[:83].count("1"),
            "leaf1_weight": bits[83:].count("1"),
            "root_count": len(root_coordinates),
            "root_coords": root_coordinates,
            "field_api_calls": calls, "field_api_entries": sum(calls.values())}


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert drive["proposal_id"] == protocol["proposal_id"] == "Q1479"
    onb = CountedOnb(83)
    samples = {}
    summary = {}
    for item in drive["rows"]:
        name = item["input"]
        folder = HERE / "runs" / f"{name}_{protocol['branch_order']}"
        row_path = folder / "receipt.json"
        assert sha(row_path) == item["receipt_sha256"]
        row = json.loads(row_path.read_text())
        assert row["status"] == "CHECKPOINT_TERMINATED"
        log_path = folder / "solver.stderr.txt"
        assert sha(log_path) == row["stderr_sha256"]
        log = log_path.read_text()
        found = [(int(i), bits) for i, bits in re.findall(
            r"^Q1479_PAIR1 (\d+) ([01]{166})$", log, re.M)]
        assert [i for i, _ in found] == list(range(1, len(found) + 1))
        assert len({bits for _, bits in found}) == len(found)
        assert 0 < len(found) <= protocol["distinct_pair1_sample_cap_per_point"]
        caps = [tuple(map(int, value)) for value in re.findall(
            r"^Q1479_SUMMARY (\d+) (\d+) (\d+) (\d+)$", log, re.M)]
        summary_at_cap = next(value for value in caps if value[0] == protocol[
            "branch_checkpoint"])
        assert summary_at_cap[1] == len(found)
        ready_at_cap = next(value for value in row["ready_checkpoints"]
                            if value[0] == protocol["branch_checkpoint"])
        assert summary_at_cap[1] + summary_at_cap[2] + summary_at_cap[3] == ready_at_cap[4]
        prior_row = json.loads((Q1478 / "runs" /
                                f"{name}_{protocol['branch_order']}" /
                                "receipt.json").read_text())
        same_ready = row["ready_checkpoints"] == prior_row["ready_checkpoints"]
        same_work = row["work_checkpoints"] == prior_row["work_checkpoints"]
        assert same_ready and same_work
        entries = []
        for index, bits in found:
            replay = replay_pair(onb, bits)
            entries.append({"sample_index": index, "leaf_bits": bits, **replay})
        samples[name] = entries
        distribution = {str(k): sum(x["root_count"] == k for x in entries)
                        for k in (0, 1, 2)}
        total = sum(x["field_api_entries"] for x in entries)
        summary[name] = {
            "workload_id": row["workload_id"],
            "sample_count": len(entries),
            "sample_cap_reached": len(entries) == protocol[
                "distinct_pair1_sample_cap_per_point"],
            "stored_sample_duplicates": summary_at_cap[2],
            "overcap_snapshots_unclassified_uniqueness": summary_at_cap[3],
            "root_count_distribution": distribution,
            "rootless_fraction_of_stored_sample": distribution["0"] / len(entries),
            "total_field_api_entries_stored_sample": total,
            "field_api_entries_per_stored_pair": total / len(entries),
            "ready_snapshots_and_propagation_work_match_q1478":
                same_ready and same_work,
            "q1478_receipt_sha256": sha(Q1478 / "runs" /
                                        f"{name}_{protocol['branch_order']}" /
                                        "receipt.json"),
            "q1479_receipt_sha256": sha(row_path)}
    sample_path = HERE / "root_samples.json"
    sample_path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n")
    result = {"proposal_id": "Q1479", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"],
              "factor_base_actual_B": protocol["factor_base_actual_B"],
              "factor_base_folded_columns_K": protocol[
                  "factor_base_folded_columns_K"],
              "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
              "sample_rule": protocol["sample_rule"],
              "root_work_unit": "CountedOnb public method entries for input coordinate conversion, exact S3 roots, and output coordinate conversion; nested field calls and oracle assertions included",
              "freeze_sha256": sha(HERE / "freeze.json"),
              "drive_sha256": sha(HERE / "drive_receipt.json"),
              "analysis_source_sha256": sha(Path(__file__)),
              "root_samples_sha256": sha(sample_path),
              "points": summary,
              "sample_representativeness": "first distinct pair-1 states in one deterministic branch prefix; no random sampling law",
              "natural_relation_yield": None,
              "novel_rank_per_query": None,
              "complete_n83_decomposition_work_log2": None,
              "complete_n131_solve_work_log2": None,
              "degree131_challenge_gap_bits": None,
              "separate_conditional_n131_pair_index_counted_pair_additions_log2":
                  86.18470212672088,
              "separate_conditional_n131_pair_index_gap_pair_add_bits":
                  25.18470212672088}
    (HERE / "analysis.json").write_text(json.dumps(result, indent=2,
                                                  sort_keys=True) + "\n")
    for name, values in summary.items():
        print(name, values["sample_count"], values["root_count_distribution"],
              values["total_field_api_entries_stored_sample"])


if __name__ == "__main__":
    main()
