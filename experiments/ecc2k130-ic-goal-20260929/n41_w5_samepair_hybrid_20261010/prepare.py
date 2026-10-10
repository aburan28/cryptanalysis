#!/usr/bin/env python3
"""Freeze the five-repeated-rotation W5 public-point native-join input."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIOR = ROOT / "n41_w5_ten_native_join_20261010"
GEOMETRY = ROOT / "n41_w5_ten_source_gate_20261010" / "geometry_result.json"
CHOICE = (0, 0, 2, 2, 4, 4, 6, 6, 8, 8)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    geometry = json.loads(GEOMETRY.read_text())
    source = (PRIOR / "input.txt").read_text().splitlines()
    assert source[0] == "1458168294740 1672312028033 1496345304064 1421510518509 549756390943 10"
    assert geometry["rotations"] == list(range(0, 40, 4))
    assert geometry["actual_subgroup_factor_base_points_B"] == 340
    assert geometry["folded_columns_K"] == 14
    blocks = []
    cursor = 5
    for _ in range(10):
        assert source[cursor] == "34"
        block = source[cursor:cursor+35]
        assert len(block) == 35
        assert len({tuple(map(int, row.split()[:2])) for row in block[1:]}) == 34
        blocks.append(block)
        cursor += 35
    assert cursor == len(source)
    selected = [blocks[i] for i in CHOICE]
    assert all(selected[2*i] == selected[2*i+1] for i in range(5))
    raw = {tuple(map(int, row.split()[:2])) for block in selected for row in block[1:]}
    assert len(raw) == 170
    assert {int(row.split()[2]) for block in selected for row in block[1:]} == set(range(14))
    payload = source[:5] + [row for block in selected for row in block]
    input_path = HERE / "input.txt"
    input_path.write_text("\n".join(payload) + "\n")
    protocol = {
        "status": "FROZEN_BEFORE_NATIVE_SEARCH",
        "kind": "n41_w5_same_rotation_five_pair_public_join_gate",
        "proposal_id": "Q_N41_W5_SAMEPAIR_HYBRID_GATE",
        "candidate_id": None,
        "curve_id": geometry["curve_id"],
        "public_q": geometry["public_target_q"],
        "subgroup_order_r": geometry["subgroup_order_r"],
        "target_count": 1,
        "summands": 10,
        "source_width": 5,
        "rotation_slots": [geometry["rotations"][i] for i in CHOICE],
        "actual_factor_base_points_B": len(raw),
        "folded_columns_K": 14,
        "source_policy": "each of five selected rotations appears in two leaf slots; all ten folded columns must be distinct",
        "native_method": "frozen exact four-plus-six group join over four raw target preimages",
        "native_seed": 202610102113,
        "right_distinct_probe_cap": 60000000,
        "wall_cap_seconds": 600,
        "rss_cap_bytes": 4294967296,
        "workers": 1,
        "source_sha256": {
            "prepare": digest(Path(__file__)),
            "geometry": digest(GEOMETRY),
            "prior_input": digest(PRIOR / "input.txt"),
            "join_source": digest(PRIOR / "join.cpp"),
            "join_binary": digest(PRIOR / "join"),
            "input": digest(input_path),
        },
    }
    (HERE / "protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"], "B": len(raw), "K": 14,
                      "input_sha256": protocol["source_sha256"]["input"]}))


if __name__ == "__main__":
    main()
