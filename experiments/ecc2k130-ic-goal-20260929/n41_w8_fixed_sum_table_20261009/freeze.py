#!/usr/bin/env python3
"""Freeze exact pair-table N41 equations before pinned and public runs."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    geometry = json.loads((HERE / "geometry.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    public = json.loads(run.PUBLIC.read_text())
    if (geometry["status"] != "EXACT_FIXED_SUM_GEOMETRY" or
            geometry["curve_id"] != public["curve_id"] or
            geometry["fixed_seed_sum_code"] != 56 or
            geometry["permitted_mask_pairs"] != 40 or
            geometry["folded_columns_K"] != 77 or
            geometry["actual_usable_base_points_B"] != 1120 or
            geometry["product_map_rank"] != 7 or
            runtime["status"] != "verified"):
        raise ValueError("frozen geometry, target, or runtime failed preflight")
    source_hashes = {name: run.sha(path) for name, path in run.source_paths().items()}
    record = {"status": "FROZEN", "kind": "n41_w8_exact_pair_table_six_pair_public_query",
              "curve_id": geometry["curve_id"],
              "proposal_id": run.PROPOSAL_ID,
              "candidate_id": None, "run_id": None,
              "target_count": 1, "summands": 12, "pair_blocks": 6,
              "fixed_seed_sum_code": 56,
              "actual_usable_factor_base_points_B": 960,
              "effective_folded_columns_K": 77,
              "input_law": "one frozen ordinary public subgroup point, with saved relation pinned only in the correctness control",
              "public_target_q": public["target_q"],
              "rotations": geometry["rotations"][:6],
              "control_wall_cap_seconds": 30,
              "online_wall_cap_seconds": 120,
              "rss_cap_bytes": 4*1024**3,
              "workers": 1,
              "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                               "--random=174000", "--maxconfl=2000000"],
              "source_sha256": source_hashes}
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "B": 960, "K": 77,
                      "pair_blocks": 6, "public_target_q": record["public_target_q"]}))


if __name__ == "__main__":
    main()
