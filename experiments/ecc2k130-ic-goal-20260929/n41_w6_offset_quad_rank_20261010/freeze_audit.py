"""Freeze exact audit inputs after the checked Sage runtime receipt exists."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
paths = {"audit_sage.py": HERE / "audit_sage.py",
         "input": BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt",
         "quad_outputs.tsv": HERE / "quad_outputs.tsv",
         "rank_result.json": HERE / "rank_result.json",
         "sage_runtime_info.json": HERE / "sage_runtime_info.json"}
record = {"status": "FROZEN_BEFORE_INDEPENDENT_SAGE_AUDIT",
          "sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                     for name, path in paths.items()},
          "audit_command": "./sage -python experiments/ecc2k130-ic-goal-20260929/n41_w6_offset_quad_rank_20261010/audit_sage.py"}
with (HERE / "sage_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
