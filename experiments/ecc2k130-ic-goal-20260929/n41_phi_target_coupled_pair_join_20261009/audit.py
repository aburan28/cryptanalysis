"""Audit frozen source, terminal bounds, and independent Sage replay receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
TEMPLATE = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/"
            "m16_static/phi_frobenius_sat_gate_m16_sparse_seed_v1.py")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, result_path, replay_path = (HERE / name for name in
                                               ("protocol.json", "result.json",
                                                "replay.json"))
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    replay = json.loads(replay_path.read_text())
    source = json.loads((BASE / "protocol.json").read_text())
    paths = {"source_protocol": BASE / "protocol.json",
             "source_table": BASE / "table.json",
             "source_formula": BASE / "source.xcnf",
             "run_join": HERE / "run_join.py",
             "replay": HERE / "replay.py",
             "curves": CODEGEN / "curves.py",
             "field": CODEGEN / "field.py",
             "runtime": HERE / "runtime_info.json"}
    for name, path in paths.items():
        if protocol["source_sha256"][name] != sha(path):
            raise ValueError(f"frozen {name} source changed")
    if (source["source_sha256"]["source"] != sha(BASE / "source.xcnf") or
            source["source_sha256"]["template"] != sha(TEMPLATE) or
            result["status"] != "VERIFIED_ORDINARY_RELATION" or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            replay["status"] != "PASS_ORDINARY_RELATION_AND_PUBLIC_XCNF" or
            replay["source_sha256"]["result"] != sha(result_path) or
            replay["source_sha256"]["replay"] != sha(HERE / "replay.py") or
            protocol["target_count"] != 1 or protocol["batch"] is not False):
        raise ValueError("terminal result or independent replay differs")
    if (result["left_draws"] != protocol["left_samples"] or
            result["left_distinct_group_points"] > result["left_draws"] or
            not 0 < result["right_draws"] <= protocol["right_samples"] or
            result["hash_hits"] < 1 or result["witness"] is None or
            result["setup_wall_ns"] <= 0 or
            result["target_dependent_online_wall_ns"] <= 0 or
            result["setup_wall_ns"] > protocol["setup_wall_cap_seconds"] * 1_000_000_000 or
            result["target_dependent_online_wall_ns"] >
            protocol["online_wall_cap_seconds"] * 1_000_000_000 or
            result["peak_rss_bytes"] > protocol["combined_rss_cap_bytes"] or
            result["target_endpoint_conversion_ns"] +
            result["target_relation_check_ns"] >
            result["target_dependent_online_wall_ns"] or
            len(replay["leaf_codes"]) != 12 or
            len(replay["partial_phi_masks"]) != 10):
        raise ValueError("search bound or witness record is inconsistent")
    receipt = {"kind": "n41_phi_target_coupled_join_terminal_audit",
               "status": "PASS_FROZEN_RELATION_AND_XCNF_REPLAY",
               "candidate_id": None, "run_id": None, "target_count": 1,
               "left_draws": result["left_draws"],
               "left_distinct_group_points": result["left_distinct_group_points"],
               "right_draws": result["right_draws"],
               "setup_wall_ns": result["setup_wall_ns"],
               "target_dependent_online_wall_ns":
               result["target_dependent_online_wall_ns"],
               "peak_rss_bytes": result["peak_rss_bytes"],
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "replay": sha(replay_path),
                                 "auditor": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"]}))


if __name__ == "__main__":
    main()
