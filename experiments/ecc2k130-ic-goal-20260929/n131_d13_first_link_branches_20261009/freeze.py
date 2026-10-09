#!/usr/bin/env python3
"""Freeze both exact first-link roots for one N131 d13 public-Q leaf pair."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PRIOR = GOAL / "n131_d13_two_leaf_cubes_20261009"
SOURCE = PRIOR / "cube0.xcnf"
ROOTS = PRIOR / "first_link_candidates.json"
MAPPING = (GOAL / "n131_d13_public_bridge_projection_20261009/"
           "budget1/variable_map.json")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RUNTIME = HERE / "runtime_info.json"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    prior = json.loads((PRIOR / "protocol.json").read_text())
    roots = json.loads(ROOTS.read_text())
    runtime = json.loads(RUNTIME.read_text())
    if (runtime["status"] != "verified" or
            roots["status"] != "PASS_TWO_COMPLETE_ROOTS_PER_CUBE" or
            roots["source_sha256"]["protocol"] != sha(PRIOR / "protocol.json") or
            prior["cubes"][0]["formula_sha256"] != sha(SOURCE) or
            roots["cubes"][0]["leaf_codes"] != prior["cubes"][0]["leaf_codes"]):
        raise ValueError("prior frozen public-Q cube or checked roots changed")
    mapping = json.loads(MAPPING.read_text())
    if mapping["new_to_old"][:289] != list(range(289)):
        raise ValueError("first partial-coordinate variables did not survive projection")
    branches = []
    for index, mask in enumerate(roots["cubes"][0]["partial0_phi_masks"]):
        destination = HERE / f"branch{index}.xcnf"
        if destination.exists():
            raise FileExistsError(destination)
        units = [158 + bit if (mask >> bit) & 1 else -(158 + bit)
                 for bit in range(131)]
        with SOURCE.open("rt", encoding="ascii") as src, destination.open(
                "x", encoding="ascii") as dst:
            header = src.readline().split()
            if header != ["p", "cnf", "115289", "292581"]:
                raise ValueError("source two-leaf cube dimensions changed")
            dst.write(f"p cnf {header[2]} {int(header[3]) + 131}\n")
            for line in src:
                dst.write(line)
            for value in units:
                dst.write(f"{value} 0\n")
        branches.append({
            "leaf_codes": prior["cubes"][0]["leaf_codes"],
            "partial0_phi_mask": mask,
            "unit_literals": units,
            "formula_sha256": sha(destination),
            "formula_bytes": destination.stat().st_size,
        })
    record = {
        "kind": "n131_d13_m12_exact_first_link_root_branches",
        "status": "FROZEN_PROPOSAL", "proposal_id": "Q20261009125500",
        "curve_id": prior["curve_id"], "workload_id": prior["workload_id"],
        "candidate_id": None, "run_id": None,
        "target_count": 1, "batch": False,
        "query_role": "one supplied public-Q point-decomposition stage",
        "branch_rule": "both exact S3 roots of partial0 for deterministic cube0 leaf codes; no witness or scalar pins",
        "root_completeness": "two distinct checked-Sage curve sums satisfy a degree-two first-link equation with nonzero leading coefficient",
        "cubes": branches,
        "solver_flags": prior["solver_flags"],
        "per_cube_wall_cap_seconds": 290,
        "total_solver_stage_cap_seconds": 580,
        "combined_rss_cap_bytes": 4294967296,
        "model_rule": "branch and original XCNF checks, then independent checked-Sage point and subgroup replay",
        "source_sha256": {"raw": prior["source_sha256"]["raw"],
                          "projected": prior["source_sha256"]["projected"],
                          "mapping": sha(MAPPING), "solver": sha(SOLVER),
                          "runtime": sha(RUNTIME), "freeze": sha(Path(__file__)),
                          "prior_cube0": sha(SOURCE), "roots": sha(ROOTS)},
        "accounting_boundary": "both exact first-link branches are one public target; failed attempts charged to that target; full online time needs source construction and transformations",
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN_PROPOSAL", "roots": [b["partial0_phi_mask"] for b in branches]}))


if __name__ == "__main__":
    main()
