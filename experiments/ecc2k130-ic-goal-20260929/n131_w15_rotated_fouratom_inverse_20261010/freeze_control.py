"""Freeze the two exact control sources for the rotated resultant."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
paths = {"control.py": HERE / "control.py", "resultant": HERE / "resultant.json",
         "n41_screen": BASE / "n41_n131_diagonal_atom_20261010/screen.json",
         "n41_hit": BASE / "n131_w15_cross_block_seed_offset_20261010/n41_hit.json",
         "n131_lift": BASE / "n131_w15_coupled_sixpair_20261010/control_group_lift.json",
         "sage_runtime_info": HERE / "sage_runtime_info.json"}
record = {"status": "FROZEN_BEFORE_ROTATED_RESULTANT_CONTROLS",
          "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for name,path in paths.items()},
          "cases": ["N41 public relation block rotations 10,15",
                    "N131 constructed witness block rotations 26,39"],
          "field_control": "field generator plus one, separately from constructed four-atom output"}
with (HERE / "control_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
