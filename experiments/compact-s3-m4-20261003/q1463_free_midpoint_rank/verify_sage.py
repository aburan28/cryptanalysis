#!/usr/bin/env python3
"""Independently replay two exact midpoint sets and their affine ranks."""

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, options  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402

OUTPUT = HERE / "verification.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def affine_rank(values):
    origin = next(iter(values))
    pivots = {}
    for raw in values:
        value = raw ^ origin
        while value:
            bit = value.bit_length() - 1
            if bit in pivots:
                value ^= pivots[bit]
            else:
                pivots[bit] = value
                break
    return len(pivots)


def replay(name, index, weight, expected):
    n = expected["degree_n"]
    receipt = json.loads((PARENT / "q1456_joint_domain_profile/runs" /
                          name / "receipt.json").read_text())
    state = receipt["solver_report"]["domain_snapshots"][index]
    onb = field.Onb(n)
    domains = []
    for fixed, ones in zip(state["leaf_fixed_mask_onb_hex"],
                           state["leaf_ones_onb_hex"]):
        domains.append(options(PartialLeaf(int(fixed, 16), int(ones, 16)),
                               n, weight))
    exact = next(row for row in expected["exact_midpoint_rows"]
                 if row["state_index"] == index)
    midpoint_sets = []
    for side in (0, 2):
        mids = set()
        for a, b in itertools.product(domains[side], domains[side + 1]):
            roots = s3_roots(onb, onb.fromCoords(a), onb.fromCoords(b))
            mids.update(onb.toCoords(x) for x in roots)
        midpoint_sets.append(mids)
    cardinalities = [len(mids) for mids in midpoint_sets]
    ranks = [affine_rank(mids) for mids in midpoint_sets]
    assert cardinalities == exact["midpoint_cardinalities"]
    assert ranks == exact["affine_ranks"] == [n, n]
    return {"cell": name, "state_index": index,
            "midpoint_cardinalities": cardinalities, "affine_ranks": ranks}


def verify():
    result = json.loads((HERE / "result.json").read_text())
    cells = {cell["name"]: cell for cell in result["cells"]}
    controls = [replay("n53_ordinary", 20, 4, cells["n53_ordinary"]),
                replay("n83_ordinary", 22, 6, cells["n83_ordinary"])]
    return {"proposal_id": "Q1463", "status": "pass",
            "result_sha256": sha(HERE / "result.json"),
            "protocol_sha256": sha(HERE / "protocol.json"),
            "checked_sage_runtime_info_sha256": sha(HERE /
                                                      "sage_runtime_info.json"),
            "independent_sage_replays": controls,
            "scope": "two bounded raw states; not a natural relation or solver-cost check"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = verify()
    if args.check:
        assert expected == json.loads(OUTPUT.read_text())
        print("Q1463 independent Sage replay: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
