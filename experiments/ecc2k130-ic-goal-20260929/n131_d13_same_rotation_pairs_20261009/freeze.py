"""Freeze N131 same-rotation pair inverse controls before local execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
STATIC = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static"
PIPELINE = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"


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
    geometry_path = STATIC / "d13_exact_geometry_v1.json"
    manifest_path = PIPELINE / "d13_m12_candidate_manifest_v1.json"
    geometry = json.loads(geometry_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    runtime = json.loads((HERE / "runtime_info.json").read_text())
    factor_base = geometry["factor_base"]
    curve = manifest["candidate_record"]["curve"]
    if (geometry["status"] != "PASS" or runtime["status"] != "verified" or
            geometry["curve_id"] != curve["curve_id"] or
            factor_base["distinct_nonidentity_signed_subgroup_options_per_position"] != 4134 or
            factor_base["actual_distinct_nonidentity_subgroup_points_before_sign_frobenius_folding"] != 1083108 or
            factor_base["folded_frobenius_columns"] != 4134):
        raise ValueError("frozen d13 geometry or Sage runtime differs")
    rotations = [rotation for rotation in (0, 22, 44, 66, 88, 110)
                 for _ in range(2)]
    if len(rotations) != 12 or len(set(rotations)) != 6:
        raise ValueError("same-rotation six-pair schedule changed")
    paths = {"geometry": geometry_path,
             "manifest": manifest_path,
             "run": HERE / "run.py",
             "field": CODEGEN / "field.py",
             "curves": CODEGEN / "curves.py",
             "runtime": HERE / "runtime_info.json"}
    protocol = {
        "kind": "n131_d13_same_rotation_pair_inverse_protocol",
        "status": "FROZEN", "proposal_id": "Q20261009212400",
        "candidate_id": None, "run_id": None,
        "curve_id": geometry["curve_id"],
        "field_degree": 131, "subspace_dimension": 13,
        "summand_count_proposal": 12,
        "rotation_schedule": rotations,
        "factor_base_policy": "same audited d13 Frobenius closure; only the twelve ordered leaf rotations change",
        "actual_factor_base_points_B": 1083108,
        "effective_folded_columns_K": 4134,
        "target_query_launched": False,
        "control_seed": 20261009212411,
        "positive_controls": 32,
        "negative_controls": 128,
        "total_wall_cap_seconds": 600,
        "rss_cap_bytes": 4294967296,
        "source_sha256": {key: sha(path) for key, path in paths.items()},
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"],
                      "rotation_schedule": rotations}))


if __name__ == "__main__":
    main()
