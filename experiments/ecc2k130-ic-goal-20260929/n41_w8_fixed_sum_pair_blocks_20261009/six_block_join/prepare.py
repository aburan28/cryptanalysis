#!/usr/bin/env python3
"""Freeze six exact fixed-sum pair lists and the public N41 target."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    geometry_path = PARENT / "geometry.json"
    public_path = PARENT.parent / "n41_adjacent_pairpair/public_target.json"
    geometry = json.loads(geometry_path.read_text())
    public = json.loads(public_path.read_text())
    if (geometry["curve_id"] != "EC1N41Ckb1h7d5e80d3c4d0" or
            geometry["fixed_seed_sum_code"] != 56 or
            geometry["pair_states_per_block"] != 160 or
            len(geometry["blocks"]) != 7 or
            tuple(public["target_q"]) != (1458168294740, 1672312028033)):
        raise ValueError("frozen exact geometry or public target changed")
    lines = [f"{public['target_q'][0]} {public['target_q'][1]} "
             f"{geometry['subgroup_order']} 6"]
    for block in geometry["blocks"][:6]:
        states = block["states"]
        lines.append(str(len(states)))
        for state in states:
            x, y = state["projected_sum"]
            a, b = state["columns"]
            lines.append(f"{x} {y} {a} {b} {state['a']} {state['b']} "
                         f"{state['sign_a']} {state['sign_b']}")
    path = HERE / "input.txt"
    if path.exists():
        raise FileExistsError(path)
    path.write_text("\n".join(lines) + "\n")
    receipt = {"status": "FROZEN_INPUT", "proposal_id": "Q20261009174000",
               "candidate_id": None, "curve_id": geometry["curve_id"],
               "blocks": 6, "signed_states_per_block": 160,
               "input_sha256": digest(path),
               "geometry_sha256": digest(geometry_path),
               "public_target_sha256": digest(public_path),
               "prepare_sha256": digest(__file__),
               "uniform_group_expected_ordered_six_tuples":
                   "16777216000000/549756390943; heuristic only"}
    (HERE / "input_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
