"""Freeze known-row raw-lift replay after correcting public preimages."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
paths = {"lift": HERE / "lift_witness.py", "corrected": HERE / "result.json",
         "screen": ROOT / "n41_n131_diagonal_atom_20261010" / "screen.json",
         "hit": ROOT / "n41_seed_partition_indexless_20261010" / "hit.json",
         "runtime": HERE / "sage_runtime_info.json"}
record = {"status": "FROZEN_BEFORE_N41_PUBLIC_RELATION_RAW_LIFT_REPLAY",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "scope": "known public relation correctness control; raw lift identity for the unpinned joint solver"}
with (HERE / "lift_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
