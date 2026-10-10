#!/usr/bin/env python3
"""Freeze a source-bound d13 pair-output quadratic-rank experiment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
ROOT = GOAL.parents[1]
SOURCE = GOAL / "n131_d13_same_rotation_pairs_20261009"
PILOT = GOAL / "n131_d13_batch_pair_outputs_20261009"
MANIFEST = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline/d13_m12_candidate_manifest_v1.json"
GEOMETRY = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static/d13_exact_geometry_v1.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paths():
    return {
        "sample.py": HERE / "sample.py",
        "rank.cpp": HERE / "rank.cpp",
        "audit_rank.cpp": HERE / "audit_rank.cpp",
        "audit.py": HERE / "audit.py",
        "pilot.py": PILOT / "pilot.py",
        "pilot_protocol": PILOT / "protocol.json",
        "pilot_runtime": PILOT / "sage_runtime_info.json",
        "geometry": GEOMETRY,
        "valid_codes": SOURCE / "valid_codes.json",
        "manifest": MANIFEST,
        "onb_field": ROOT / "ecc2k130/codegen/field.py",
        "onb_curve": ROOT / "ecc2k130/codegen/curves.py",
        "runtime": HERE / "sage_runtime_info.json",
    }


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    if runtime["status"] != "verified":
        raise ValueError("checked Sage runtime was not verified")
    manifest = json.loads(MANIFEST.read_text())
    curve_id = manifest["candidate_record"]["curve"]["curve_id"]
    if curve_id != "EC1N131Ckb1heb5f1998f20b":
        raise ValueError("d13 candidate curve identity changed")
    valid = json.loads((SOURCE / "valid_codes.json").read_text())
    if len(valid) != 4134 or valid != sorted(set(valid)):
        raise ValueError("d13 valid-code list changed")
    protocol = {
        "status": "FROZEN", "kind": "n131_d13_pair_phi_quadratic_rank",
        "proposal_id": "Q20261009173000", "curve_id": curve_id,
        "candidate_id": None, "run_id": None,
        "input_law": "seeded sample of 2200 right codes for each of the first four valid left codes, both signed sums",
        "sample_seed": 20261009173000, "left_count": 4,
        "partners_per_left": 2200, "sample_rows": 17600,
        "record_bytes": 22, "field_bits": 131,
        "quadratic_features": 1 + 131 + 131 * 130 // 2,
        "sample_wall_cap_seconds": 300, "rank_wall_cap_seconds": 300,
        "rss_cap_bytes": 4 * 1024**3,
        "source_sha256": {name: sha(path) for name, path in paths().items()},
    }
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "curve_id": curve_id,
                      "rows": protocol["sample_rows"],
                      "features": protocol["quadratic_features"]}))


if __name__ == "__main__":
    main()
