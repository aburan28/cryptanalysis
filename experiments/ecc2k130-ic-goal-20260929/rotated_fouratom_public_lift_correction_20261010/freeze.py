"""Freeze corrected H-coordinate public preimages before computation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
paths = {"script": HERE / "correct.py",
         "resultant": ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json",
         "controls": ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "control_result.json",
         "n41_public": ROOT / "n41_seed_partition_indexless_20261010" / "replay_result.json",
         "n131_archived_preimages": ROOT / "n131_fixed_seed_eight_pair_circuit_20261010" / "target_preimages.json",
         "prior_torsion_screen": ROOT / "rotated_fouratom_factorization_20261010" / "torsion_result.json",
         "runtime": HERE / "sage_runtime_info.json"}
record = {"status": "FROZEN_BEFORE_CORRECTED_RECIPROCAL_X_PUBLIC_LIFTS",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "workers": 1, "parent_wall_cap_seconds": 120,
          "coordinate_contract": {"rotated_resultant": "1/x",
                                  "archived_target_preimages": "1/(x+1)"}}
with (HERE / "protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
