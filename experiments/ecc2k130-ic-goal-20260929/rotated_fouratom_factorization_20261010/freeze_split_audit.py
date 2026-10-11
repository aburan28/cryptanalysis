"""Freeze independent bit-field replay of the native quartic scan."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
paths = {"audit": HERE / "audit_split.py", "split": HERE / "split_n131_positive.json",
         "split_receipt": HERE / "split_receipt.json", "factor": HERE / "n131_positive.json",
         "legacy": SOURCE / "native_n131_positive.json",
         "control": SOURCE / "control_result.json", "resultant": SOURCE / "resultant.json"}
record = {"status": "FROZEN_BEFORE_INDEPENDENT_SPLIT_NATIVE_ROOT_REPLAY",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "method": "independent GF(2^131) arithmetic, linear-GCD root, and factor evaluation"}
with (HERE / "split_audit_protocol.json").open("x") as out:
    json.dump(record, out, sort_keys=True, indent=2)
    out.write("\n")
