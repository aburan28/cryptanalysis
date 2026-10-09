"""Freeze an all-sum pair inverse comparison before measured execution."""

import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_d13_same_rotation_pairs_20261009"
GEOMETRY = HERE.parent / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static/d13_exact_geometry_v1.json"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    source = json.loads((SOURCE / "result.json").read_text())
    geometry = json.loads(GEOMETRY.read_text())
    if (source["status"] != "PASS_EXACT_PAIR_INVERSE_CONTROLS" or
            source["valid_selector_count"] != 4134 or
            geometry["curve_id"] != "EC1N131Ckb1heb5f1998f20b"):
        raise ValueError("source geometry changed")
    inputs = [{"kind": "positive", "z_mask": item["output_phi_mask"],
               "pair": item["codes"]} for item in source["positive_controls"]]
    rng = random.Random(20261009225000)
    while len(inputs) < 64:
        mask = rng.randrange(2, 1 << 131)
        if mask not in {item["z_mask"] for item in inputs}:
            inputs.append({"kind": "uniform_field_control", "z_mask": mask,
                           "pair": None})
    paths = {"run": HERE / "run.py", "audit": HERE / "audit.py",
             "field": CODEGEN / "field.py", "geometry": GEOMETRY,
             "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "source_result": SOURCE / "result.json",
             "runtime": HERE / "runtime_info.json"}
    protocol = {"status": "FROZEN", "proposal_id": "Q20261009225000",
                "candidate_id": None, "curve_id": geometry["curve_id"],
                "question": "Does linear batching lower exact full-sum pair inverse stage cost?",
                "basis_masks_hex": geometry["domain"]["basis_coordinate_masks_hex"],
                "inputs": inputs, "input_law": "32 source positive pair outputs and 32 independently seeded uniform nonzero 131-bit coordinate masks; same 64 inputs for each method",
                "repetitions": 2, "wall_cap_seconds": 300,
                "rss_cap_bytes": 4 * 1024**3,
                "methods": ["direct_product", "linear_dense", "linear_gray"],
                "measurement_boundary": "all 8191 seed sums and pair validation for one proposed output; index and field setup excluded; methods interleaved per input; correctness and audit outside timing",
                "host_isolation": None, "source_sha256":
                {name: sha(path) for name, path in paths.items()}}
    output.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": protocol["status"], "inputs": len(inputs),
                      "methods": protocol["methods"]}))


if __name__ == "__main__":
    main()
