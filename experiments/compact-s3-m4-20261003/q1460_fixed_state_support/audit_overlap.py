#!/usr/bin/env python3
"""Compare exact N83 midpoint sets for Q1459's new and old admissions."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, options  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

PROTOCOL = HERE / "overlap_protocol.json"
OUTPUT = HERE / "overlap_result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def midpoint_digest(values: set[int], n: int) -> str:
    width = (n + 7) // 8
    return hashlib.sha256(b"".join(x.to_bytes(width, "big")
                                    for x in sorted(values))).hexdigest()


def make_result() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1460"
    assert protocol["post_result_follow_up"] is True
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    parent = json.loads((HERE / "result.json").read_text())
    onb = field.Onb(83)
    rows = []
    sets = []
    for state, mode in protocol["selected_state_modes"]:
        row = next(item for item in parent["rows"]
                   if item["cell"] == protocol["case"] and
                   item["state_index"] == state and item["mode"] == mode)
        domains = []
        for fixed, ones in zip(row["leaf_fixed_mask_onb_hex"],
                               row["leaf_ones_onb_hex"]):
            values = options(PartialLeaf(int(fixed, 16), int(ones, 16)),
                             83, row["weight"])
            if mode == "lift":
                values = tuple(x for x in values if
                               onb.trace(onb.add(
                                   onb.fromCoords(x),
                                   onb.inv(onb.fromCoords(x)))) == 0)
            domains.append(values)
        assert [len(domain) for domain in domains] == row["leaf_counts"]
        midpoint_sets = []
        root_values = []
        for side in (0, 2):
            mids = set()
            count = 0
            for a, b in itertools.product(domains[side], domains[side + 1]):
                roots = s3_roots(onb, onb.fromCoords(a), onb.fromCoords(b))
                count += len(roots)
                mids.update(onb.toCoords(root) for root in roots)
            midpoint_sets.append(mids)
            root_values.append(count)
        assert [len(s) for s in midpoint_sets] == row[
            "midpoint_cardinalities"]
        assert root_values == row["pair_root_values"]
        sets.append(midpoint_sets)
        rows.append({
            "state_index": state, "mode": mode,
            "pair_candidates": row["pair_candidates"],
            "pair_root_values": root_values,
            "midpoint_cardinalities": [len(s) for s in midpoint_sets],
            "midpoint_sha256": [midpoint_digest(s, 83)
                                for s in midpoint_sets],
            "target_x_support_upper_bound": row[
                "target_x_support_upper_bound"],
        })
    equal = [all(sets[0][side] == item[side] for item in sets[1:])
             for side in (0, 1)]
    return {
        "kind": "q1460_post_result_n83_midpoint_overlap_audit",
        "proposal_id": "Q1460", "candidate_id": None,
        "isogeny": "none", "post_result_follow_up": True,
        "protocol_sha256": sha(PROTOCOL),
        "parent_result_sha256": sha(HERE / "result.json"),
        "case": protocol["case"],
        "rows": rows,
        "exact_midpoint_sets_equal_by_pair": equal,
        "new_n83_admission_adds_midpoint_x": not all(equal),
        "identical_final_s3_target_x_support_if_both_sets_equal": all(equal),
        "successful_decomposition_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_result()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1460 post-result N83 midpoint overlap: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"equal_by_pair": result[
            "exact_midpoint_sets_equal_by_pair"],
            "new_admission_adds_midpoint_x": result[
                "new_n83_admission_adds_midpoint_x"]}))


if __name__ == "__main__":
    main()
