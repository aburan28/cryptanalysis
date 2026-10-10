#!/usr/bin/env python3
"""Freeze exact source, point, geometry, solver, and limits before queries."""

import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError("preserve first frozen protocol")
    geometry = json.loads(run.GEOMETRY.read_text())
    public = json.loads(run.PUBLIC.read_text())
    preflight = json.loads((HERE / "preflight.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    if (geometry["curve_id"] != public["curve_id"] or
            geometry["fixed_seed_sum_code"] != 56 or
            geometry["permitted_mask_pairs"] != 40 or
            geometry["folded_columns_K"] != 77 or
            geometry["actual_usable_base_points_B"] != 1120 or
            preflight["status"] != "PASS_BALANCED_SIX_PREFLIGHT" or
            preflight["target_q"] != public["target_q"] or
            runtime["status"] != "verified"):
        raise ValueError("geometry, target, preflight, or checked runtime changed")
    record = {"status": "FROZEN", "proposal_id": run.PROPOSAL_ID,
              "candidate_id": None, "curve_id": geometry["curve_id"],
              "target_count": 1, "target_q": public["target_q"],
              "input_law": "one previously supplied frozen public subgroup point",
              "summands": 12, "pair_blocks": 6,
              "actual_usable_factor_base_points_B": 960,
              "effective_folded_columns_K": 77,
              "pair_descriptors_per_block": 80,
              "rotations": geometry["rotations"][:6],
              "control_wall_cap_seconds": 30,
              "online_wall_cap_seconds": 120,
              "rss_cap_bytes": 4*1024**3,
              "workers": 1,
              "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                               "--random=174000", "--maxconfl=2000000"],
              "source_sha256": {name: run.sha(path)
                                for name, path in run.source_paths().items()}}
    output.write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": "FROZEN", "proposal_id": run.PROPOSAL_ID,
                      "source_files": len(record["source_sha256"])}, sort_keys=True))


if __name__ == "__main__":
    main()
