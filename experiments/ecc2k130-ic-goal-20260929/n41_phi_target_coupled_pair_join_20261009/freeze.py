"""Freeze the N41 one-target group-join method and source receipts before execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "runtime_info.json").read_text())
    source = json.loads((BASE / "protocol.json").read_text())
    table = json.loads((BASE / "table.json").read_text())
    if (runtime["status"] != "verified" or source["field_degree"] != 41 or
            source["summands"] != 12 or source["target_count"] != 1 or
            source["valid_selector_count"] != 30 or
            len(table["valid_codes"]) != 30):
        raise ValueError("frozen N41 workload differs from join contract")
    paths = {"source_protocol": BASE / "protocol.json",
             "source_table": BASE / "table.json",
             "source_formula": BASE / "source.xcnf",
             "run_join": HERE / "run_join.py",
             "replay": HERE / "replay.py",
             "curves": CODEGEN / "curves.py",
             "field": CODEGEN / "field.py",
             "runtime": HERE / "runtime_info.json"}
    protocol = {
        "kind": "n41_phi_target_coupled_five_plus_five_group_join_protocol",
        "status": "FROZEN", "proposal_id": "Q20261009211000",
        "candidate_id": None, "run_id": None,
        "target_count": 1, "batch": False,
        "curve_id": None, "subgroup_order": source["subgroup_order"],
        "frozen_public_target_coordinates": source["target_coordinates"],
        "first_leaf_codes": table["first_link_leaf_codes"],
        "first_root_phi_mask": table["selected_first_link_root"],
        "summands": 12, "valid_codes_per_slot": 30,
        "signed_options_per_slot": 60,
        "left_slots": [2, 3, 4, 5, 6],
        "right_slots": [7, 8, 9, 10, 11],
        "reusable_pair_slots": [[2, 3], [4, 5], [8, 9], [10, 11]],
        "left_sample_seed": 20261009140901,
        "right_sample_seed": 20261009140902,
        "left_samples": 1800000, "right_samples": 2000000,
        "setup_wall_cap_seconds": 600,
        "online_wall_cap_seconds": 600,
        "combined_rss_cap_bytes": 4294967296,
        "online_start": "first target-dependent endpoint conversion from supplied public Q after reusable index setup",
        "online_stop": "first exact point-addition-checked relation or frozen cap",
        "replay_policy": "independent checked-Sage group, subgroup, distinct-x, and public-XCNF replay after online clock",
        "source_sha256": {key: sha(path) for key, path in paths.items()},
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"],
                      "left_samples": protocol["left_samples"],
                      "right_samples": protocol["right_samples"]}))


if __name__ == "__main__":
    main()
