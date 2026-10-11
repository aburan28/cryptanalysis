"""Bind the torsion-shift specialization screen before execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
paths = {"screen": HERE / "screen_torsion.py",
         "resultant": ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json",
         "controls": ROOT / "n131_w15_rotated_fouratom_inverse_20261010" / "control_result.json",
         "public_preimages": ROOT / "n131_fixed_seed_eight_pair_circuit_20261010" / "target_preimages.json",
         "runtime": HERE / "sage_runtime_info.json"}
record = {"status": "FROZEN_BEFORE_TORSION_SHIFT_FACTORIZATION_SCREEN",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "worker_count": 1,
          "parent_wall_cap_seconds": 100,
          "field_moduli": ["t^41+t^3+1", "t^131+t^13+t^2+t+1"],
          "output_scope": "exact factor degrees and trace character; times exploratory"}
with (HERE / "torsion_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
