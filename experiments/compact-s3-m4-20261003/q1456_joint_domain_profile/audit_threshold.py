#!/usr/bin/env python3
"""Post-run exact cap-admission counts from Q1456's full state archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from q1455_joint_tail.joint_tail import PartialLeaf, option_count  # noqa: E402

OUTPUT = HERE / "threshold_interpretation.json"
THRESHOLDS = (256, 1024, 4096, 8192, 65536)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol_path = HERE / "protocol.json"
    verification_path = HERE / "verification.json"
    protocol = json.loads(protocol_path.read_text())
    verification = json.loads(verification_path.read_text())
    assert protocol["proposal_id"] == verification["proposal_id"] == "Q1456"
    assert verification["status"] == "pass"
    assert verification["protocol_sha256"] == sha(protocol_path)
    rows = []
    for name in protocol["run_order"]:
        receipt_path = HERE / "runs" / name / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        report = receipt["solver_report"]
        cell = protocol["cells"][name]
        assert receipt["solver_status"] == "censored"
        assert receipt["verified_relation_count"] == 0
        assert report is not None
        pair_counts = []
        for snapshot in report["domain_snapshots"]:
            leaves = [PartialLeaf(int(mask, 16), int(ones, 16))
                      for mask, ones in zip(
                          snapshot["leaf_fixed_mask_onb_hex"],
                          snapshot["leaf_ones_onb_hex"])]
            counts = [option_count(leaf, cell["degree_n"], cell[
                "normal_basis_weight_bound"]) for leaf in leaves]
            pairs = [counts[0] * counts[1], counts[2] * counts[3]]
            assert snapshot["pair_candidate_counts"] == pairs
            pair_counts.append(pairs)
        assert len(pair_counts) == report["unique_partial_states"]
        rows.append({
            "case": name, "degree_n": cell["degree_n"],
            "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "unique_partial_states": len(pair_counts),
            "min_max_pair_candidates": min(map(max, pair_counts)),
            "eligible_unique_states_by_pair_cap": {
                str(cap): sum(max(pairs) <= cap for pairs in pair_counts)
                for cap in THRESHOLDS},
            "receipt_sha256": sha(receipt_path),
        })
    result = {"kind": "q1456_postrun_exact_cap_admission_audit",
              "proposal_id": "Q1456", "candidate_id": None,
              "isogeny": "none", "status": "pass",
              "thresholds": list(THRESHOLDS), "rows": rows,
              "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path),
              "verification_sha256": sha(verification_path),
              "successful_decomposition_cost_measured": False,
              "complete_n131_log2_work": None,
              "challenge_run_admitted": False}
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1456 exact cap-admission audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1456",
                          "cap_4096_admissions": [row[
                              "eligible_unique_states_by_pair_cap"]["4096"]
                              for row in rows]}))


if __name__ == "__main__":
    main()
