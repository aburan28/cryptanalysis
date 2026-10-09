"""Write-once source and resource protocol for the affine-span screen."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PAIR = GOAL / "n131_d13_same_rotation_pairs_20261009"
STATIC = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"


def main():
    path = HERE / "protocol.json"
    sources = {
        "producer": HERE / "produce.py",
        "runtime": HERE / "runtime_info.json",
        "geometry": STATIC / "d13_exact_geometry_v1.json",
        "valid_codes": PAIR / "valid_codes.json",
        "pair_result": PAIR / "result.json",
        "pair_source": PAIR / "run.py",
        "field": CODEGEN / "field.py",
        "curves": CODEGEN / "curves.py",
    }
    protocol = {
        "kind": "n131_d13_pair_output_affine_span_protocol",
        "status": "FROZEN",
        "proposal_id": "Q20261009214000",
        "candidate_id": None,
        "run_id": None,
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "input_policy": "independent sampled usable d13 selectors at rotation zero; exact subgroup pair sum",
        "sample_seed": 20261009214007,
        "max_pair_attempts": 4096,
        "wall_cap_seconds": 600,
        "rss_cap_bytes": 4 * 1024 ** 3,
        "acceptance": "132 independent augmented [1, phi(P+Q)] rows with independent group replay",
        "source_sha256": {key: hashlib.sha256(source.read_bytes()).hexdigest()
                          for key, source in sources.items()},
    }
    with path.open("x") as stream:
        json.dump(protocol, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(path)


if __name__ == "__main__":
    main()
